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

import time

import jhbuild.frontends.buildscript
import jhbuild.versioncontrol
import jhbuild.errors
import jhbuild.config

class Config(jhbuild.config.Config):
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
    nopoison = False
    makecheck_advisory = False
    module_makecheck = {}
    module_nopoison = {}
    forcecheck = False
    autogenargs = ''
    module_autogenargs = {}
    module_extra_env = {}
    makeargs = ''
    module_makeargs = {}
    build_targets = ['install']

    min_age = None

    prefix = '/tmp/'

    def __init__(self):
        pass


class PackageDB:
    time_delta = 0

    def __init__(self, uptodate = False):
        self.force_uptodate = uptodate
        self.db = {}

    def check(self, package, version=None):
        if self.force_uptodate:
            return self.force_uptodate
        return self.db.get(package, ('_none_'))[0] == version

    def add(self, package, version):
        self.db[package] = (version, time.time()+self.time_delta)

    def remove(self, package):
        del self.db[package]

    def installdate(self, package):
        return self.db.get(package, ('_none_'))[1]


class BuildScript(jhbuild.frontends.buildscript.BuildScript):
    execute_is_failure = False

    def __init__(self, config, module_list):
        self.config = config
        self.modulelist = module_list
        self.packagedb = PackageDB()
        self.actions = []
    
    def set_action(self, action, module, module_num=-1, action_target=None):
        self.actions.append('%s:%s' % (module.name, action))

    def execute(self, command, hint=None, cwd=None, extra_env=None):
        if self.execute_is_failure:
            raise jhbuild.errors.CommandError('Mock command asked to fail')

    def message(self, msg, module_num = -1):
        pass
    
    def handle_error(self, module, state, nextstate, error, altstates):
        self.actions[-1] = self.actions[-1] + ' [error]'
        return 'fail'

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

def raise_command_error(*args):
    raise jhbuild.errors.CommandError('Mock Command Error Exception')
