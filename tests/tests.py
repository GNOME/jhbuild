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
from jhbuild.errors import DependencyCycleError, UsageError

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


class ModTypeTestCase(unittest.TestCase):
    def setUp(self):
        self.config = mock.Config()
        self.branch = mock.Branch()
        self.branch.config = self.config

    def build(self, packagedb_params = {}, **kwargs):
        for k in kwargs:
            setattr(self.config, k, kwargs[k])
        buildscript = mock.BuildScript(self.config, [self.module])
        buildscript.packagedb = mock.PackageDB(**packagedb_params)
        buildscript.build()
        return buildscript.actions


class AutotoolsModTypeTestCase(ModTypeTestCase):
    '''Autotools steps'''

    def setUp(self):
        ModTypeTestCase.setUp(self)
        from jhbuild.modtypes.autotools import AutogenModule
        self.module = AutogenModule('foo', self.branch)

    def test_build(self):
        '''Building a autotools module'''
        self.assertEqual(self.build(),
                ['Checking out', 'Configuring', 'Building', 'Installing'])

    def test_build_no_network(self):
        '''Building a autotools module, without network'''
        self.assertEqual(self.build(nonetwork = True),
                ['Configuring', 'Building', 'Installing'])

    def test_update(self):
        '''Updating a autotools module'''
        self.assertEqual(self.build(nobuild = True), ['Checking out'])

    def test_build_check(self):
        '''Building a autotools module, with checks'''
        self.assertEqual(self.build(makecheck = True),
                ['Checking out', 'Configuring', 'Building', 'Checking', 'Installing'])

    def test_build_clean_and_check(self):
        '''Building a autotools module, with cleaning and checks'''
        self.assertEqual(self.build(makecheck = True, makeclean = True),
                ['Checking out', 'Configuring', 'Cleaning', 'Building', 'Checking', 'Installing'])


class BuildPolicyTestCase(ModTypeTestCase):
    '''Build Policy'''

    def setUp(self):
        ModTypeTestCase.setUp(self)
        from jhbuild.modtypes.autotools import AutogenModule
        self.module = AutogenModule('foo', self.branch)

    def test_policy_all(self):
        '''Building an uptodate module with build policy set to "all"'''
        self.config.build_policy = 'all'
        self.assertEqual(self.build(packagedb_params = {'uptodate': True}),
                ['Checking out', 'Configuring', 'Building', 'Installing'])

    def test_policy_updated(self):
        '''Building an uptodate module with build policy set to "updated"'''
        self.config.build_policy = 'updated'
        self.assertEqual(self.build(packagedb_params = {'uptodate': True}), ['Checking out'])

    def test_policy_all_with_no_network(self):
        '''Building an uptodate module with "all" policy, without network'''
        self.config.build_policy = 'all'
        self.assertEqual(self.build(
                    packagedb_params = {'uptodate': True},
                    nonetwork = True),
                ['Configuring', 'Building', 'Installing'])

    def test_policy_updated_with_no_network(self):
        '''Building an uptodate module with "updated" policy, without network'''
        self.config.build_policy = 'updated'
        self.assertEqual(self.build(
                    packagedb_params = {'uptodate': True},
                    nonetwork = True), [])


class TestModTypeTestCase(ModTypeTestCase):
    '''Tests Module Steps'''

    def setUp(self):
        ModTypeTestCase.setUp(self)
        from jhbuild.modtypes.testmodule import TestModule
        self.module = TestModule('foo', self.branch, 'dogtail')

    def test_run(self):
        '''Running a test module'''
        self.assertEqual(self.build(), ['Checking out', 'Testing'])

    def test_build_no_network(self):
        '''Running a test module, without network'''
        self.assertEqual(self.build(nonetwork = True), ['Testing'])



if __name__ == '__main__':
    unittest.main()
