# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007-2008  Frederic Peters
# Copyright (C) 2014 Canonical Limited
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
import os.path
import re
import sys
import traceback
import time
import types
import logging

from jhbuild.environment import setup_env, setup_env_defaults, addpath
from jhbuild.errors import FatalError
from jhbuild.utils import execfile, sysid, _

if sys.platform.startswith('win'):
    # For munging paths for MSYS's benefit
    import jhbuild.utils.subprocess_win32
    jhbuild.utils.subprocess_win32

__all__ = [ 'Config' ]

_defaults_file = os.path.join(os.path.dirname(__file__), 'defaults.jhbuildrc')

_known_keys = [ 'moduleset', 'modules', 'skip', 'tags', 'prefix',
                'partial_build', 'checkoutroot', 'buildroot', 'top_builddir',
                'autogenargs', 'makeargs', 'nice_build', 'jobs',
                'installprog', 'repos', 'branches', 'noxvfb', 'xvfbargs',
                'builddir_pattern', 'module_autogenargs', 'module_makeargs',
                'module_ninjaargs', 'ninjaargs', 'interact', 'buildscript',
                'nonetwork', 'nobuild', 'alwaysautogen', 'noinstall',
                'makeclean', 'makedistclean', 'makecheck', 'module_makecheck',
                'system_libdirs', 'tinderbox_outputdir', 'sticky_date', 'tarballdir',
                'pretty_print', 'svn_program', 'makedist', 'makedistcheck',
                'nonotify', 'notrayicon', 'cvs_program', 'checkout_mode',
                'copy_dir', 'export_dir', 'module_checkout_mode', 'build_policy',
                'trycheckout', 'min_age', 'nopoison', 'module_nopoison',
                'forcecheck', 'makecheck_advisory', 'quiet_mode',
                'progress_bar', 'module_extra_env',
                'use_local_modulesets', 'ignore_suggests', 'modulesets_dir',
                'mirror_policy', 'module_mirror_policy', 'dvcs_mirror_dir',
                'shallow_clone', 'build_targets', 'cmakeargs', 'module_cmakeargs',
                'mesonargs', 'module_mesonargs',
                'print_command_pattern', 'static_analyzer',
                'module_static_analyzer', 'static_analyzer_template',
                'static_analyzer_outputdir', 'check_sysdeps', 'system_prefix',
                'help_website', 'conditions', 'extra_prefixes',
                'disable_Werror', 'xdg_cache_home', 'exit_on_error'
              ]

env_prepends = {}
def prependpath(envvar, path):
    env_prepends.setdefault(envvar, []).append(path)

def parse_relative_time(s):
    m = re.match(r'(\d+) *([smhdw])', s.lower())
    if m:
        coeffs = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w':7*86400}
        return float(m.group(1)) * coeffs[m.group(2)]
    else:
        raise ValueError

def modify_conditions(conditions, conditions_modifiers):
    for flag in conditions_modifiers:
        for mod in flag.split(','):
            if mod.startswith('+'):
                conditions.add(mod[1:])
            elif mod.startswith('-'):
                conditions.discard(mod[1:])
            else:
                raise FatalError(_("Invalid condition set modifier: '%s'.  Must start with '+' or '-'.") % mod)

class Config:
    _orig_environ = None

    def __init__(self, filename, conditions_modifiers):
        self._config = {
            '__file__': _defaults_file,
            'addpath':  addpath,
            'prependpath':  prependpath,
            'include': self.include,
            }

        if not self._orig_environ:
            self.__dict__['_orig_environ'] = os.environ.copy()
        os.environ['UNMANGLED_LD_LIBRARY_PATH'] = os.environ.get('LD_LIBRARY_PATH', '')
        os.environ['UNMANGLED_PATH'] = os.environ.get('PATH', '')

        env_prepends.clear()
        try:
            execfile(_defaults_file, self._config)
        except Exception:
            traceback.print_exc()
            raise FatalError(_('could not load config defaults'))

        xdg_config_dirs = os.environ.get('XDG_CONFIG_DIRS', '/etc/xdg').split(':')
        for xdg_config_dir in xdg_config_dirs:
            try:
                config_path = os.path.join(xdg_config_dir, 'jhbuildrc')
                execfile(config_path, self._config)
            except FileNotFoundError:
                pass
            except Exception:
                traceback.print_exc()
                raise FatalError(_('could not load system config %s' % config_path))

        old_config = os.path.join(os.path.expanduser('~'), '.jhbuildrc')
        new_config = os.path.join(os.environ.get('XDG_CONFIG_HOME',
            os.path.join(os.path.expanduser('~'), '.config')),
            'jhbuildrc')

        if filename:
            if not os.path.exists(filename):
                raise FatalError(_('could not load config file, %s is missing') % filename)
        else:
            if os.path.isfile(old_config) \
                    and not os.path.islink(old_config) \
                    and os.path.isfile(new_config) \
                    and not os.path.islink(new_config):
                raise FatalError(_('The default location of the configuration '
                                   'file has changed. Please move %(old_path)s'
                                   ' to %(new_path)s.' \
                                   % {'old_path': old_config,
                                      'new_path': new_config}))
            if os.path.exists(new_config):
                filename = new_config
            elif os.path.exists(old_config):
                filename = old_config

        if filename:
            self._config['__file__'] = filename
            self.filename = filename
        else:
            self._config['__file__'] = new_config
            self.filename = new_config

        # we might need to redo this process on config reloads, so save these
        self.saved_conditions_modifiers = conditions_modifiers

        # We handle the conditions flags like so:
        #   - get the default set of conditions (determined by the OS)
        #   - modify it with the commandline arguments
        #   - load the config file so that it can make further modifications
        #   - modify it with the commandline arguments again
        #
        # We apply the commandline argument condition modifiers both before
        # and after parsing the configuration so that the jhbuildrc has a
        # chance to inspect the modified set of flags (and conditionally act
        # on it to set new autogenargs, for example) but also so that the
        # condition flags given on the commandline will ultimately override
        # those in jhbuildrc.
        self._config['conditions'] = sysid.get_default_conditions()
        modify_conditions(self._config['conditions'], conditions_modifiers)
        self.load(filename)
        modify_conditions(self.conditions, conditions_modifiers)

        self.create_directories()

        setup_env_defaults(self.system_libdirs)

        for prefix in reversed(self.extra_prefixes):
            setup_env(prefix)
        setup_env(self.prefix)

        self.apply_env_prepends()
        self.update_build_targets()

    def reload(self):
        os.environ = self._orig_environ.copy()
        self.__init__(filename=self._config.get('__file__'), conditions_modifiers=self.saved_conditions_modifiers)
        self.set_from_cmdline_options(options=None)

    def include(self, filename):
        '''Read configuration variables from a file.'''
        try:
            execfile(filename, self._config)
        except Exception:
            traceback.print_exc()
            raise FatalError(_('Could not include config file (%s)') % filename)

    def load(self, filename=None):
        config = self._config
        if filename:
            try:
                execfile(filename, config)
            except Exception as e:
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
        if 'cflags' in config and config['cflags']:
            os.environ['CFLAGS'] = config['cflags']
        if config.get('installprog') and os.path.exists(config['installprog']):
            os.environ['INSTALL'] = config['installprog']

        for path_key in ('checkoutroot', 'buildroot', 'top_builddir',
                         'tinderbox_outputdir', 'tarballdir', 'copy_dir',
                         'modulesets_dir',
                         'dvcs_mirror_dir', 'static_analyzer_outputdir',
                         'prefix'):
            if config.get(path_key):
                config[path_key] = os.path.expanduser(config[path_key])

        # copy known config keys to attributes on the instance
        for name in _known_keys:
            setattr(self, name, config[name])

        # default tarballdir to checkoutroot
        if not self.tarballdir:
            self.tarballdir = self.checkoutroot

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

        if self.buildroot and not os.path.isabs(self.buildroot):
            raise FatalError(_('%s must be an absolute path') % 'buildroot')
        if not os.path.isabs(self.checkoutroot):
            raise FatalError(_('%s must be an absolute path') % 'checkoutroot')
        if not os.path.isabs(self.prefix):
            raise FatalError(_('%s must be an absolute path') % 'prefix')
        if not os.path.isabs(self.tarballdir):
            raise FatalError(_('%s must be an absolute path') % 'tarballdir')
        if (self.tinderbox_outputdir and
                not os.path.isabs(self.tinderbox_outputdir)):
            raise FatalError(_('%s must be an absolute path') %
                             'tinderbox_outputdir')

    def get_original_environment(self):
        return self._orig_environ

    def create_directories(self):
        if not os.path.exists(self.prefix):
            try:
                os.makedirs(self.prefix)
            except EnvironmentError:
                raise FatalError(_('install prefix (%s) can not be created') % self.prefix)

        if not os.path.exists(self.top_builddir):
            try:
                os.makedirs(self.top_builddir)
            except OSError:
                raise FatalError(
                        _('working directory (%s) can not be created') % self.top_builddir)

        if os.path.exists(os.path.join(self.prefix, 'lib64', 'libglib-2.0.so')):
            raise FatalError(_("Your install prefix contains a 'lib64' directory, which is no longer "
                               "supported by jhbuild.  This is likely the result of a previous build with an "
                               "older version of jhbuild or of a broken package.  Please consider removing "
                               "your install and checkout directories and starting fresh."))

    def apply_env_prepends(self):
        ''' handle environment prepends ... '''
        for envvar in env_prepends.keys():
            for path in env_prepends[envvar]:
                addpath(envvar, path)

    def update_build_targets(self):
        # update build targets according to old flags
        if self.makecheck and 'check' not in self.build_targets:
            self.build_targets.insert(0, 'check')
        if self.makeclean and 'clean' not in self.build_targets:
            self.build_targets.insert(0, 'clean')
        if self.makedistclean and 'distclean' not in self.build_targets:
            self.build_targets.insert(0, 'distclean')
        if self.nobuild:
            # nobuild actually means "checkout"
            for phase in ('configure', 'build', 'check', 'clean', 'install'):
                if phase in self.build_targets:
                    self.build_targets.remove(phase)
            self.build_targets.append('checkout')
        if self.makedist and 'dist' not in self.build_targets:
            self.build_targets.append('dist')
        if self.makedistcheck and 'distcheck' not in self.build_targets:
            self.build_targets.append('distcheck')

    def set_from_cmdline_options(self, options=None):
        if options is None:
            options = self.cmdline_options
        else:
            self.cmdline_options = options
        if hasattr(options, 'autogen') and options.autogen:
            self.alwaysautogen = True
        if hasattr(options, 'check') and (
                options.check and 'check' not in self.build_targets):
            self.build_targets.insert(0, 'check')
        if hasattr(options, 'clean') and (
                options.clean and 'clean' not in self.build_targets):
            self.build_targets.insert(0, 'clean')
        if hasattr(options, 'distclean') and (
                options.distclean and 'distclean' not in self.build_targets):
            self.build_targets.insert(0, 'distclean')
        if hasattr(options, 'dist') and (
                options.dist and 'dist' not in self.build_targets):
            self.build_targets.append('dist')
        if hasattr(options, 'distcheck') and (
                options.distcheck and 'distcheck' not in self.build_targets):
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
        if hasattr(options, 'trycheckout') and options.trycheckout:
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
        if (hasattr(options, 'check_sysdeps') and
                options.check_sysdeps is not None):
            self.check_sysdeps = options.check_sysdeps

    def __setattr__(self, k, v):
        '''Override __setattr__ for additional checks on some options.'''
        if k == 'quiet_mode' and v:
            try:
                import curses
                curses
                logging.getLogger().setLevel(logging.ERROR)
            except ImportError:
                logging.warning(
                        _('quiet mode has been disabled because the Python curses module is missing.'))
                v = False

        self.__dict__[k] = v

