# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2009  Codethink Ltd.
#
#   builddeps.py: satisfy build dependencies from system packages
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
#
#  Authors:
#    John Carr <john.carr@unrouted.co.uk>

from optparse import make_option
import logging

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import UsageError, FatalError, CommandError
from jhbuild.commands import Command, register_command

from jhbuild.utils import systempackages

class cmd_builddeps(Command):
    doc = N_('Get build dependencies for modules')

    name = 'builddeps'
    usage_args = N_('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('--dryrun',
                        action='store_true', dest='dryrun', default=False,
                        help=_('Just show which packages would be installed')),
            ])

    def run(self, config, options, args):
        if not config.reuse_system_packages:
            logging.error(_("Command not available when reuse_system_packages is False. Check your jhbuildrc."))
            return

        asked_modules = (args or config.modules)[:]

        pkgs = systempackages.get_system_packages(config)
        module_set = jhbuild.moduleset.load(config)

        to_install = []

        all_modules = module_set.get_module_list(asked_modules)

        visited = asked_modules[:]
        for modname in visited:
            module = module_set.get_module(modname)
            min_version = module.get_minimum_version(all_modules)

            if modname in asked_modules or (pkgs.satisfiable(module, min_version) and not pkgs.satisfied(module, min_version)):
                to_install.append(pkgs.get_pkgname(module.name))
            else:
                for depmod in module.dependencies:
                    if depmod not in visited:
                        visited.append(depmod)
                if not config.ignore_suggests:
                    for depmod in module.suggests:
                        if depmod not in visited:
                            visited.append(depmod)

        if options.dryrun:
            print "Will install: %s" % " ".join(to_install)
        else:
            pkgs.install(to_install)

register_command(cmd_builddeps)

