# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008  Frederic Peters
#
#   rdepends.py: show reverse-dependencies of a module
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

import jhbuild.moduleset
from jhbuild.commands import Command, register_command
from jhbuild.errors import FatalError
from jhbuild.utils import uprint, N_, _


class cmd_rdepends(Command):
    doc = N_('Display reverse-dependencies of a module')

    name = 'rdepends'
    usage_args = N_('[ module ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('--dependencies',
                        action='store_true', dest='dependencies', default=False,
                        help=_('display dependency path next to modules')),
            make_option('--direct',
                        action='store_true', dest='direct', default=False,
                        help=_('limit display to modules directly depending on given module'))
            ])

    def run(self, config, options, args, help=None):
        module_set = jhbuild.moduleset.load(config)

        if not args:
            self.parser.error(_('This command requires a module parameter.'))

        try:
            modname = module_set.get_module(args[0], ignore_case = True).name
        except KeyError:
            raise FatalError(_("A module called '%s' could not be found.") % args[0])

        # get all modules but those that are a dependency of modname
        dependencies_list = [x.name for x in module_set.get_module_list([modname])]
        if modname in dependencies_list:
            dependencies_list.remove(modname)
        modules = module_set.get_full_module_list(skip=dependencies_list)
        modules = modules[[x.name for x in modules].index(modname)+1:]

        # iterate over remaining modules, and print those with modname as dep;
        # this is totally inefficient as a complete dependency list is computed
        # for each module.
        seen_modules = []
        for module in modules:
            if options.direct:
                if modname in module.dependencies:
                    uprint(module.name)
            else:
                module_list = module_set.get_module_list([module.name])
                if modname in [x.name for x in module_list]:
                    seen_modules.append(module.name)
                    deps = ''
                    if options.dependencies:
                        dependencies = [x for x in module.dependencies if x in seen_modules]
                        if dependencies:
                            deps = '[' + ','.join(dependencies) + ']'
                    uprint(module.name, deps)

register_command(cmd_rdepends)
