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
        pkgs = systempackages.get_system_packages()
        module_set = jhbuild.moduleset.load(config)

        to_install = []

        for module in module_set.get_module_list(args or config.modules):
            if pkgs.satisfiable(module.name, module) and not pkgs.satisfied(module.name, module):
                to_install.append(pkgs.get_pkgname(module.name))

        if options.dryrun:
            print "Will install: %s" % " ".join(to_install)
        else:
            pkgs.install(to_install)

register_command(cmd_builddeps)

