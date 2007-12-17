# jhbuild - a build script for GNOME 1.x and 2.x
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



import urllib2
from optparse import make_option

import jhbuild.moduleset
from jhbuild.commands import Command, register_command

class cmd_checkbranches(Command):
    """Check modules in GNOME svn have the correct branch definition"""
    name = 'checkbranches'
    
    def __init__(self):
        Command.__init__(self, [
            make_option('-b', '--branch', metavar = 'BRANCH',
                    action = 'store', dest = 'branch', default = None)])

    def run(self, config, options, args):
        if options.branch:
            branch = options.branch
        else:
            if type(config.moduleset) is list:
                branch = config.moduleset[0].replace('.', '-')
            else:
                branch = config.moduleset.replace('.', '-')

        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                                                 config.skip)
        for mod in module_list:
            if mod.type in ('meta', 'tarball'):
                continue
            if not mod.branch or not mod.branch.repository.__class__.__name__ == 'SubversionRepository':
                continue
            if not 'svn.gnome.org' in mod.branch.repository.href:
                continue
            rev = mod.branch.revision
            if rev:
                continue

            url = 'http://svn.gnome.org/viewcvs/%s/branches/%s' % (mod.name, branch)
            try:
                st = urllib2.urlopen(url).read()
            except urllib2.URLError:
                pass
            else:
                print mod.name, 'is missing branch definition for', branch


register_command(cmd_checkbranches)
