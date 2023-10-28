# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2004  James Henstridge
# Copyright (C) 2008  Andy Wingo
#
#   snapshot.py: output a moduleset corresponding to the exact versions
#                that are checked out
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
from jhbuild.commands import Command, register_command
from jhbuild.utils import N_, bprint
from jhbuild.utils.sxml import sxml, sxml_to_string


class cmd_snapshot(Command):
    doc = N_('Print out a moduleset for the exact versions that are checked out')
    name = 'snapshot'
    
    def __init__(self):
        Command.__init__(self)

    def run(self, config, options, args, help=None):
        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                                                 config.skip)
        meta = [m for m in module_list if m.type == 'meta']
        checked_out_mods = [m for m in module_list
                            if getattr(m, 'branch', None) and m.branch.tree_id()]
        checked_out_repos = []

        for mod in checked_out_mods:
            if mod.branch.repository not in checked_out_repos:
                checked_out_repos.append(mod.branch.repository)

        x = ([sxml.moduleset]
             + [r.to_sxml() for r in checked_out_repos]
             + [m.to_sxml() for m in checked_out_mods]
             + [m.to_sxml() for m in meta])

        bprint(b'<?xml version="1.0"?>\n')
        bprint(sxml_to_string(x).encode("utf-8") + b'\n')

register_command(cmd_snapshot)
