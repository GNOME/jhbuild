#! /usr/bin/env python2
# jhbuild - a tool to ease building collections of source packages
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

import builtins
import os
import shutil
import logging
import subprocess
import sys
import glob
import tempfile
import unittest

SRCDIR = os.path.join(os.path.dirname(__file__), '..')

builtins.__dict__['PKGDATADIR'] = None
builtins.__dict__['DATADIR'] = None
builtins.__dict__['SRCDIR'] = SRCDIR

sys.path.insert(0, SRCDIR)

# Override jhbuild.utils.systeminstall with this module 'tests'
import jhbuild.utils.systeminstall
sys.modules['jhbuild.utils.systeminstall'] = sys.modules[__name__]
sys.modules['jhbuild.utils'].systeminstall = sys.modules[__name__]

from jhbuild.errors import UsageError, CommandError
from jhbuild.modtypes import Package
from jhbuild.modtypes.autotools import AutogenModule
from jhbuild.modtypes.distutils import DistutilsModule
import jhbuild.config
import jhbuild.frontends.terminal
import jhbuild.moduleset
import jhbuild.utils.cmds
import jhbuild.versioncontrol.tarball
from jhbuild.utils.sxml import sxml_to_string
from jhbuild.utils.cmds import pprint_output

from . import mock

if sys.platform.startswith('win'):
    import jhbuild.utils.subprocess_win32 as subprocess_win32
    class WindowsTestCase(unittest.TestCase):
        '''Tests for Windows kludges.'''
        def testCmdline2List(self):
            cmdline = 'test "no quotes" != \\"no\\ quotes\\"'
            cmd_list = subprocess_win32.cmdline2list (cmdline)
            self.assertEqual (cmd_list, ['test', 'no quotes', '!=', '"no\\ quotes"'])


def has_xmllint():
    try:
        subprocess.check_output(['xmllint'], stderr=subprocess.STDOUT)
    except OSError:
        return False
    except subprocess.CalledProcessError:
        pass
    return True


def has_trang():
    try:
        subprocess.check_output(['trang'], stderr=subprocess.STDOUT)
    except OSError:
        return False
    except subprocess.CalledProcessError:
        pass
    return True


class ModulesetXMLTest(unittest.TestCase):
    """Check the modulesets for validity.

    This is a lower-level check than `jhbuild checkmodulesets` (which analyses the
    module graph), and doesn't require jhbuild to be built and installed.
    """

    @unittest.skipUnless(has_xmllint(), "no xmllint")
    def test_dtd(self):
        modulesets = os.path.join(SRCDIR, 'modulesets')
        modules = glob.glob(os.path.join(modulesets, '*.modules'))
        dtd = os.path.join(modulesets, 'moduleset.dtd')
        try:
            subprocess.check_output(
                ['xmllint', '--noout', '--dtdvalid', dtd] + modules, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise Exception(e.output)

    @unittest.skipUnless(has_xmllint(), "no xmllint")
    @unittest.skipUnless(has_trang(), "no trang")
    def test_relaxng(self):
        modulesets = os.path.join(SRCDIR, 'modulesets')
        modules = glob.glob(os.path.join(modulesets, '*.modules'))
        rnc = os.path.join(modulesets, 'moduleset.rnc')
        temp_dir = tempfile.mkdtemp()
        rng = os.path.join(temp_dir, 'moduleset.rng')
        try:
            subprocess.check_output(
                ['trang', rnc, rng], stderr=subprocess.STDOUT)
            subprocess.check_output(
                ['xmllint', '--noout', '--relaxng', rng] + modules, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise Exception(e.output)
        finally:
            shutil.rmtree(temp_dir)


class CmdTestCase(unittest.TestCase):

    def test_pprint_output(self):
        try:
            p = subprocess.Popen(
                ["echo", "foo\nbar"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            raise unittest.SkipTest("no echo command")
        arguments = []
        pprint_output(p, lambda *args: arguments.append(args))
        self.assertEqual(arguments, [('foo\n', False), ('bar\n', False)])


class _TestConfig(jhbuild.config.Config):

    # The Config base class calls setup_env() in the constructor, but
    # we need to override some attributes before calling it.
    def setup_env(self):
        pass

    def real_setup_env(self):
        from jhbuild.environment import setup_env
        setup_env(self.prefix)

class JhbuildConfigTestCase(unittest.TestCase):
    """A test case that creates a mock configuration and temporary directory."""

    def setUp(self):
        self.config = mock.Config()
        self._old_env = os.environ.copy()
        self._temp_dirs = []

    def tearDown(self):
        restore_environ(self._old_env)
        for temp_dir in self._temp_dirs:
            shutil.rmtree(temp_dir)

    def make_temp_dir(self):
        temp_dir = tempfile.mkdtemp(prefix='unittest-')
        self._temp_dirs.append(temp_dir)
        return temp_dir

    def make_config(self):
        temp_dir = self.make_temp_dir()
        config = _TestConfig(None, [])
        config.checkoutroot = os.path.abspath(os.path.join(temp_dir, 'checkout'))
        config.prefix = os.path.abspath(os.path.join(temp_dir, 'prefix'))
        config.top_builddir = os.path.join(config.prefix, '_jhbuild')
        os.makedirs(config.checkoutroot)
        os.makedirs(config.prefix)
        config.buildroot = None
        config.interact = False
        config.use_local_modulesets = True
        config.quiet_mode = True # Not enough to disable output entirely
        config.progress_bar = False
        config.real_setup_env()
        return config

    def make_branch(self, config, src_name):
        branch_dir = os.path.join(config.checkoutroot, src_name)
        shutil.copytree(os.path.join(os.path.dirname(__file__), src_name),
                        branch_dir)
        # With 'make distcheck' the source is read only, so we need to chmod
        # after copying
        os.chmod(branch_dir, 0o777)
        return SimpleBranch(src_name, branch_dir)

    def make_terminal_buildscript(self, config, module_list):
        module_set = jhbuild.moduleset.load(config)
        module_set.packagedb = mock.PackageDB()
        return jhbuild.frontends.terminal.TerminalBuildScript(config, module_list, module_set)


class CMakeModuleTest(unittest.TestCase):

    def test_to_sxml(self):
        from jhbuild.modtypes.cmake import CMakeModule

        mod = CMakeModule("foo")
        self.assertEqual(
            sxml_to_string(mod.to_sxml()),
            '<cmake id="foo"><dependencies></dependencies>\n<branch></branch></cmake>')


class ModuleOrderingTestCase(JhbuildConfigTestCase):
    '''Module Ordering'''

    def setUp(self):
        super(ModuleOrderingTestCase, self).setUp()
        self.moduleset = jhbuild.moduleset.ModuleSet(config=self.config)
        self.moduleset.add(Package('foo'))
        self.moduleset.add(Package('bar'))
        self.moduleset.add(Package('baz'))
        self.moduleset.add(Package('qux'))
        self.moduleset.add(Package('quux'))
        self.moduleset.add(Package('corge'))

    def get_module_list(self, seed, skip=[], tags=[], include_suggests=True,
                        include_afters=False):
        return [x.name for x in self.moduleset.get_module_list(
                    seed, skip, tags, include_suggests,
                    include_afters)]

    def test_standalone_one(self):
        '''A standalone module'''
        self.assertEqual(self.get_module_list(['foo']), ['foo'])

    def test_standalone_two(self):
        '''Two standalone modules'''
        self.assertEqual(self.get_module_list(['foo', 'bar']), ['foo', 'bar'])

    def test_standalone_skip_fnmatch(self):
        '''Four standalone modules with a fnmatch skip'''
        self.assertEqual(self.get_module_list(['foo', 'bar', 'baz', 'corge'], ['ba*']), ['foo', 'corge'])
        self.assertEqual(self.get_module_list(['foo', 'bar', 'baz', 'corge'], ['?o']), ['foo', 'bar', 'baz', 'corge'])
        self.assertEqual(self.get_module_list(['foo', 'bar', 'baz', 'corge'], ['?o*']), ['bar', 'baz'])
        self.assertEqual(self.get_module_list(['foo', 'bar', 'baz', 'corge'], ['*r*']), ['foo', 'baz'])

    def test_standalone_dont_skip_config_module(self):
        '''Don't skip the modules=[...] in the config file'''
        self.config.modules = ['foo', 'baz']
        self.assertEqual(self.get_module_list(['foo', 'bar', 'baz', 'corge'], ['*']), ['foo', 'baz'])
        self.assertEqual(self.get_module_list('all', ['*']), ['foo', 'baz'])

    def test_standalone_dont_skip_config_module_fnmatch(self):
        '''Don't skip the modules=[...] in the config file even if the fnmatch applies'''
        self.config.modules = ['foo', 'baz']
        self.assertEqual(self.get_module_list(['foo', 'bar', 'baz', 'corge'], ['b*']), ['foo', 'baz', 'corge'])
        self.assertEqual(self.get_module_list('all', ['b*']), ['foo', 'baz', 'qux', 'quux', 'corge'])

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

    def test_dependency_chain_straight_skip_fnmatch(self):
        '''A straight chain of dependencies, with a module to skip'''
        self.moduleset.modules['foo'].dependencies = ['bar']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.assertEqual(self.get_module_list(['foo'], ['b?r']), ['foo'])

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
        self.moduleset.raise_exception_on_warning = True
        self.assertRaises(UsageError, self.get_module_list, ['foo'])
        self.moduleset.raise_exception_on_warning = False

    def test_dependency_chain_missing_dependencies(self):
        '''A chain of dependencies with a missing <dependencies> module'''
        self.moduleset.modules['foo'].dependencies = ['bar', 'plop']
        self.moduleset.modules['bar'].dependencies = ['baz']
        self.moduleset.raise_exception_on_warning = True
        self.assertRaises(UsageError, self.get_module_list, ['foo'])
        self.moduleset.raise_exception_on_warning = False
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])

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
        self.assertEqual(self.get_module_list(['foo'], include_afters=True), ['quux', 'qux', 'baz', 'bar', 'foo'])

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

    def test_dependency_chain_recursive_after(self):
        '''A chain of dependencies with a recursively defined <after> module'''
        # see http://bugzilla.gnome.org/show_bug.cgi?id=546640
        self.moduleset.modules['foo'] # gtk-doc
        self.moduleset.modules['bar'].dependencies = ['foo'] # meta-bootstrap
        self.moduleset.modules['bar'].type = 'meta'
        self.moduleset.modules['baz'].after = ['bar'] # cairo
        self.moduleset.modules['qux'].dependencies = ['baz'] # meta-stuff
        self.assertEqual(self.get_module_list(['qux', 'foo']), ['foo', 'baz', 'qux'])

    def test_dependency_chain_recursive_after_dependencies(self):
        '''A chain dependency with an <after> module depending on an inversed relation'''
        # see http://bugzilla.gnome.org/show_bug.cgi?id=546640
        self.moduleset.modules['foo'] # nautilus
        self.moduleset.modules['bar'] # nautilus-cd-burner
        self.moduleset.modules['baz'] # tracker
        self.moduleset.modules['foo'].after = ['baz']
        self.moduleset.modules['bar'].dependencies = ['foo']
        self.moduleset.modules['baz'].dependencies = ['bar']
        self.moduleset.raise_exception_on_warning = True
        self.assertRaises(UsageError, self.get_module_list, ['foo', 'bar'])
        self.moduleset.raise_exception_on_warning = False

    def test_sys_deps(self):
        '''deps ommitted because satisfied by system dependencies'''
        class TestBranch(jhbuild.versioncontrol.tarball.TarballBranch):
            version = None

            def __init__(self):
                pass

        self.moduleset.add(Package('syspkgalpha'))
        self.moduleset.modules['foo'].dependencies = ['bar']
        self.moduleset.modules['bar'].dependencies = ['syspkgalpha']
        self.moduleset.modules['syspkgalpha'].dependencies = ['baz']
        self.moduleset.modules['syspkgalpha'].pkg_config = 'syspkgalpha.pc'
        self.moduleset.modules['syspkgalpha'].branch = TestBranch()
        self.moduleset.modules['syspkgalpha'].branch.version = '3'
        self.assertEqual(self.get_module_list(['foo']),
                         ['baz', 'syspkgalpha', 'bar', 'foo'])
        self.moduleset.modules['syspkgalpha'].branch.version = '3.1'
        self.assertEqual(self.get_module_list(['foo']),
                         ['baz', 'syspkgalpha', 'bar', 'foo'])
        self.moduleset.modules['syspkgalpha'].branch.version = '2'
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])
        self.moduleset.modules['syspkgalpha'].branch.version = '1'
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])
        self.moduleset.modules['syspkgalpha'].branch.version = '1.1'
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])

        self.moduleset.add(Package('syspkgbravo'))
        self.moduleset.modules['foo'].dependencies = ['bar']
        self.moduleset.modules['bar'].dependencies = ['syspkgbravo']
        self.moduleset.modules['syspkgbravo'].dependencies = ['baz']
        self.moduleset.modules['syspkgbravo'].pkg_config = 'syspkgbravo.pc'
        self.moduleset.modules['syspkgbravo'].branch = TestBranch()
        self.moduleset.modules['syspkgbravo'].branch.version = '3'
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])
        self.moduleset.modules['syspkgbravo'].branch.version = '3.3'
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])
        self.moduleset.modules['syspkgbravo'].branch.version = '3.4'
        self.assertEqual(self.get_module_list(['foo']), ['baz', 'bar', 'foo'])
        self.moduleset.modules['syspkgbravo'].branch.version = '3.5'
        self.assertEqual(self.get_module_list(['foo']),
                         ['baz', 'syspkgbravo', 'bar', 'foo'])
        self.moduleset.modules['syspkgbravo'].branch.version = '4'
        self.assertEqual(self.get_module_list(['foo']),
                         ['baz', 'syspkgbravo', 'bar', 'foo'])


class BuildTestCase(JhbuildConfigTestCase):
    def setUp(self):
        super(BuildTestCase, self).setUp()
        self.branch = mock.Branch(os.path.join(self.config.buildroot, 'nonexistent'))
        self.branch.config = self.config
        self.packagedb = None
        self.buildscript = None
        self.moduleset = None
        os.environ['JHBUILD_PREFIX'] = self.config.prefix

    def tearDown(self):
        super(BuildTestCase, self).tearDown()
        self.buildscript = None

    def build(self, packagedb_params = {}, **kwargs):
        self.config.build_targets = ['install', 'test']
        for k in kwargs:
            setattr(self.config, k, kwargs[k])
        self.config.update_build_targets()

        if (self.packagedb is None) or (len(packagedb_params) > 0):
            self.packagedb = mock.PackageDB(**packagedb_params)
            self.moduleset = jhbuild.moduleset.ModuleSet(self.config, db=self.packagedb)
        self.buildscript = mock.BuildScript(self.config, self.modules, self.moduleset)

        self.buildscript.build()
        return self.buildscript.actions

class AutotoolsModTypeTestCase(BuildTestCase):
    '''Autotools steps'''

    def setUp(self):
        super(AutotoolsModTypeTestCase, self).setUp()
        module = mock.MockModule('foo', branch=self.branch)
        self.modules = [module]
        self.modules[0].config = self.config
        # replace clean method as it checks for Makefile existence
        self.modules[0].skip_clean = lambda x,y: False

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
        make_check_error.depends = self.modules[0].do_check.depends
        make_check_error.error_phases = self.modules[0].do_check.error_phases
        self.modules[0].do_check_orig = self.modules[0].do_check
        self.modules[0].do_check = make_check_error

        self.assertEqual(self.build(makecheck = True),
                ['foo:Checking out', 'foo:Configuring', 'foo:Building',
                 'foo:Checking [error]'])


class BuildPolicyTestCase(BuildTestCase):
    '''Build Policy'''

    def setUp(self):
        super(BuildPolicyTestCase, self).setUp()
        self.modules = [mock.MockModule('foo', branch=self.branch)]
        self.modules[0].config = self.config

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


class TwoModulesTestCase(BuildTestCase):
    '''Building two dependent modules'''

    def setUp(self):
        super(TwoModulesTestCase, self).setUp()
        self.foo_branch = mock.Branch(os.path.join(self.config.buildroot, 'nonexistent-foo'))
        self.modules = [mock.MockModule('foo', branch=self.foo_branch),
                        mock.MockModule('bar', branch=self.branch)]
        self.modules[0].config = self.config
        self.modules[1].config = self.config

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
        build_error.depends = self.modules[0].do_build.depends
        build_error.error_phases = self.modules[0].do_build.error_phases
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
        build_error.depends = self.modules[0].do_build.depends
        build_error.error_phases = self.modules[0].do_build.error_phases
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
        build_error.depends = self.modules[0].do_build.depends
        build_error.error_phases = self.modules[0].do_build.error_phases
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

    def test_make_check_failure_dependent_modules(self):
        '''Building two dependent autotools modules, with failure in make check'''
        self.modules[1].dependencies = ['foo']

        def check_error(buildscript, *args):
            self.modules[0].do_check_orig(buildscript, *args)
            raise CommandError('Mock Command Error Exception')
        check_error.depends = self.modules[0].do_check.depends
        check_error.error_phases = self.modules[0].do_check.error_phases
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
        check_error.depends = self.modules[0].do_check.depends
        check_error.error_phases = self.modules[0].do_check.error_phases
        self.modules[0].do_check_orig = self.modules[0].do_check
        self.modules[0].do_check = check_error

        self.assertEqual(self.build(makecheck = True, makecheck_advisory = True),
                ['foo:Checking out', 'foo:Configuring',
                 'foo:Building', 'foo:Checking', 'foo:Installing',
                 'bar:Checking out', 'bar:Configuring',
                 'bar:Building', 'bar:Checking', 'bar:Installing'])


class SimpleBranch(object):

    def __init__(self, name, dir_path):
        self.branchname = name
        self.srcdir = dir_path
        self.checkoutdir = None

    def checkout(self, buildscript):
        pass

    def may_checkout(self, buildscript):
        return True

    def tree_id(self):
        return 'made-up-tree-id'

    def get_module_basename(self):
        return 'made-up-module-basename'


def restore_environ(env):
    # os.environ.clear() doesn't appear to change underlying environment.
    for key in os.environ.keys():
        del os.environ[key]
    for key, value in env.items():
        os.environ[key] = value


STDOUT_FILENO = 1

def with_stdout_hidden(func):
    null_device = '/dev/null'
    if sys.platform.startswith('win'):
        null_device = 'NUL'
    old_fd = os.dup(STDOUT_FILENO)
    new_fd = os.open(null_device, os.O_WRONLY)
    os.dup2(new_fd, STDOUT_FILENO)
    os.close(new_fd)
    try:
        return func()
    finally:
        os.dup2(old_fd, STDOUT_FILENO)
        os.close(old_fd)


class EndToEndTest(JhbuildConfigTestCase):

    # FIXME: broken under Win32
    def test_distutils(self):
        config = self.make_config()
        module_list = [DistutilsModule('hello',
                                       self.make_branch(config, 'distutils'))]
        module_list[0].config = self.config
        module_list[0].python = 'python3'
        build = self.make_terminal_buildscript(config, module_list)
        with_stdout_hidden(build.build)
        proc = subprocess.Popen(['hello'], stdout=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        self.assertEqual(stdout.strip(), b'Hello world (distutils)')
        self.assertEqual(proc.wait(), 0)

    def test_autotools(self):
        config = self.make_config()
        module_list = [AutogenModule('hello',
                                     branch=self.make_branch(config, 'autotools'))]
        module_list[0].config = self.config
        build = self.make_terminal_buildscript(config, module_list)
        with_stdout_hidden(build.build)
        proc = subprocess.Popen(['hello'], stdout=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        self.assertEqual(stdout.strip(), b'Hello world (autotools)')
        self.assertEqual(proc.wait(), 0)

    # Won't pass under stock MSYS because pkgconfig isn't installed in base
    # path. Will work if you set ACLOCAL_FLAGS, PATH and PKG_CONFIG_PATH to
    # a prefix where pkg-config is installed.
    def test_autotools_with_libtool(self):
        config = self.make_config()
        module_list = [
            AutogenModule('libhello', branch=self.make_branch(config, 'libhello')),
            AutogenModule('hello', branch=self.make_branch(config, 'hello'))]
        module_list[0].config = self.config
        module_list[1].config = self.config
        build = self.make_terminal_buildscript(config, module_list)
        with_stdout_hidden(build.build)
        proc = subprocess.Popen(['hello'], stdout=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        self.assertEqual(stdout.strip(), b'Hello world (library test)')
        self.assertEqual(proc.wait(), 0)

class UtilsTest(JhbuildConfigTestCase):

    def test_compare_version(self):
        self.assertTrue(jhbuild.utils.cmds.compare_version('3.13.1.with.ckbi.1.88', '3'))
        self.assertTrue(jhbuild.utils.cmds.compare_version('3.13.1.with.ckbi.1.88', '3.12'))
        self.assertTrue(jhbuild.utils.cmds.compare_version('3.13.1.with.ckbi.1.88', '3.13.1'))
        self.assertFalse(jhbuild.utils.cmds.compare_version('3.13.1.with.ckbi.1.88', '4'))
        self.assertFalse(jhbuild.utils.cmds.compare_version('3.13.1.with.ckbi.1.88', '3.14'))
        self.assertFalse(jhbuild.utils.cmds.compare_version('3.13.1.with.ckbi.1.88', '3.13.2'))
        self.assertFalse(jhbuild.utils.cmds.compare_version('3with', '3.1'))
        self.assertTrue(jhbuild.utils.cmds.compare_version('3with', '2'))
        self.assertFalse(jhbuild.utils.cmds.compare_version('with3', '3.1'))
        self.assertTrue(jhbuild.utils.cmds.compare_version('with3', '2'))
        self.assertFalse(jhbuild.utils.cmds.compare_version('3.with', '3.1'))
        self.assertTrue(jhbuild.utils.cmds.compare_version('3.with', '3'))
        self.assertFalse(jhbuild.utils.cmds.compare_version('0.5', '0.6'))
        self.assertTrue(jhbuild.utils.cmds.compare_version('0.5', '0.5'))
        self.assertFalse(jhbuild.utils.cmds.compare_version('1', '1.2.3.4'))
        self.assertTrue(jhbuild.utils.cmds.compare_version('1.2.3.4', '1'))
        self.assertTrue(jhbuild.utils.cmds.compare_version('2', '1.2.3.4'))
        self.assertFalse(jhbuild.utils.cmds.compare_version('1.2.3.4', '2'))

def get_installed_pkgconfigs(config):
    ''' overload jhbuild.utils.get_installed_pkgconfigs'''
    return {'syspkgalpha'   : '2',
            'syspkgbravo'   : '3.4'}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main()
