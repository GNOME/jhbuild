# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007-2008  Frederic Peters
#
#   config.py: configuration file parser
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import re
import sys
import traceback
import time
import types
import logging
import __builtin__

from jhbuild.errors import UsageError, FatalError, CommandError
from jhbuild.utils.cmds import get_output

if sys.platform.startswith('win'):
    # For munging paths for MSYS's benefit
    import jhbuild.utils.subprocess_win32

__all__ = [ 'Config' ]

_defaults_file = os.path.join(os.path.dirname(__file__), 'defaults.jhbuildrc')
_default_jhbuildrc = os.path.join(os.environ['HOME'], '.jhbuildrc')

_known_keys = [ 'moduleset', 'modules', 'skip', 'tags', 'prefix',
                'partial_build', 'checkoutroot', 'buildroot', 'top_builddir',
                'autogenargs', 'makeargs', 'nice_build', 'jobs',
                'installprog', 'repos', 'branches', 'noxvfb', 'xvfbargs',
                'builddir_pattern', 'module_autogenargs', 'module_makeargs',
                'interact', 'buildscript', 'nonetwork',
                'nobuild', 'makeclean', 'makecheck', 'module_makecheck',
                'use_lib64', 'tinderbox_outputdir', 'sticky_date',
                'tarballdir', 'pretty_print', 'svn_program', 'makedist',
                'makedistcheck', 'nonotify', 'notrayicon', 'cvs_program',
                'checkout_mode', 'copy_dir', 'module_checkout_mode',
                'build_policy', 'trycheckout', 'min_age',
                'nopoison', 'module_nopoison', 'forcecheck',
                'makecheck_advisory', 'quiet_mode', 'progress_bar',
                'module_extra_env', 'jhbuildbot_master', 'jhbuildbot_slavename',
                'jhbuildbot_password', 'jhbuildbot_svn_commits_box',
                'jhbuildbot_slaves_dir', 'jhbuildbot_dir',
                'jhbuildbot_mastercfg', 'use_local_modulesets',
                'ignore_suggests', 'modulesets_dir', 'mirror_policy',
                'module_mirror_policy', 'dvcs_mirror_dir', 'build_targets',
                'cmakeargs', 'module_cmakeargs', 'print_command_pattern',
                'static_analyzer', 'module_static_analyzer', 'static_analyzer_template', 'static_analyzer_outputdir',

                # Internal only keys (propagated from command line options)
                '_internal_noautogen',
                ]

env_prepends = {}
def prependpath(envvar, path):
    env_prepends.setdefault(envvar, []).append(path)

def addpath(envvar, path):
    '''Adds a path to an environment variable.'''
    # special case ACLOCAL_FLAGS
    if envvar in [ 'ACLOCAL_FLAGS' ]:
        if sys.platform.startswith('win'):
            path = jhbuild.utils.subprocess_win32.fix_path_for_msys(path)

        envval = os.environ.get(envvar, '-I %s' % path)
        parts = ['-I', path] + envval.split()
        i = 2
        while i < len(parts)-1:
            if parts[i] == '-I':
                # check if "-I parts[i]" comes earlier
                for j in range(0, i-1):
                    if parts[j] == '-I' and parts[j+1] == parts[i+1]:
                        del parts[i:i+2]
                        break
                else:
                    i += 2
            else:
                i += 1
        envval = ' '.join(parts)
    elif envvar in [ 'LDFLAGS', 'CFLAGS', 'CXXFLAGS' ]:
        if sys.platform.startswith('win'):
            path = jhbuild.utils.subprocess_win32.fix_path_for_msys(path)

        envval = os.environ.get(envvar)
        if envval:
            envval = path + ' ' + envval
        else:
            envval = path
    else:
        if envvar == 'PATH':
            # PATH is special cased on Windows to allow execution without
            # sh.exe. The other env vars (like LD_LIBRARY_PATH) don't mean
            # anything to native Windows so they stay in UNIX format, but
            # PATH is kept in Windows format (; separated, c:/ or c:\ format
            # paths) so native Popen works.
            pathsep = os.pathsep
        else:
            pathsep = ':'
            if sys.platform.startswith('win'):
                path = jhbuild.utils.subprocess_win32.fix_path_for_msys(path)

            if sys.platform.startswith('win') and len(path) > 1 and \
               path[1] == ':':
                # Windows: Don't allow c:/ style paths in :-separated env vars
                # for obvious reasons. /c/ style paths are valid - if a var is
                # separated by : it will only be of interest to programs inside
                # MSYS anyway.
                path='/'+path[0]+path[2:]

        envval = os.environ.get(envvar, path)
        parts = envval.split(pathsep)
        parts.insert(0, path)
        # remove duplicate entries:
        i = 1
        while i < len(parts):
            if parts[i] in parts[:i]:
                del parts[i]
            elif envvar == 'PYTHONPATH' and parts[i] == "":
                del parts[i]
            else:
                i += 1
        envval = pathsep.join(parts)

    os.environ[envvar] = envval

def parse_relative_time(s):
    m = re.match(r'(\d+) *([smhdw])', s.lower())
    if m:
        coeffs = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w':7*86400}
        return float(m.group(1)) * coeffs[m.group(2)]
    else:
        raise ValueError


class Config:
    _orig_environ = None

    def __init__(self, filename=_default_jhbuildrc):
        self._config = {
            '__file__': _defaults_file,
            'addpath':  addpath,
            'prependpath':  prependpath,
            'include': self.include,
            }

        if not self._orig_environ:
            self.__dict__['_orig_environ'] = os.environ.copy()
        os.environ['UNMANGLED_PATH'] = os.environ.get('PATH', '')

        try:
            SRCDIR
        except NameError:
            # this happens when an old jhbuild script is called
            if os.path.realpath(sys.argv[0]) == os.path.expanduser('~/bin/jhbuild'):
                # if it was installed in ~/bin/, it may be because the new one
                # is installed in ~/.local/bin/jhbuild
                if os.path.exists(os.path.expanduser('~/.local/bin/jhbuild')):
                    logging.warning(
                            _('JHBuild start script has been installed in '
                              '~/.local/bin/jhbuild, you should remove the '
                              'old version that is still in ~/bin/ (or make '
                              'it a symlink to ~/.local/bin/jhbuild)'))
            if os.path.exists(os.path.join(sys.path[0], 'jhbuild')):
                # the old start script inserted its source directory in
                # sys.path, use it now to set new variables
                __builtin__.__dict__['SRCDIR'] = sys.path[0]
                __builtin__.__dict__['PKGDATADIR'] = None
                __builtin__.__dict__['DATADIR'] = None
            else:
                raise FatalError(
                    _('Obsolete JHBuild start script, make sure it is removed '
                      'then do run \'make install\''))
            
        # Set defaults for internal variables
        self._config['_internal_noautogen'] = False

        env_prepends.clear()
        try:
            execfile(_defaults_file, self._config)
        except:
            traceback.print_exc()
            raise FatalError(_('could not load config defaults'))
        self._config['__file__'] = filename
        self.filename = filename
        if not os.path.exists(filename):
            raise FatalError(_('could not load config file, %s is missing') % filename)

        self.load()
        self.setup_env()

    def reload(self):
        os.environ = self._orig_environ.copy()
        self.__init__(filename=self._config.get('__file__'))
        self.set_from_cmdline_options(options=None)

    def include(self, filename):
        '''Read configuration variables from a file.'''
        try:
            execfile(filename, self._config)
        except:
            traceback.print_exc()
            raise FatalError(_('Could not include config file (%s)') % filename)

    def load(self):
        config = self._config
        try:
            execfile(self.filename, config)
        except Exception, e:
            if isinstance(e, FatalError):
                # raise FatalErrors back, as it means an error in include()
                # and it will print a traceback, and provide a meaningful
                # message.
                raise e
            traceback.print_exc()
            raise FatalError(_('could not load config file'))

        if not config.get('quiet_mode'):
            unknown_keys = []
            for k in config.keys():
                if k in _known_keys + ['cvsroots', 'svnroots', 'cflags']:
                    continue
                if k[0] == '_':
                    continue
                if type(config[k]) in (types.ModuleType, types.FunctionType, types.MethodType):
                    continue
                unknown_keys.append(k)
            if unknown_keys:
                logging.info(
                        _('unknown keys defined in configuration file: %s') % \
                        ', '.join(unknown_keys))

        # backward compatibility, from the days when jhbuild only
        # supported Gnome.org CVS.
        if config.get('cvsroot'):
            logging.warning(
                    _('the "%s" configuration variable is deprecated, '
                      'you should use "repos[\'gnome.org\']".') % 'cvsroot')
            config['repos'].update({'gnome.org': config['cvsroot']})
        if config.get('cvsroots'):
            logging.warning(
                    _('the "%s" configuration variable is deprecated, '
                      'you should use "repos".') % 'cvsroots')
            config['repos'].update(config['cvsroots'])
        if config.get('svnroots'):
            logging.warning(
                    _('the "%s" configuration variable is deprecated, '
                      'you should use "repos".') % 'svnroots')
            config['repos'].update(config['svnroots'])

        # environment variables
        if config.has_key('cflags') and config['cflags']:
            os.environ['CFLAGS'] = config['cflags']
        if config.get('installprog') and os.path.exists(config['installprog']):
            os.environ['INSTALL'] = config['installprog']

        for path_key in ('checkoutroot', 'buildroot', 'top_builddir',
                         'tinderbox_outputdir', 'tarballdir', 'copy_dir',
                         'jhbuildbot_slaves_dir', 'jhbuildbot_dir',
                         'jhbuildbot_mastercfg', 'modulesets_dir',
                         'dvcs_mirror_dir', 'static_analyzer_outputdir'):
            if config.get(path_key):
                config[path_key] = os.path.expanduser(config[path_key])

        # copy known config keys to attributes on the instance
        for name in _known_keys:
            setattr(self, name, config[name])

        # default tarballdir to checkoutroot
        if not self.tarballdir: self.tarballdir = self.checkoutroot

        # Ensure top_builddir is absolute
        if not os.path.isabs(self.top_builddir):
            self.top_builddir = os.path.join(self.prefix, self.top_builddir)

        # check possible checkout_mode values
        seen_copy_mode = (self.checkout_mode == 'copy')
        possible_checkout_modes = ('update', 'clobber', 'export', 'copy')
        if self.checkout_mode not in possible_checkout_modes:
            raise FatalError(_('invalid checkout mode'))
        for module, checkout_mode in self.module_checkout_mode.items():
            seen_copy_mode = seen_copy_mode or (checkout_mode == 'copy')
            if checkout_mode not in possible_checkout_modes:
                raise FatalError(_('invalid checkout mode (module: %s)') % module)
        if seen_copy_mode and not self.copy_dir:
            raise FatalError(_('copy mode requires copy_dir to be set'))

        if not os.path.exists(self.modulesets_dir):
            if self.use_local_modulesets:
                logging.warning(
                        _('modulesets directory (%s) not found, '
                          'disabling use_local_modulesets') % self.modulesets_dir)
                self.use_local_modulesets = False
            self.modulesets_dir = None

    def get_original_environment(self):
        return self._orig_environ

    def setup_env(self):
        '''set environment variables for using prefix'''

        if not os.path.exists(self.prefix):
            try:
                os.makedirs(self.prefix)
            except:
                raise FatalError(_('install prefix (%s) can not be created') % self.prefix)

        if not os.path.exists(self.top_builddir):
            try:
                os.makedirs(self.top_builddir)
            except OSError:
                raise FatalError(
                        _('working directory (%s) can not be created') % self.top_builddir)

        os.environ['JHBUILD_PREFIX'] = self.prefix

        os.environ['UNMANGLED_LD_LIBRARY_PATH'] = os.environ.get('LD_LIBRARY_PATH', '')

        if not os.environ.get('DBUS_SYSTEM_BUS_ADDRESS'):
            # Use the distribution's D-Bus for the system bus. JHBuild's D-Bus
            # will # be used for the session bus
            os.environ['DBUS_SYSTEM_BUS_ADDRESS'] = 'unix:path=/var/run/dbus/system_bus_socket'

        # LD_LIBRARY_PATH
        if self.use_lib64:
            libdir = os.path.join(self.prefix, 'lib64')
        else:
            libdir = os.path.join(self.prefix, 'lib')
        self.libdir = libdir
        addpath('LD_LIBRARY_PATH', libdir)

        # LDFLAGS and C_INCLUDE_PATH are required for autoconf configure
        # scripts to find modules that do not use pkg-config (such as guile
        # looking for gmp, or wireless-tools for NetworkManager)
        # (see bug #377724 and bug #545018)

        # This path doesn't always get passed to addpath so we fix it here
        if sys.platform.startswith('win'):
            libdir = jhbuild.utils.subprocess_win32.fix_path_for_msys(libdir)
        os.environ['LDFLAGS'] = ('-L%s ' % libdir) + os.environ.get('LDFLAGS', '')

        includedir = os.path.join(self.prefix, 'include')
        addpath('C_INCLUDE_PATH', includedir)
        addpath('CPLUS_INCLUDE_PATH', includedir)

        # On Mac OS X, we use DYLD_FALLBACK_LIBRARY_PATH
        addpath('DYLD_FALLBACK_LIBRARY_PATH', libdir)

        # PATH
        bindir = os.path.join(self.prefix, 'bin')
        addpath('PATH', bindir)

        # MANPATH
        manpathdir = os.path.join(self.prefix, 'share', 'man')
        addpath('MANPATH', '')
        addpath('MANPATH', manpathdir)

        # INFOPATH
        infopathdir = os.path.join(self.prefix, 'share', 'info')
        addpath('INFOPATH', infopathdir)

        # PKG_CONFIG_PATH
        if os.environ.get('PKG_CONFIG_PATH') is None and self.partial_build:
            for dirname in ('share', 'lib', 'lib64'):
                full_name = '/usr/%s/pkgconfig' % dirname
                if os.path.exists(full_name):
                    addpath('PKG_CONFIG_PATH', full_name)
        pkgconfigdatadir = os.path.join(self.prefix, 'share', 'pkgconfig')
        pkgconfigdir = os.path.join(libdir, 'pkgconfig')
        addpath('PKG_CONFIG_PATH', pkgconfigdatadir)
        addpath('PKG_CONFIG_PATH', pkgconfigdir)

        # GI_TYPELIB_PATH
        if not 'GI_TYPELIB_PATH' in os.environ:
            if self.use_lib64:
                full_name = '/usr/lib64/girepository-1.0'
            else:
                full_name = '/usr/lib/girepository-1.0'
            if os.path.exists(full_name):
                addpath('GI_TYPELIB_PATH', full_name)
        typelibpath = os.path.join(self.libdir, 'girepository-1.0')
        addpath('GI_TYPELIB_PATH', typelibpath)

        # XDG_DATA_DIRS
        if self.partial_build:
            addpath('XDG_DATA_DIRS', '/usr/share')
        xdgdatadir = os.path.join(self.prefix, 'share')
        addpath('XDG_DATA_DIRS', xdgdatadir)

        # XDG_CONFIG_DIRS
        if self.partial_build:
            addpath('XDG_CONFIG_DIRS', '/etc')
        xdgconfigdir = os.path.join(self.prefix, 'etc', 'xdg')
        addpath('XDG_CONFIG_DIRS', xdgconfigdir)

        # XCURSOR_PATH
        xcursordir = os.path.join(self.prefix, 'share', 'icons')
        addpath('XCURSOR_PATH', xcursordir)

        # GST_PLUGIN_PATH
        for gst in ('gstreamer-1.0', 'gstreamer-0.10'):
            gstplugindir = os.path.join(self.libdir , gst)
            if os.path.exists(gstplugindir):
                addpath('GST_PLUGIN_PATH', gstplugindir)

        # GST_REGISTRY
        gstregistry = os.path.join(self.prefix, '_jhbuild', 'gstreamer.registry')
        addpath('GST_REGISTRY', gstregistry)

        # ACLOCAL_PATH
        aclocalpath = os.path.join(self.prefix, 'share', 'aclocal')
        addpath('ACLOCAL_PATH', aclocalpath)

        # ACLOCAL_FLAGS
        aclocaldir = os.path.join(self.prefix, 'share', 'aclocal')
        if not os.path.exists(aclocaldir):
            try:
                os.makedirs(aclocaldir)
            except:
                raise FatalError(_("Can't create %s directory") % aclocaldir)
        if self.partial_build:
            if os.path.exists('/usr/share/aclocal'):
                addpath('ACLOCAL_FLAGS', '/usr/share/aclocal')
                if os.path.exists('/usr/local/share/aclocal'):
                    addpath('ACLOCAL_FLAGS', '/usr/local/share/aclocal')
        addpath('ACLOCAL_FLAGS', aclocaldir)

        # PERL5LIB
        perl5lib = os.path.join(self.prefix, 'lib', 'perl5')
        addpath('PERL5LIB', perl5lib)

        # These two variables are so that people who use "jhbuild shell"
        # can tweak their shell prompts and such to show "I'm under jhbuild".
        # The first variable is the obvious one to look for; the second
        # one is for historical reasons. 
        os.environ['UNDER_JHBUILD'] = 'true'
        os.environ['CERTIFIED_GNOMIE'] = 'yes'

        # PYTHONPATH
        # Python inside jhbuild may be different than Python executing jhbuild,
        # so it is executed to get its version number (fallback to local
        # version number should never happen)
        python_bin = os.environ.get('PYTHON', 'python')
        try:
            pythonversion = 'python' + get_output([python_bin, '-c',
                'import sys; print ".".join([str(x) for x in sys.version_info[:2]])'],
                get_stderr = False).strip()
        except CommandError:
            pythonversion = 'python' + str(sys.version_info[0]) + '.' + str(sys.version_info[1])

        # In Python 2.6, site-packages got replaced by dist-packages, get the
        # actual value by asking distutils
        # <http://bugzilla.gnome.org/show_bug.cgi?id=575426>
        try:
            python_packages_dir = get_output([python_bin, '-c',
                'import os, distutils.sysconfig; '\
                'print distutils.sysconfig.get_python_lib(prefix="%s").split(os.path.sep)[-1]' % self.prefix],
                get_stderr=False).strip()
        except CommandError:
            python_packages_dir = 'site-packages'
            
        if self.use_lib64:
            pythonpath = os.path.join(self.prefix, 'lib64', pythonversion, python_packages_dir)
            addpath('PYTHONPATH', pythonpath)
            if not os.path.exists(pythonpath):
                os.makedirs(pythonpath)

        pythonpath = os.path.join(self.prefix, 'lib', pythonversion, python_packages_dir)
        addpath('PYTHONPATH', pythonpath)
        if not os.path.exists(pythonpath):
            os.makedirs(pythonpath)

        # if there is a Python installed in JHBuild prefix, set it in PYTHON
        # environment variable, so it gets picked up by configure scripts
        # <http://bugzilla.gnome.org/show_bug.cgi?id=560872>
        if os.path.exists(os.path.join(self.prefix, 'bin', 'python')):
            os.environ['PYTHON'] = os.path.join(self.prefix, 'bin', 'python')

        # Mono Prefixes
        os.environ['MONO_PREFIX'] = self.prefix
        os.environ['MONO_GAC_PREFIX'] = self.prefix

        # GConf:
        # Create a GConf source path file that tells GConf to use the data in
        # the jhbuild prefix (in addition to the data in the system prefix),
        # and point to it with GCONF_DEFAULT_SOURCE_PATH so modules will be read
        # the right data (assuming a new enough libgconf).
        gconfdir = os.path.join(self.prefix, 'etc', 'gconf')
        gconfpathdir = os.path.join(gconfdir, '2')
        if not os.path.exists(gconfpathdir):
            os.makedirs(gconfpathdir)
        gconfpath = os.path.join(gconfpathdir, 'path.jhbuild')
        if not os.path.exists(gconfpath) and os.path.exists('/etc/gconf/2/path'):
            try:
                inp = open('/etc/gconf/2/path')
                out = open(gconfpath, 'w')
                for line in inp.readlines():
                    if '/etc/gconf' in line:
                        out.write(line.replace('/etc/gconf', gconfdir))
                    out.write(line)
                out.close()
                inp.close()
            except:
                traceback.print_exc()
                raise FatalError(_('Could not create GConf config (%s)') % gconfpath)
        os.environ['GCONF_DEFAULT_SOURCE_PATH'] = gconfpath

        # Set GCONF_SCHEMA_INSTALL_SOURCE to point into the jhbuild prefix so
        # modules will install their schemas there (rather than failing to
        # install them into /etc).
        os.environ['GCONF_SCHEMA_INSTALL_SOURCE'] = 'xml:merged:' + os.path.join(
                gconfdir, 'gconf.xml.defaults')

        # handle environment prepends ...
        for envvar in env_prepends.keys():
            for path in env_prepends[envvar]:
                addpath(envvar, path)


        # get rid of gdkxft from the env -- it will cause problems.
        if os.environ.has_key('LD_PRELOAD'):
            valarr = os.environ['LD_PRELOAD'].split(' ')
            for x in valarr[:]:
                if x.find('libgdkxft.so') >= 0:
                    valarr.remove(x)
            os.environ['LD_PRELOAD'] = ' '.join(valarr)

        self.update_build_targets()

    def update_build_targets(self):
        # update build targets according to old flags
        if self.makecheck and not 'check' in self.build_targets:
            self.build_targets.insert(0, 'check')
        if self.makeclean and not 'clean' in self.build_targets:
            self.build_targets.insert(0, 'clean')
        if self.nobuild:
            # nobuild actually means "checkout"
            for phase in ('configure', 'build', 'check', 'clean', 'install'):
                if phase in self.build_targets:
                    self.build_targets.remove(phase)
            self.build_targets.append('checkout')
        if self.makedist and not 'dist' in self.build_targets:
            self.build_targets.append('dist')
        if self.makedistcheck and not 'distcheck' in self.build_targets:
            self.build_targets.append('distcheck')

    def set_from_cmdline_options(self, options=None):
        if options is None:
            options = self.cmdline_options
        else:
            self.cmdline_options = options
        if hasattr(options, 'clean') and (
                options.clean and not 'clean' in self.build_targets):
            self.build_targets.insert(0, 'clean')
        if hasattr(options, 'check') and (
                options.check and not 'check' in self.build_targets):
            self.build_targets.insert(0, 'check')
        if hasattr(options, 'dist') and (
                options.dist and not 'dist' in self.build_targets):
            self.build_targets.append('dist')
        if hasattr(options, 'distcheck') and (
                options.distcheck and not 'distcheck' in self.build_targets):
            self.build_targets.append('distcheck')
        if hasattr(options, 'ignore_suggests') and options.ignore_suggests:
            self.ignore_suggests = True
        if hasattr(options, 'nonetwork') and options.nonetwork:
            self.nonetwork = True
        if hasattr(options, 'skip'):
            for item in options.skip:
                self.skip += item.split(',')
        if hasattr(options, 'tags'):
            for item in options.tags:
                self.tags += item.split(',')
        if hasattr(options, 'sticky_date') and options.sticky_date is not None:
                self.sticky_date = options.sticky_date
        if hasattr(options, 'xvfb') and options.noxvfb is not None:
                self.noxvfb = options.noxvfb
        if hasattr(options, 'trycheckout') and  options.trycheckout:
            self.trycheckout = True
        if hasattr(options, 'nopoison') and options.nopoison:
            self.nopoison = True
        if hasattr(options, 'quiet') and options.quiet:
            self.quiet_mode = True
        if hasattr(options, 'force_policy') and options.force_policy:
            self.build_policy = 'all'
        if hasattr(options, 'min_age') and options.min_age:
            try:
                self.min_age = time.time() - parse_relative_time(options.min_age)
            except ValueError:
                raise FatalError(_('Failed to parse \'min_age\' relative '
                                   'time'))

    def __setattr__(self, k, v):
        '''Override __setattr__ for additional checks on some options.'''
        if k == 'quiet_mode' and v:
            try:
                import curses
                logging.getLogger().setLevel(logging.ERROR)
            except ImportError:
                logging.warning(
                        _('quiet mode has been disabled because the Python curses module is missing.'))
                v = False

        self.__dict__[k] = v

