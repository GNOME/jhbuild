#! /usr/bin/env python
# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007-2008  Frederic Peters
#
#   tests.py: unit tests
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
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest

import jhbuild.moduleset
from jhbuild.modtypes import Package
from jhbuild.errors import DependencyCycleError, UsageError, CommandError

import mock

class ModuleOrderingTestCase(unittest.TestCase):
    '''Module Ordering'''

    def setUp(self):
        self.moduleset = jhbuild.moduleset.ModuleSet()
        self.moduleset.add(Package('foo'))
        self.moduleset.add(Package('bar'))
        self.moduleset.add(Package('baz'))
        self.moduleset.add(Package('qux'))
        self.moduleset.add(Package('quux'))
        self.moduleset.add(Package('corge'))

    def get_module_list(self, seed, skip=[]):
        return [x.name for x in self.moduleset.get_module_list(seed, skip)]

    def test_standalone_one(self):
        '''A standalone module'''
        self.assertEqual(self.get_module_list(['foo']), ['foo'])

    def test_standalone_two(self):
        '''Two standalone modules'''
        self.assertEqual(self.get_module_list(['foo', 'bar']), ['foo', 'bar'])

    def test_dependency_chain_straight(self):
        '''A straight chain of dependencies'''
        self.moduleset.modules['foo'].dependencies = ['bar']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])

    def test_dependency_chain_straight_skip(self):
        '''A straight chain of dependencies, with a module to skip'''
        self.moduleset.modules['foo'].dependencies = ['bar']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.assertEqual(self.get_module_list(['foo'], ['bar']), ['foo'])

    def test_dependency_chain_bi(self):
        '''A dividing chain of dependencies'''
        self.moduleset.modules['foo'].dependencies = ['bar', 'qux']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.moduleset.modules['qux'].dependencies = ['quux']
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'quux', 'qux', 'foo'])

    def test_dependency_cycle(self):
        '''A chain of dependencies with a cycle'''
        self.moduleset.modules['foo'].dependencies = ['bar', 'qux']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.moduleset.modules['qux'].dependencies = ['quux', 'foo']
        self.assertRaises(DependencyCycleError, self.get_module_list, ['foo'])

    def test_dependency_chain_missing_dependencies(self):
        '''A chain of dependencies with a missing <dependencies> module'''
        self.moduleset.modules['foo'].dependencies = ['bar', 'plop']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.assertRaises(UsageError, self.get_module_list, ['foo'])

    def test_dependency_chain_missing_after(self):
        '''A chain of dependencies with a missing <after> module'''
        self.moduleset.modules['foo'].dependencies = ['bar']
        self.moduleset.modules['foo'].after = ['plop']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])

    def test_dependency_chain_missing_suggests(self):
        '''A chain of dependencies with a missing <suggests> module'''
        self.moduleset.modules['foo'].dependencies = ['bar']
        self.moduleset.modules['foo'].suggests = ['plop']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])

    def test_dependency_chain_after(self):
        '''A dividing chain of dependencies with an <after> module'''
        self.moduleset.modules['foo'].dependencies = ['bar', 'qux']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.moduleset.modules['baz'].after = ['qux']
        self.moduleset.modules['qux'].dependencies = ['quux']
        self.assertEqual(self.get_module_list(['foo']), ['quux', 'qux', 'baz', 'bar', 'foo'])

    def test_dependency_chain_suggests(self):
        '''A dividing chain of dependencies with an <suggests> module'''
        self.moduleset.modules['foo'].dependencies = ['bar', 'qux']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.moduleset.modules['baz'].suggests = ['qux']
        self.moduleset.modules['qux'].dependencies = ['quux']
        self.assertEqual(self.get_module_list(['foo']), ['quux', 'qux', 'baz', 'bar', 'foo'])

    def test_dependency_cycle_after(self):
        '''A chain of dependencies with a cycle caused by an <after> module'''
        self.moduleset.modules['foo'].dependencies = ['bar', 'qux']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.moduleset.modules['qux'].dependencies = ['quux']
        self.moduleset.modules['qux'].after = ['foo']
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'quux', 'qux', 'foo'])

    def test_dependency_cycle_suggests(self):
        '''A chain of dependencies with a cycle caused by an <suggests> module'''
        self.moduleset.modules['foo'].dependencies = ['bar', 'qux']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.moduleset.modules['qux'].dependencies = ['quux']
        self.moduleset.modules['qux'].suggests = ['foo']
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'quux', 'qux', 'foo'])


class BuildTestCase(unittest.TestCase):
    def setUp(self):
        self.config = mock.Config()
        self.branch = mock.Branch()
        self.branch.config = self.config
        self.buildscript = None

    def build(self, packagedb_params = {}, **kwargs):
        for k in kwargs:
            setattr(self.config, k, kwargs[k])

        if not self.buildscript or packagedb_params:
            self.buildscript = mock.BuildScript(self.config, self.modules)
            self.buildscript.packagedb = mock.PackageDB(**packagedb_params)
        else:
            packagedb = self.buildscript.packagedb
            self.buildscript = mock.BuildScript(self.config, self.modules)
            self.buildscript.packagedb = packagedb

        self.buildscript.build()
        return self.buildscript.actions

    def tearDown(self):
        self.buildscript = None


class AutotoolsModTypeTestCase(BuildTestCase):
    '''Autotools steps'''

    def setUp(self):
        BuildTestCase.setUp(self)
        from jhbuild.modtypes.autotools import AutogenModule
        self.modules = [AutogenModule('foo', self.branch)]

    def test_build(self):
        '''Building a autotools module'''
        self.assertEqual(self.build(),
                ['foo:Checking out', 'foo:Configuring', 'foo:Building',
                 'foo:Installing'])

    def test_build_no_network(self):
        '''Building a autotools module, without network'''
        self.assertEqual(self.build(nonetwork = True),
                ['foo:Configuring', 'foo:Building', 'foo:Installing'])

    def test_update(self):
        '''Updating a autotools module'''
        self.assertEqual(self.build(nobuild = True), ['foo:Checking out'])

    def test_build_check(self):
        '''Building a autotools module, with checks'''
        self.assertEqual(self.build(makecheck = True),
                ['foo:Checking out', 'foo:Configuring', 'foo:Building',
                 'foo:Checking', 'foo:Installing'])

    def test_build_clean_and_check(self):
        '''Building a autotools module, with cleaning and checks'''
        self.assertEqual(self.build(makecheck = True, makeclean = True),
                ['foo:Checking out', 'foo:Configuring', 'foo:Cleaning',
                 'foo:Building', 'foo:Checking', 'foo:Installing'])

    def test_build_check_error(self):
        '''Building a autotools module, with an error in make check'''

        def make_check_error(buildscript, *args):
            self.modules[0].do_check_orig(buildscript, *args)
            raise CommandError('Mock Command Error Exception')
        make_check_error.next_state = self.modules[0].do_check.next_state
        make_check_error.error_states = self.modules[0].do_check.error_states
        self.modules[0].do_check_orig = self.modules[0].do_check
        self.modules[0].do_check = make_check_error

        self.assertEqual(self.build(makecheck = True),
                ['foo:Checking out', 'foo:Configuring', 'foo:Building',
                 'foo:Checking [error]'])



class BuildPolicyTestCase(BuildTestCase):
    '''Build Policy'''

    def setUp(self):
        BuildTestCase.setUp(self)
        from jhbuild.modtypes.autotools import AutogenModule
        self.modules = [AutogenModule('foo', self.branch)]

    def test_policy_all(self):
        '''Building an uptodate module with build policy set to "all"'''
        self.config.build_policy = 'all'
        self.assertEqual(self.build(packagedb_params = {'uptodate': True}),
                ['foo:Checking out', 'foo:Configuring', 'foo:Building',
                 'foo:Installing'])

    def test_policy_updated(self):
        '''Building an uptodate module with build policy set to "updated"'''
        self.config.build_policy = 'updated'
        self.assertEqual(self.build(packagedb_params = {'uptodate': True}),
                ['foo:Checking out'])

    def test_policy_all_with_no_network(self):
        '''Building an uptodate module with "all" policy, without network'''
        self.config.build_policy = 'all'
        self.assertEqual(self.build(
                    packagedb_params = {'uptodate': True},
                    nonetwork = True),
                ['foo:Configuring', 'foo:Building', 'foo:Installing'])

    def test_policy_updated_with_no_network(self):
        '''Building an uptodate module with "updated" policy, without network'''
        self.config.build_policy = 'updated'
        self.assertEqual(self.build(
                    packagedb_params = {'uptodate': True},
                    nonetwork = True), [])


class TestModTypeTestCase(BuildTestCase):
    '''Tests Module Steps'''

    def setUp(self):
        BuildTestCase.setUp(self)
        from jhbuild.modtypes.testmodule import TestModule
        self.modules = [TestModule('foo', self.branch, 'dogtail')]

    def test_run(self):
        '''Running a test module'''
        self.assertEqual(self.build(), ['foo:Checking out', 'foo:Testing'])

    def test_build_no_network(self):
        '''Running a test module, without network'''
        self.assertEqual(self.build(nonetwork = True), ['foo:Testing'])


class TwoModulesTestCase(BuildTestCase):
    '''Building two dependent modules'''

    def setUp(self):
        BuildTestCase.setUp(self)
        from jhbuild.modtypes.autotools import AutogenModule
        self.foo_branch = mock.Branch()
        self.modules = [AutogenModule('foo', self.foo_branch),
                        AutogenModule('bar', self.branch)]

    def test_build(self):
        '''Building two autotools module'''
        self.assertEqual(self.build(),
                ['foo:Checking out', 'foo:Configuring',
                 'foo:Building', 'foo:Installing',
                 'bar:Checking out', 'bar:Configuring',
                 'bar:Building', 'bar:Installing',
                ])

    def test_build_failure_independent_modules(self):
        '''Building two independent autotools modules, with failure in first'''

        def build_error(buildscript, *args):
            self.modules[0].do_build_orig(buildscript, *args)
            raise CommandError('Mock Command Error Exception')
        build_error.next_state = self.modules[0].do_build.next_state
        build_error.error_states = self.modules[0].do_build.error_states
        self.modules[0].do_build_orig = self.modules[0].do_build
        self.modules[0].do_build = build_error

        self.assertEqual(self.build(),
                ['foo:Checking out', 'foo:Configuring', 'foo:Building [error]',
                 'bar:Checking out', 'bar:Configuring',
                 'bar:Building', 'bar:Installing',
                ])

    def test_build_failure_dependent_modules(self):
        '''Building two dependent autotools modules, with failure in first'''
        self.modules[1].dependencies = ['foo']

        def build_error(buildscript, *args):
            self.modules[0].do_build_orig(buildscript, *args)
            raise CommandError('Mock Command Error Exception')
        build_error.next_state = self.modules[0].do_build.next_state
        build_error.error_states = self.modules[0].do_build.error_states
        self.modules[0].do_build_orig = self.modules[0].do_build
        self.modules[0].do_build = build_error

        self.assertEqual(self.build(),
                ['foo:Checking out', 'foo:Configuring', 'foo:Building [error]'])

    def test_build_failure_dependent_modules_nopoison(self):
        '''Building two dependent autotools modules, with failure, but nopoison'''
        self.modules[1].dependencies = ['foo']

        def build_error(buildscript, *args):
            self.modules[0].do_build_orig(buildscript, *args)
            raise CommandError('Mock Command Error Exception')
        build_error.next_state = self.modules[0].do_build.next_state
        build_error.error_states = self.modules[0].do_build.error_states
        self.modules[0].do_build_orig = self.modules[0].do_build
        self.modules[0].do_build = build_error

        self.assertEqual(self.build(nopoison = True),
                ['foo:Checking out', 'foo:Configuring', 'foo:Building [error]',
                 'bar:Checking out', 'bar:Configuring',
                 'bar:Building', 'bar:Installing',
                ])

    def test_build_no_update(self):
        '''Building two uptodate, autotools module'''
        self.build() # will feed PackageDB
        self.assertEqual(self.build(),
                ['foo:Checking out', 'foo:Configuring',
                 'foo:Building', 'foo:Installing',
                 'bar:Checking out', 'bar:Configuring',
                 'bar:Building', 'bar:Installing',
                ])

    def test_build_no_update_updated_policy(self):
        '''Building two uptodate, autotools module, with 'updated' policy'''
        self.build() # will feed PackageDB
        self.assertEqual(self.build(build_policy = 'updated'),
                ['foo:Checking out', 'bar:Checking out'])

    def test_build_no_update_updated_deps_policy(self):
        '''Building two autotools module, (changed and not), with 'updated-deps' policy'''
        self.modules[1].dependencies = ['foo']
        self.build() # will feed PackageDB
        self.buildscript.packagedb.remove('foo')
        self.buildscript.packagedb.time_delta = 5
        self.assertEqual(self.build(build_policy = 'updated-deps'),
                ['foo:Checking out', 'foo:Configuring',
                 'foo:Building', 'foo:Installing',
                 'bar:Checking out', 'bar:Configuring',
                 'bar:Building', 'bar:Installing',
                ])

    def test_build_no_update_updated_deps_policy(self):
        '''Building two independent autotools module, (changed and not), with 'updated-deps' policy'''
        self.build() # will feed PackageDB
        self.buildscript.packagedb.remove('foo')
        self.buildscript.packagedb.time_delta = 5
        self.assertEqual(self.build(build_policy = 'updated-deps'),
                ['foo:Checking out', 'foo:Configuring',
                 'foo:Building', 'foo:Installing',
                 'bar:Checking out',])

    def test_make_check_failure_dependent_modules(self):
        '''Building two dependent autotools modules, with failure in make check'''
        self.modules[1].dependencies = ['foo']

        def check_error(buildscript, *args):
            self.modules[0].do_check_orig(buildscript, *args)
            raise CommandError('Mock Command Error Exception')
        check_error.next_state = self.modules[0].do_check.next_state
        check_error.error_states = self.modules[0].do_check.error_states
        self.modules[0].do_check_orig = self.modules[0].do_check
        self.modules[0].do_check = check_error

        self.assertEqual(self.build(makecheck = True),
                ['foo:Checking out', 'foo:Configuring',
                 'foo:Building', 'foo:Checking [error]'])

    def test_make_check_failure_dependent_modules_makecheck_advisory(self):
        '''Building two dependent autotools modules, with *advisory* failure in make check'''
        self.modules[1].dependencies = ['foo']

        def check_error(buildscript, *args):
            buildscript.execute_is_failure = True
            try:
                self.modules[0].do_check_orig(buildscript, *args)
            finally:
                buildscript.execute_is_failure = False
        check_error.next_state = self.modules[0].do_check.next_state
        check_error.error_states = self.modules[0].do_check.error_states
        self.modules[0].do_check_orig = self.modules[0].do_check
        self.modules[0].do_check = check_error

        self.assertEqual(self.build(makecheck = True, makecheck_advisory = True),
                ['foo:Checking out', 'foo:Configuring',
                 'foo:Building', 'foo:Checking', 'foo:Installing',
                 'bar:Checking out', 'bar:Configuring',
                 'bar:Building', 'bar:Checking', 'bar:Installing'])


if __name__ == '__main__':
    unittest.main()
