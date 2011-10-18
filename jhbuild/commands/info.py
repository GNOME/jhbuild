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
from jhbuild.versioncontrol.cvs import CVSBranch
from jhbuild.versioncontrol.svn import SubversionBranch
from jhbuild.versioncontrol.darcs import DarcsBranch
from jhbuild.versioncontrol.git import GitBranch
from jhbuild.versioncontrol.tarball import TarballBranch


class cmd_info(Command):
    doc = N_('Display information about one or more modules')

    name = 'info'
    usage_args = N_('[ modules ... ]')


    def run(self, config, options, args, help=None):
        module_set = jhbuild.moduleset.load(config)
        packagedb = module_set.packagedb

        if args:
            for modname in args:
                try:
                    module = module_set.get_module(modname, ignore_case = True)
                except KeyError:
                    raise FatalError(_('unknown module %s') % modname)
                self.show_info(module, packagedb, module_set)
        else:
            for module in module_set.modules.values():
                self.show_info(module, packagedb, module_set)

    def show_info(self, module, packagedb, module_set):
        package_entry = packagedb.get(module.name)

        uprint(_('Name:'), module.name)
        uprint(_('Module Set:'), module.moduleset_name)
        uprint(_('Type:'), module.type)

        if package_entry is not None:
            uprint(_('Install version:'), package_entry.version)
            uprint(_('Install date:'), time.strftime('%Y-%m-%d %H:%M:%S',
                                                     time.localtime(packagedb.installdate(module.name))))
        else:
            uprint(_('Install version:'), _('not installed'))
            uprint(_('Install date:'), _('not installed'))

        if isinstance(module, MetaModule):
            pass
        elif isinstance(module.branch, CVSBranch):
            uprint(_('CVS Root:'), module.branch.repository.cvsroot)
            uprint(_('CVS Module:'), module.branch.module)
            if module.branch.revision:
                uprint(_('CVS Revision:'), module.branch.revision)
        elif isinstance(module.branch, SubversionBranch):
            uprint(_('Subversion Module:'), module.branch.module)
        elif isinstance(module.branch, DarcsBranch):
            uprint(_('Darcs Archive:'), module.branch.module)
        elif isinstance(module.branch, GitBranch):
            uprint(_('Git Module:'), module.branch.module)
            if module.branch.unmirrored_module:
                uprint(_('Git Origin Module:'), module.branch.unmirrored_module)
            git_branch = module.branch.branch
            if not git_branch:
                git_branch = 'master'
            uprint(_('Git Branch:'), git_branch)
            if module.branch.tag:
                uprint(_('Git Tag:'), module.branch.tag)
        elif isinstance(module.branch, TarballBranch):
            uprint(_('URL:'), module.branch.module)
            uprint(_('Version:'), module.branch.version)
        try:
            tree_id = module.branch.tree_id()
            uprint(_('Tree-ID:'), tree_id)
        except (NotImplementedError, AttributeError):
            pass
        try:
            source_dir = module.branch.srcdir
            uprint(_('Sourcedir:'), source_dir)
        except (NotImplementedError, AttributeError):
            pass

        # dependencies
        if module.dependencies:
            uprint(_('Requires:'), ', '.join(module.dependencies))
        requiredby = [ mod.name for mod in module_set.modules.values()
                       if module.name in mod.dependencies ]
        if requiredby:
            uprint(_('Required by:'), ', '.join(requiredby))
        if module.suggests:
            uprint(_('Suggests:'), ', '.join(module.suggests))
        if module.after:
            uprint(_('After:'), ', '.join(module.after))
        before = [ mod.name for mod in module_set.modules.values()
                   if module.name in mod.after ]
        if before:
            uprint(_('Before:'), ', '.join(before))

        print

register_command(cmd_info)
