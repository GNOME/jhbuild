# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2004  James Henstridge
#
#   checkbranches.py: check GNOME module sets for missing branches definition
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
from jhbuild.utils.cmds import get_output
from jhbuild.utils import uprint, N_, _
from jhbuild.errors import CommandError

class cmd_checkbranches(Command):
    doc = N_('Check modules in GNOME Git repository have the correct branch definition')
    name = 'checkbranches'
    
    def __init__(self):
        Command.__init__(self, [
            make_option('-b', '--branch', metavar = 'BRANCH',
                    action = 'store', dest = 'branch', default = None)])

    def run(self, config, options, args, help=None):
        if options.branch:
            branch = options.branch
        else:
            if type(config.moduleset) is list:
                branch = config.moduleset[0].replace('.', '-')
            else:
                branch = config.moduleset.replace('.', '-')
            for prefix in ('gnome-suites-core-deps', 'gnome-suites-core',
                           'gnome-suites-', 'gnome-apps-'):
                branch = branch.replace(prefix, 'gnome-')

        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules)
        for mod in module_list:
            if mod.type in ('meta', 'tarball'):
                continue
            if not mod.branch or not mod.branch.repository.__class__.__name__ == 'GitRepository':
                continue
            if 'git.gnome.org' not in mod.branch.repository.href:
                continue
            if mod.branch.branch:
                # there is already a branch defined
                continue

            try:
                if get_output(['git', 'ls-remote',
                        'https://git.gnome.org/browse/%s' % mod.name,
                        'refs/heads/%s' % branch]):
                    uprint(_('%(module)s is missing branch definition for %(branch)s') % {'module': mod.name, 'branch': branch})
            except CommandError:
                pass


register_command(cmd_checkbranches)
