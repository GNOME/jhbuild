# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007-2008  Frederic Peters
#
#   mock.py: mock objects for unit testing
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



import jhbuild.frontends.buildscript
import jhbuild.versioncontrol

class Config:
    buildroot = '/tmp/'
    builddir_pattern = '%s'
    use_lib64 = False
    noxvfb = True

    force_policy = False
    build_policy = 'all'

    nonetwork = False
    nobuild = False
    makeclean = False
    makecheck = False
    makedist = False
    makedistcheck = False

    prefix = '/tmp/'

class PackageDB:
    def __init__(self, uptodate = False):
        self.uptodate = uptodate

    def check(self, package, version=None):
        return self.uptodate

    def add(self, package, version):
        pass

class BuildScript(jhbuild.frontends.buildscript.BuildScript):
    def __init__(self, config, module_list):
        self.config = config
        self.modulelist = module_list
        self.packagedb = PackageDB()
        self.actions = []
    
    def set_action(self, action, module, module_num=-1, action_target=None):
        self.actions.append(action)

    def execute(self, command, hint=None, cwd=None, extra_env=None):
        pass

    def message(self, msg, module_num = -1):
        pass

class Branch(jhbuild.versioncontrol.Branch):
    def __init__(self):
        pass

    def srcdir(self):
        return '/tmp/'
    srcdir = property(srcdir)

    def checkout(self, buildscript):
        pass

    def tree_id(self):
        return 'foo'
