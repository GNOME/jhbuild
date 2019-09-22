# jhbuild - a tool to ease building collections of source packages
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
import os
import tempfile

import jhbuild.frontends.buildscript
import jhbuild.versioncontrol
import jhbuild.errors
import jhbuild.config
from jhbuild.utils import _

class Config(jhbuild.config.Config):
    buildroot = tempfile.mkdtemp(prefix='jhbuild-tests-')
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
    makedistclean = False
    nopoison = False
    makecheck_advisory = False
    module_makecheck = {}
    module_nopoison = {}
    noinstall = False
    forcecheck = False
    partial_build = True
    autogenargs = ''
    module_autogenargs = {}
    module_extra_env = {}
    makeargs = ''
    module_makeargs = {}
    build_targets = ['install']
    exit_on_error = False
    disable_Werror = False

    min_age = None

    prefix = os.path.join(buildroot, 'prefix')
    top_builddir = os.path.join(buildroot, '_jhbuild')

    def __init__(self):
        pass

class PackageEntry:
    def __init__(self, package, version, manifest,
                 metadata):
        self.package = package # string
        self.version = version # string
        self.manifest = manifest # list of strings
        self.metadata = metadata # hash of string to value

class PackageDB:
    time_delta = 0

    def __init__(self, uptodate = False):
        self.force_uptodate = uptodate
        self.entries = {}

    def check(self, package, version=None):
        if self.force_uptodate:
            return self.force_uptodate
        entry = self.entries.get(package)
        if not entry:
            return None
        return entry.version == version

    def add(self, package, version, manifest, configure_cmd=None):
        entry = PackageEntry(package, version, [], {})
        entry.metadata['installed-date'] = time.time()+self.time_delta
        self.entries[package] = entry

    def remove(self, package):
        del self.entries[package]

    def installdate(self, package):
        entry = self.entries.get(package)
        if entry is None:
            return None
        return entry.metadata['installed-date']

    def get(self, package):
        '''Return entry if package is installed, otherwise return None.'''
        return self.entries.get(package)

class BuildScript(jhbuild.frontends.buildscript.BuildScript):
    execute_is_failure = False

    def __init__(self, config, module_list, moduleset):
        self.config = config
        self.modulelist = module_list
        self.moduleset = moduleset
        self.packagedb = moduleset.packagedb
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

class MockModule(jhbuild.modtypes.Package):
    PHASE_FORCE_CHECKOUT = 'force-checkout'
    PHASE_CHECKOUT       = 'checkout'
    PHASE_CLEAN          = 'clean'
    PHASE_DISTCLEAN      = 'distclean'
    PHASE_CONFIGURE      = 'configure'
    PHASE_BUILD          = 'build'
    PHASE_CHECK          = 'check'
    PHASE_DIST           = 'dist'
    PHASE_INSTALL        = 'install'

    def do_checkout(self, buildscript):
        buildscript.set_action(_('Checking out'), self)
        if self.check_build_policy(buildscript) == self.PHASE_DONE:
            raise jhbuild.errors.SkipToEnd()
    do_checkout.error_phases = [PHASE_FORCE_CHECKOUT]

    def skip_checkout(self, buildscript, last_phase):
        # skip the checkout stage if the nonetwork flag is set
        if not self.branch.may_checkout(buildscript):
            if self.check_build_policy(buildscript) == self.PHASE_DONE:
                raise jhbuild.errors.SkipToEnd()
            return True
        return False

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
    do_clean.depends = [PHASE_CONFIGURE]
    do_clean.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_configure(self, buildscript):
        buildscript.set_action(_('Configuring'), self)
    do_configure.depends = [PHASE_CHECKOUT]

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
    do_build.depends = [PHASE_CONFIGURE]
    do_build.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE,
                             PHASE_CLEAN, PHASE_DISTCLEAN]

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        buildscript.moduleset.packagedb.add(self.name, self.get_revision(), None)
    do_install.depends = [PHASE_BUILD]

    def do_check(self, buildscript):
        buildscript.set_action(_('Checking'), self)
    do_check.depends = [PHASE_BUILD]
    do_check.error_phases = [PHASE_CONFIGURE]


class Branch(jhbuild.versioncontrol.Branch):
    def __init__(self, tmpdir):
        self._tmpdir = tmpdir

    @property
    def srcdir(self):
        return self._tmpdir

    @property
    def checkoutdir(self):
        return self._tmpdir

    def checkout(self, buildscript):
        pass

    def may_checkout(self, buildscript):
        if buildscript.config.nonetwork:
            return False
        return True

    def tree_id(self):
        return 'foo'

def raise_command_error(*args):
    raise jhbuild.errors.CommandError('Mock Command Error Exception')
