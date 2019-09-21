# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2004  James Henstridge
#
#   checkmodulesets.py: check GNOME module sets for missing branches definition
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

import logging

import jhbuild.moduleset
from jhbuild.utils import N_, _
from jhbuild.commands import Command, register_command

class cmd_checkmodulesets(Command):
    doc = N_('Check if modules in JHBuild have the correct definition')
    name = 'checkmodulesets'

    def run(self, config, options, args, help=None):
        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_full_module_list(
            warn_about_circular_dependencies = True)
        for mod in module_list:
            if mod.type in ('meta', 'tarball'):
                continue

            try:
                if not mod.branch.exists():
                    logging.error(_('%(module)s is unreachable (%(href)s)') % {
                            'module': mod.name, 'href': mod.branch.module})
            except NotImplementedError:
                logging.warning((_('Cannot check %(module)s (%(href)s)') % {
                            'module': mod.name, 'href': mod.branch.module}))

register_command(cmd_checkmodulesets)
