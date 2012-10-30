# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2011 Colin Walters <walters@verbum.org>
#
#   sysdeps.py: Install system dependencies
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

from optparse import make_option
import logging
import os.path

import jhbuild.moduleset
from jhbuild.errors import FatalError
from jhbuild.commands import Command, register_command
from jhbuild.commands.base import cmd_build
from jhbuild.utils.systeminstall import SystemInstall
from jhbuild.utils import cmds

class cmd_sysdeps(cmd_build):
    doc = N_('Check and install tarball dependencies using system packages')

    name = 'sysdeps'

    def __init__(self):
        Command.__init__(self, [
            make_option('--install',
                        action='store_true', default = False,
                        help=_('Install pkg-config modules via system'))])

    def run(self, config, options, args, help=None):

        def fmt_details(pkg_config, req_version, installed_version):
            fmt_list = []
            if pkg_config:
                fmt_list.append(pkg_config)
            if req_version:
                fmt_list.append(_('required=%s') % req_version)
            if installed_version and installed_version != 'unknown':
                fmt_list.append(_('installed=%s') % installed_version)
            # Translators: This is used to separate items of package metadata
            fmt_str = _(', ').join(fmt_list)
            if fmt_str:
                return _('(%s)') % fmt_str
            else:
                return ''

        config.set_from_cmdline_options(options)

        module_set = jhbuild.moduleset.load(config)
        modules = args or config.modules
        module_list = module_set.get_full_module_list(modules, config.skip)
        module_state = module_set.get_module_state(module_list)

        have_new_enough = False
        have_too_old = False

        print _('System installed packages which are new enough:')
        for module,(req_version, installed_version, new_enough, systemmodule) in module_state.iteritems():
            if (installed_version is not None) and new_enough and (config.partial_build or systemmodule):
                have_new_enough = True
                print ('    %s %s' % (module.name,
                                      fmt_details(module.pkg_config,
                                                  req_version,
                                                  installed_version)))
        if not have_new_enough:
            print _('  (none)')

        print _('Required packages:')
        print _('  System installed packages which are too old:')
        for module, (req_version, installed_version, new_enough, systemmodule) in module_state.iteritems():
            if (installed_version is not None) and (not new_enough) and systemmodule:
                have_too_old = True
                print ('    %s %s' % (module.name,
                                      fmt_details(module.pkg_config,
                                                  req_version,
                                                  installed_version)))
        if not have_too_old:
            print _('    (none)')

        print _('  No matching system package installed:')
        uninstalled_pkgconfigs = []
        uninstalled_filenames = []
        for module, (req_version, installed_version, new_enough, systemmodule) in module_state.iteritems():
            if installed_version is None and (not new_enough) and systemmodule:
                print ('    %s %s' % (module.name,
                                      fmt_details(module.pkg_config,
                                                  req_version,
                                                  installed_version)))
                if module.pkg_config is not None:
                    uninstalled_pkgconfigs.append((module.name,
                                                   # remove .pc
                                                   module.pkg_config[:-3]))
                elif module.systemdependencies is not None:
                    for dep_type, value in module.systemdependencies:
                        if dep_type.lower() == 'path':
                            uninstalled_filenames.append(
                                (module.name,
                                 os.path.join(config.system_prefix, 'bin',
                                              value),))
                        elif dep_type.lower() == 'c_include':
                            uninstalled_filenames.append(
                                (module.name,
                                 os.path.join(config.system_prefix, 'include',
                                              value),))
        if len(uninstalled_pkgconfigs) + len(uninstalled_filenames) == 0:
            print _('    (none)')

        have_too_old = False

        if config.partial_build:
            print _('Optional packages: (JHBuild will build the missing packages)')
            print _('  System installed packages which are too old:')
            for module, (req_version, installed_version, new_enough, systemmodule) in module_state.iteritems():
                if (installed_version is not None) and (not new_enough) and (not systemmodule):
                    have_too_old = True
                    print ('    %s %s' % (module.name,
                                          fmt_details(module.pkg_config,
                                                      req_version,
                                                      installed_version)))
            if not have_too_old:
                print _('    (none)')

            print _('  No matching system package installed:')
            for module,(req_version, installed_version, new_enough, systemmodule) in module_state.iteritems():
                if installed_version is None and (not new_enough) and (not systemmodule):
                    print ('    %s %s' % (module.name,
                                          fmt_details(module.pkg_config,
                                                      req_version,
                                                      installed_version)))
                    if module.pkg_config is not None:
                        uninstalled_pkgconfigs.append((module.name,
                                                       # remove .pc
                                                       module.pkg_config[:-3]))

            if len(uninstalled_pkgconfigs) == 0:
                print _('  (none)')

        if options.install:
            installer = SystemInstall.find_best()
            if installer is None:
                # FIXME: This should be implemented per Colin's design:
                # https://bugzilla.gnome.org/show_bug.cgi?id=682104#c3
                if cmds.has_command('apt-get'):
                    raise FatalError(_("%(cmd)s is required to install "
                                       "packages on this system. Please "
                                       "install %(cmd)s.")
                                     % {'cmd' : 'apt-file'})

                raise FatalError(_("Don't know how to install packages on this system"))

            if (len(uninstalled_pkgconfigs) +
                len(uninstalled_filenames)) == 0:
                logging.info(_("No uninstalled system dependencies to install for modules: %r" % (modules, )))
            else:
                logging.info(_("Installing dependencies on system: %s" % \
                               ' '.join([pkg[0] for pkg in
                                         uninstalled_pkgconfigs +
                                         uninstalled_filenames])))
                installer.install(uninstalled_pkgconfigs,
                                  uninstalled_filenames)

register_command(cmd_sysdeps)
