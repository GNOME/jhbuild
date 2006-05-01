# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   info.py: show information about a module
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

import sys
import time
import getopt

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import FatalError
from jhbuild.commands.base import register_command
from jhbuild.modtypes.base import AutogenModule, MetaModule
from jhbuild.modtypes.tarball import Tarball
from jhbuild.versioncontrol.cvs import CVSBranch
from jhbuild.versioncontrol.svn import SubversionBranch
from jhbuild.versioncontrol.arch import ArchBranch
from jhbuild.versioncontrol.darcs import DarcsBranch

def do_info(config, args):
    opts, args = getopt.getopt(args, '', []) # no special args
    packagedb = jhbuild.frontends.get_buildscript(config, []).packagedb
    module_set = jhbuild.moduleset.load(config)

    for modname in args:
        try:
            module = module_set.modules[modname]
        except KeyError:
            raise FatalError('unknown module %s' % modname)
        if isinstance(module, AutogenModule):
            installdate = packagedb.installdate(module.name,
                                                module.branch.branchname or '')
        elif isinstance(module, Tarball):
            installdate = packagedb.installdate(module.name,
                                                module.version or '')
        else:
            installdate = packagedb.installdate(module.name)

        print 'Name:', modname
        print 'Type:', module.type

        if installdate is not None:
            print 'Install-date:', time.strftime('%Y-%m-%d %H:%M:%S',
                                                 time.localtime(installdate))
        else:
            print 'Install-date:', 'not installed'

        if isinstance(module, AutogenModule):
            if isinstance(module.branch, CVSBranch):
                print 'CVS-Root:', module.branch.repository.cvsroot
                print 'CVS-Module:', module.branch.module
                if module.branch.revision:
                    print 'CVS-Revision:', module.branch.revision
            elif isinstance(module.branch, SubversionBranch):
                print 'Subversion-Module:', module.branch.module
            elif isinstance(module.branch, ArchBranch):
                print 'Arch-Version:', module.branch.module
            elif isinstance(module.branch, DarcsBranch):
                print 'Darcs-Archive:', module.branch.module
        elif isinstance(module, Tarball):
            print 'URL:', module.source_url
            print 'Version:', module.version

        # dependencies
        if module.dependencies:
            print 'Requires:', ', '.join(module.dependencies)
        if module.suggests:
            print 'Suggests:', ', '.join(module.suggests)
        requiredby = [ mod.name for mod in module_set.modules.values()
                       if modname in mod.dependencies ]
        if requiredby:
            print 'Required-by:', ', '.join(requiredby)
        suggestedby = [ mod.name for mod in module_set.modules.values()
                       if modname in mod.suggests ]
        if suggestedby:
            print 'Suggested-by:', ', '.join(suggestedby)

        print

register_command('info', do_info)
