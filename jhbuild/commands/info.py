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
from jhbuild.modtypes.base import MetaModule, CVSModule
from jhbuild.modtypes.tarball import Tarball
from jhbuild.modtypes.svnmodule import SVNModule

def do_info(config, args):
    opts, args = getopt.getopt(args, '', []) # no special args
    packagedb = jhbuild.frontends.get_buildscript(config, []).packagedb
    module_set = jhbuild.moduleset.load(config)

    for modname in args:
        try:
            module = module_set.modules[modname]
        except KeyError:
            raise FatalError('unknown module %s' % modname)
        if isinstance(module, CVSModule):
            installdate = packagedb.installdate(module.name,
                                                module.revision or '')
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

        if isinstance(module, CVSModule):
            print 'CVS-Root:', module.cvsroot
            print 'CVS-Module:', module.cvsmodule
            if module.revision:
                print 'CVS-Revision:', module.revision
        elif isinstance(module, SVNModule):
            print 'Subversion-Repository:', module.svnroot
            print 'Subversion-Module:', module.svnmodule
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
