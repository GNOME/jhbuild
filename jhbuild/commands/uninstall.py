# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   base.py: the most common jhbuild commands
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

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import UsageError, FatalError
from jhbuild.commands import Command, register_command


class cmd_uninstall(Command):
    doc = _('Uninstall all modules')

    name = 'uninstall'
    usage_args = '[ options ... ] [ modules ... ]'

    def run(self, config, options, args):
        module_set = jhbuild.moduleset.load(config)
        module_list = []

        # remove modules that are not marked as installed
        packagedb = jhbuild.frontends.get_buildscript(config, []).packagedb
        for module in module_set.get_module_list(args or config.modules,
                config.skip, tags=config.tags, ignore_suggests=config.ignore_suggests):
            if packagedb.check(module.name):
                module_list.append(module)

        config.build_policy = 'all'
        config.build_targets = ['uninstall']

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_uninstall)
