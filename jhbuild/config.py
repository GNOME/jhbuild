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
import traceback
import sys

from jhbuild.errors import UsageError, FatalError, CommandError
from jhbuild.utils.cmds import get_output

__all__ = [ 'Config' ]

_defaults_file = os.path.join(os.path.dirname(__file__), 'defaults.jhbuildrc')
_default_jhbuildrc = os.path.join(os.environ['HOME'], '.jhbuildrc')

_known_keys = [ 'moduleset', 'modules', 'skip', 'tags', 'prefix',
                'checkoutroot', 'buildroot', 'autogenargs', 'makeargs',
                'repos', 'branches', 'noxvfb', 'xvfbargs',
                'builddir_pattern', 'module_autogenargs', 'module_makeargs',
                'interact', 'buildscript', 'nonetwork',
                'alwaysautogen', 'nobuild', 'makeclean', 'makecheck', 'module_makecheck',
                'use_lib64', 'tinderbox_outputdir', 'sticky_date',
                'tarballdir', 'pretty_print', 'svn_program', 'makedist',
                'makedistcheck', 'nonotify', 'cvs_program',
                'checkout_mode', 'copy_dir', 'module_checkout_mode',
                'build_policy', 'trycheckout', 'min_time',
                'nopoison', 'forcecheck', 'makecheck_advisory',
                'quiet_mode', 'progress_bar', 'module_extra_env']

env_prepends = {}
def prependpath(envvar, path):
    env_prepends.setdefault(envvar, []).append(path)

def addpath(envvar, path):
    '''Adds a path to an environment variable.'''
    # special case ACLOCAL_FLAGS
    if envvar in [ 'ACLOCAL_FLAGS' ]:
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
    else:
        envval = os.environ.get(envvar, path)
        parts = envval.split(':')
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
        envval = ':'.join(parts)

    os.environ[envvar] = envval

class Config:
    def __init__(self, filename=_default_jhbuildrc):
        config = {
            '__file__': _defaults_file,
            'addpath':  addpath,
            'prependpath':  prependpath
            }
        env_prepends.clear()
        try:
            execfile(_defaults_file, config)
        except:
            traceback.print_exc()
            raise FatalError(_('could not load config defaults'))
        config['__file__'] = filename
        try:
            execfile(filename, config)
        except Exception:
            traceback.print_exc()
            raise FatalError(_('could not load config file'))

        # backward compatibility, from the days when jhbuild only
        # supported Gnome.org CVS.
        if config.has_key('cvsroot'):
            config['cvsroots']['gnome.org'] = config['cvsroot']
        if config.has_key('cvsroots'):
            config['repos'].update(config['cvsroots'])
        if config.has_key('svnroots'):
            config['repos'].update(config['svnroots'])

        # environment variables
        if config.has_key('cflags') and config['cflags']:
            os.environ['CFLAGS'] = config['cflags']
        if config.has_key('installprog') and config['installprog']:
            os.environ['INSTALL'] = config['installprog']

        # copy known config keys to attributes on the instance
        for name in _known_keys:
            setattr(self, name, config[name])

        # default tarballdir to checkoutroot
        if not self.tarballdir: self.tarballdir = self.checkoutroot

        # check possible checkout_mode values
        possible_checkout_modes = ('update', 'clobber', 'export', 'copy')
        if self.checkout_mode not in possible_checkout_modes:
            raise FatalError(_('invalid checkout mode'))
        for module, checkout_mode in self.module_checkout_mode.items():
            if checkout_mode not in possible_checkout_modes:
                raise FatalError(_('invalid checkout mode (module: %s)') % module)

        self.setup_env()

    def setup_env(self):
        '''set environment variables for using prefix'''

        if not os.path.exists(self.prefix):
            try:
                os.makedirs(self.prefix)
            except:
                raise FatalError(_("Can't create %s directory") % self.prefix)

        # LD_LIBRARY_PATH
        if self.use_lib64:
            libdir = os.path.join(self.prefix, 'lib64')
        else:
            libdir = os.path.join(self.prefix, 'lib')
        addpath('LD_LIBRARY_PATH', libdir)

        # LDFLAGS and C_INCLUDE_PATH are required for autoconf configure
        # scripts to find modules that do not use pkg-config (such as guile
        # looking for gmp, or wireless-tools for NetworkManager)
        # (see bug #377724 and bug #545018)
        os.environ['LDFLAGS'] = ('-L%s ' % libdir) + os.environ.get('LDFLAGS', '')
        includedir = os.path.join(self.prefix, 'include')
        addpath('C_INCLUDE_PATH', includedir)

        # On Mac OS X, we use DYLD_FALLBACK_LIBRARY_PATH
        addpath('DYLD_FALLBACK_LIBRARY_PATH', libdir)

        # PATH
        bindir = os.path.join(self.prefix, 'bin')
        addpath('PATH', bindir)

        # MANPATH
        manpathdir = os.path.join(self.prefix, 'share', 'man')
        addpath('MANPATH', manpathdir)

        # PKG_CONFIG_PATH
        pkgconfigdatadir = os.path.join(self.prefix, 'share', 'pkgconfig')
        pkgconfigdir = os.path.join(libdir, 'pkgconfig')
        addpath('PKG_CONFIG_PATH', pkgconfigdatadir)
        addpath('PKG_CONFIG_PATH', pkgconfigdir)

        # XDG_DATA_DIRS
        xdgdatadir = os.path.join(self.prefix, 'share')
        addpath('XDG_DATA_DIRS', xdgdatadir)

        # XDG_CONFIG_DIRS
        xdgconfigdir = os.path.join(self.prefix, 'etc', 'xdg')
        addpath('XDG_CONFIG_DIRS', xdgconfigdir)

        # ACLOCAL_FLAGS
        aclocaldir = os.path.join(self.prefix, 'share', 'aclocal')
        if not os.path.exists(aclocaldir):
            try:
                os.makedirs(aclocaldir)
            except:
                raise FatalError(_("Can't create %s directory") % aclocaldir)
        addpath('ACLOCAL_FLAGS', aclocaldir)

        # PERL5LIB
        perl5lib = os.path.join(self.prefix, 'lib', 'perl5')
        addpath('PERL5LIB', perl5lib)

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
        
        if self.use_lib64:
            pythonpath = os.path.join(self.prefix, 'lib64', pythonversion, 'site-packages')
            addpath('PYTHONPATH', pythonpath)

        pythonpath = os.path.join(self.prefix, 'lib', pythonversion, 'site-packages')
        addpath('PYTHONPATH', pythonpath)

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

