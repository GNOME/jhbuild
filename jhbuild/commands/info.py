# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
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

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import FatalError
from jhbuild.commands import Command, register_command
from jhbuild.modtypes import MetaModule
from jhbuild.modtypes.autotools import AutogenModule
from jhbuild.modtypes.mozillamodule import MozillaModule
from jhbuild.versioncontrol.cvs import CVSBranch
from jhbuild.versioncontrol.svn import SubversionBranch
from jhbuild.versioncontrol.arch import ArchBranch
from jhbuild.versioncontrol.darcs import DarcsBranch
from jhbuild.versioncontrol.git import GitBranch
from jhbuild.versioncontrol.tarball import TarballBranch


class cmd_info(Command):
    """Display information about one or more modules"""

    name = 'info'
    usage_args = '[ modules ... ]'

    def run(self, config, options, args):
        packagedb = jhbuild.frontends.get_buildscript(config, []).packagedb
        module_set = jhbuild.moduleset.load(config)

        if not args:
            self.parser.error('This command requires a module parameter.')

        for modname in args:
            try:
                module = module_set.modules[modname]
            except KeyError:
                raise FatalError('unknown module %s' % modname)
            self.show_info(module, packagedb, module_set)

    def show_info(self, module, packagedb, module_set):
        installdate = packagedb.installdate(module.name, module.get_revision() or '')

        print 'Name:', module.name
        print 'Module Set:', module.moduleset_name
        print 'Type:', module.type

        if installdate is not None:
            print 'Install-date:', time.strftime('%Y-%m-%d %H:%M:%S',
                                                 time.localtime(installdate))
        else:
            print 'Install-date:', 'not installed'

        if isinstance(module, MozillaModule):
            if module.projects:
                print 'Moz-Projects:', ', '.join(module.projects)

        if isinstance(module, MetaModule):
            pass
        elif isinstance(module.branch, CVSBranch):
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
        elif isinstance(module.branch, GitBranch):
            print 'Git-Module:', module.branch.module
        elif isinstance(module.branch, TarballBranch):
            print 'URL:', module.branch.module
            print 'Version:', module.branch.version
        try:
            tree_id = module.branch.tree_id()
            print 'Tree-ID:', tree_id
        except (NotImplementedError, AttributeError):
            pass

        # dependencies
        if module.dependencies:
            print 'Requires:', ', '.join(module.dependencies)
        requiredby = [ mod.name for mod in module_set.modules.values()
                       if module.name in mod.dependencies ]
        if requiredby:
            print 'Required-by:', ', '.join(requiredby)
        if module.suggests:
            print 'Suggests:', ', '.join(module.suggests)
        if module.after:
            print 'After:', ', '.join(module.after)
        before = [ mod.name for mod in module_set.modules.values()
                   if module.name in mod.after ]
        if before:
            print 'Before:', ', '.join(before)

        print

register_command(cmd_info)
