# jhbuild - a tool to ease building collections of source packages
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

from optparse import make_option

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import FatalError
from jhbuild.utils import _
from jhbuild.commands import Command, register_command


class cmd_clean(Command):
    doc = _('Clean all modules')

    name = 'clean'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help=_('treat the given modules as up to date')),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help=_('start building at the given module')),
            ])

    def run(self, config, options, args, help=None):
        for item in options.skip:
            config.skip += item.split(',')

        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules, config.skip)
        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError(_('%s not in module list') % options.startat)

        # remove modules that are not marked as installed
        packagedb = module_set.packagedb
        for module in module_list[:]:
            if not packagedb.check(module.name):
                module_list.remove(module)

        config.nopoison = True

        build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
        return build.build(phases=['clean'])

register_command(cmd_clean)
