# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   moduleset.py: logic for running the build.
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

from __future__ import generators

import os
import sys
import urlparse
import logging

from jhbuild.errors import UsageError, FatalError, DependencyCycleError, \
             CommandError, UndefinedRepositoryError

try:
    import xml.dom.minidom
    import xml.parsers.expat
except ImportError:
    raise FatalError(_('Python xml packages are required but could not be found'))

from jhbuild import modtypes
from jhbuild.versioncontrol import get_repo_type
from jhbuild.utils import httpcache
from jhbuild.utils import packagedb
from jhbuild.utils.cmds import compare_version, get_output
from jhbuild.modtypes.testmodule import TestModule
from jhbuild.versioncontrol.tarball import TarballBranch
from jhbuild.utils import systeminstall

__all__ = ['load', 'load_tests', 'get_default_repo']

_default_repo = None
def get_default_repo():
    return _default_repo

class ModuleSet:
    def __init__(self, config = None, db=None):
        self.config = config
        self.modules = {}

        if db is None:
            legacy_pkgdb_path = os.path.join(self.config.prefix, 'share', 'jhbuild', 'packagedb.xml')
            new_pkgdb_path = os.path.join(self.config.top_builddir, 'packagedb.xml')
            if os.path.isfile(legacy_pkgdb_path):
                os.rename(legacy_pkgdb_path, new_pkgdb_path)
            self.packagedb = packagedb.PackageDB(new_pkgdb_path, config)
        else:
            self.packagedb = db

    def add(self, module):
        '''add a Module object to this set of modules'''
        self.modules[module.name] = module

    def get_module(self, module_name, ignore_case = False):
        if self.modules.has_key(module_name) or not ignore_case:
            return self.modules[module_name]
        module_name_lower = module_name.lower()
        for module in self.modules.keys():
            if module.lower() == module_name_lower:
                logging.info(_('fixed case of module \'%(orig)s\' to '
                               '\'%(new)s\'') % {'orig': module_name,
                                                 'new': module})
                return self.modules[module]
        raise KeyError(module_name)

    def get_module_list(self, seed, skip=[], tags=[], ignore_cycles=False,
                ignore_suggests=False, include_optional_modules=False,
                ignore_missing=False, process_sysdeps=True):
        '''gets a list of module objects (in correct dependency order)
        needed to build the modules in the seed list'''

        if seed == 'all': seed = self.modules.keys()
        try:
            all_modules = [self.get_module(mod, ignore_case = True) for mod in seed if mod not in skip]
        except KeyError, e:
            raise UsageError(_('module "%s" not found') % e)

        asked_modules = all_modules[:]

        # 1st: get all modules that will be needed
        # note this is only needed to skip "after" modules that would not
        # otherwise be built
        i = 0
        while i < len(all_modules):
            dep_missing = False
            for modname in all_modules[i].dependencies:
                depmod = self.modules.get(modname)
                if not depmod:
                    if not ignore_missing:
                        raise UsageError(_(
                                '%(module)s has a dependency on unknown "%(invalid)s" module') % {
                                    'module': all_modules[i].name,
                                    'invalid': modname})
                    logging.info(_(
                                '%(module)s has a dependency on unknown "%(invalid)s" module') % {
                                    'module': all_modules[i].name,
                                    'invalid': modname})
                    dep_missing = True
                    continue

                if not depmod in all_modules:
                    all_modules.append(depmod)

            if not ignore_suggests:
                # suggests can be ignored if not in moduleset
                for modname in all_modules[i].suggests:
                    depmod = self.modules.get(modname)
                    if not depmod:
                        continue
                    if not depmod in all_modules:
                        all_modules.append(depmod)

            if dep_missing:
                del all_modules[i]

            i += 1

        # 2nd: order them, raise an exception on hard dependency cycle, ignore
        # them for soft dependencies
        self._ordered = []
        self._state = {}

        for modname in skip:
            # mark skipped modules as already processed
            self._state[self.modules.get(modname)] = 'processed'

        # process_sysdeps lets us avoid repeatedly checking system module state when
        # handling recursive dependencies.
        if self.config.partial_build and process_sysdeps:
            system_module_state = self.get_system_modules(all_modules)
            for pkg_config,(module, req_version, installed_version, new_enough) in system_module_state.iteritems():
                # Only mark a module as processed if new enough *and* we haven't built it before
                if new_enough and not self.packagedb.check(module.name):
                    self._state[module] = 'processed'

        if tags:
            for modname in self.modules:
                for tag in tags:
                    if tag in self.modules[modname].tags:
                        break
                else:
                    # no tag matched, mark module as processed
                    self._state[self.modules[modname]] = 'processed'

        def order(modules, module, mode = 'dependencies'):
            if self._state.get(module, 'clean') == 'processed':
                # already seen
                return
            if self._state.get(module, 'clean') == 'in-progress':
                # dependency circle, abort when processing hard dependencies
                if not ignore_cycles:
                    raise DependencyCycleError()
                else:
                    self._state[module] = 'in-progress'
                    return
            self._state[module] = 'in-progress'
            for modname in module.dependencies:
                try:
                    depmod = self.modules[modname]
                    order([self.modules[x] for x in depmod.dependencies], depmod, 'dependencies')
                except KeyError:
                    pass # user already notified via logging.info above
            if not ignore_suggests:
                for modname in module.suggests:
                    depmod = self.modules.get(modname)
                    if not depmod:
                        continue
                    save_state, save_ordered = self._state.copy(), self._ordered[:]
                    try:
                        order([self.modules[x] for x in depmod.dependencies], depmod, 'suggests')
                    except DependencyCycleError:
                        self._state, self._ordered = save_state, save_ordered
                    except KeyError:
                        pass # user already notified via logging.info above

            extra_afters = []
            for modname in module.after:
                depmod = self.modules.get(modname)
                if not depmod:
                    # this module doesn't exist, skip.
                    continue
                if not depmod in all_modules and not include_optional_modules:
                    # skip modules that would not be built otherwise
                    # (build_optional_modules being the argument to force them
                    # to be included nevertheless)

                    if not depmod.dependencies:
                        # depmod itself has no dependencies, skip.
                        continue

                    # more expensive, if depmod has dependencies, compute its
                    # full list of hard dependencies, getting it into
                    # extra_afters, so they are also evaluated.
                    # <http://bugzilla.gnome.org/show_bug.cgi?id=546640>
                    t_ms = ModuleSet(self.config)
                    t_ms.modules = self.modules.copy()
                    dep_modules = t_ms.get_module_list(seed=[depmod.name], process_sysdeps=False)
                    for m in dep_modules[:-1]:
                        if m in all_modules:
                            extra_afters.append(m)
                    continue
                save_state, save_ordered = self._state.copy(), self._ordered[:]
                try:
                    order([self.modules[x] for x in depmod.dependencies], depmod, 'after')
                except DependencyCycleError:
                    self._state, self._ordered = save_state, save_ordered
            for depmod in extra_afters:
                save_state, save_ordered = self._state.copy(), self._ordered[:]
                try:
                    order([self.modules[x] for x in depmod.dependencies], depmod, 'after')
                except DependencyCycleError:
                    self._state, self._ordered = save_state, save_ordered
            self._state[module] = 'processed'
            self._ordered.append(module)

        for i, module in enumerate(all_modules):
            order([], module)
            if i+1 == len(asked_modules): 
                break

        ordered = self._ordered[:]
        del self._ordered
        del self._state
        return ordered
    
    def get_full_module_list(self, skip=[], ignore_cycles=False):
        return self.get_module_list(self.modules.keys(), skip=skip,
                ignore_cycles=ignore_cycles, ignore_missing=True)

    def get_test_module_list (self, seed, skip=[]):
        test_modules = []
        if seed == []:
            return
        for mod in self.modules.values():
            for test_app in seed:
                if test_app in mod.tested_pkgs:
                    test_modules.append(mod)
        return test_modules

    def get_system_modules(self, modules):
        assert self.config.partial_build

        installed_pkgconfig = systeminstall.get_installed_pkgconfigs(self.config)
        
        # pkgconfig -> (required_version, installed_verison)
        module_state = {}
        for module in modules:
            if module.pkg_config is None:
                continue
            if not isinstance(module.branch, TarballBranch):
                continue
            # Strip off the .pc
            module_pkg = module.pkg_config[:-3]
            required_version = module.branch.version
            if not module_pkg in installed_pkgconfig:
                module_state[module_pkg] = (module, required_version, None, False)
            else:
                installed_version = installed_pkgconfig[module_pkg]
                new_enough = compare_version(installed_version, required_version)
                module_state[module_pkg] = (module, required_version, installed_version, new_enough)
        return module_state
    
    def write_dot(self, modules=None, fp=sys.stdout, suggests=False, clusters=False):
        from jhbuild.modtypes import MetaModule
        from jhbuild.modtypes.autotools import AutogenModule
        from jhbuild.versioncontrol.tarball import TarballBranch
        
        if modules is None:
            modules = self.modules.keys()
        inlist = {}
        for module in modules:
            inlist[module] = None

        fp.write('digraph "G" {\n'
                 '  fontsize = 8;\n'
                 '  ratio = auto;\n')
        while modules:
            modname = modules[0]
            try:
                mod = self.modules[modname]
            except KeyError:
                logging.warning(_('Unknown module:') + ' '+ modname)
                del modules[0]
                continue
            if isinstance(mod, MetaModule):
                attrs = '[color="lightcoral",style="filled",' \
                        'label="%s"]' % mod.name
            else:
                label = mod.name
                color = 'lightskyblue'
                if mod.branch.branchname:
                    label += '\\n(%s)' % mod.branch.branchname
                if isinstance(mod.branch, TarballBranch):
                    color = 'lightgoldenrod'
                attrs = '[color="%s",style="filled",label="%s"]' % (color, label)
            fp.write('  "%s" %s;\n' % (modname, attrs))
            del modules[0]
            
            for dep in self.modules[modname].dependencies:
                fp.write('  "%s" -> "%s";\n' % (modname, dep))
                if not inlist.has_key(dep):
                    modules.append(dep)
                inlist[dep] = None

            if suggests:
                for dep in self.modules[modname].after + self.modules[modname].suggests:
                    if self.modules.has_key(dep):
                        fp.write('  "%s" -> "%s" [style=dotted];\n' % (modname, dep))
                        if not inlist.has_key(dep):
                            modules.append(dep)
                        inlist[dep] = None

        if clusters:
            # create clusters for MetaModules
            for modname in inlist.keys():
                mod = self.modules.get(modname)
                if isinstance(mod, MetaModule):
                    fp.write('  subgraph "cluster_%s" {\n' % mod.name)
                    fp.write('     label="%s";\n' % mod.name)
                    fp.write('     style="filled";bgcolor="honeydew2";\n')

                    for dep in mod.dependencies:
                        fp.write('    "%s";\n' % dep)
                    fp.write('  }\n')

        fp.write('}\n')

def load(config, uri=None):
    if uri is not None:
        modulesets = [ uri ]
    elif type(config.moduleset) in (list, tuple):
        modulesets = config.moduleset
    else:
        modulesets = [ config.moduleset ]
    ms = ModuleSet(config = config)
    for uri in modulesets:
        if os.path.isabs(uri):
            pass
        elif config.modulesets_dir and config.nonetwork or config.use_local_modulesets:
            if os.path.isfile(os.path.join(config.modulesets_dir,
                                           uri + '.modules')):
                uri = os.path.join(config.modulesets_dir, uri + '.modules')
            elif os.path.isfile(os.path.join(config.modulesets_dir, uri)):
                uri = os.path.join(config.modulesets_dir, uri)
        elif not urlparse.urlparse(uri)[0]:
            uri = 'http://git.gnome.org/browse/jhbuild/plain/modulesets' \
                  '/%s.modules' % uri
        ms.modules.update(_parse_module_set(config, uri).modules)
    return ms

def load_tests (config, uri=None):
    ms = load (config, uri)
    ms_tests = ModuleSet(config = config)
    for app, module in ms.modules.iteritems():
        if module.__class__ == TestModule:
            ms_tests.modules[app] = module
    return ms_tests

def _child_elements(parent):
    for node in parent.childNodes:
        if node.nodeType == node.ELEMENT_NODE:
            yield node

def _child_elements_matching(parent, names):
    for node in parent.childNodes:
        if node.nodeType == node.ELEMENT_NODE and node.nodeName in names:
            yield node

def _parse_module_set(config, uri):
    try:
        filename = httpcache.load(uri, nonetwork=config.nonetwork, age=0)
    except Exception, e:
        raise FatalError(_('could not download %s: %s') % (uri, e))
    filename = os.path.normpath(filename)
    try:
        document = xml.dom.minidom.parse(filename)
    except IOError, e:
        raise FatalError(_('failed to parse %s: %s') % (filename, e))
    except xml.parsers.expat.ExpatError, e:
        raise FatalError(_('failed to parse %s: %s') % (uri, e))

    assert document.documentElement.nodeName == 'moduleset'
    moduleset = ModuleSet(config = config)
    moduleset_name = document.documentElement.getAttribute('name')
    if not moduleset_name:
        moduleset_name = os.path.basename(uri)
        if moduleset_name.endswith('.modules'):
            moduleset_name = moduleset_name[:-len('.modules')]

    # load up list of repositories
    repositories = {}
    default_repo = None
    for node in _child_elements_matching(
            document.documentElement, ['repository', 'cvsroot', 'svnroot',
                                       'arch-archive']):
        name = node.getAttribute('name')
        if node.getAttribute('default') == 'yes':
            default_repo = name
        if node.nodeName == 'repository':
            repo_type = node.getAttribute('type')
            repo_class = get_repo_type(repo_type)
            kws = {}
            for attr in repo_class.init_xml_attrs:
                if node.hasAttribute(attr):
                    kws[attr.replace('-', '_')] = node.getAttribute(attr)
            if name in repositories:
                logging.warning(_('Duplicate repository:') + ' '+ name)
            repositories[name] = repo_class(config, name, **kws)
            repositories[name].moduleset_uri = uri
            mirrors = {}
            for mirror in _child_elements_matching(node, ['mirror']):
                mirror_type = mirror.getAttribute('type')
                mirror_class = get_repo_type(mirror_type)
                kws = {}
                for attr in mirror_class.init_xml_attrs:
                    if mirror.hasAttribute(attr):
                        kws[attr.replace('-','_')] = mirror.getAttribute(attr)
                mirrors[mirror_type] = mirror_class(config, name, **kws)
                #mirrors[mirror_type].moduleset_uri = uri
            setattr(repositories[name], "mirrors", mirrors)
        if node.nodeName == 'cvsroot':
            cvsroot = node.getAttribute('root')
            if node.hasAttribute('password'):
                password = node.getAttribute('password')
            else:
                password = None
            repo_type = get_repo_type('cvs')
            repositories[name] = repo_type(config, name,
                                           cvsroot=cvsroot, password=password)
        elif node.nodeName == 'svnroot':
            svnroot = node.getAttribute('href')
            repo_type = get_repo_type('svn')
            repositories[name] = repo_type(config, name, href=svnroot)
        elif node.nodeName == 'arch-archive':
            archive_uri = node.getAttribute('href')
            repo_type = get_repo_type('arch')
            repositories[name] = repo_type(config, name,
                                           archive=name, href=archive_uri)

    # and now module definitions
    for node in _child_elements(document.documentElement):
        if node.nodeName == 'include':
            href = node.getAttribute('href')
            inc_uri = urlparse.urljoin(uri, href)
            try:
                inc_moduleset = _parse_module_set(config, inc_uri)
            except UndefinedRepositoryError:
                raise
            except FatalError, e:
                if inc_uri[0] == '/':
                    raise e
                # look up in local modulesets
                inc_uri = os.path.join(os.path.dirname(__file__), '..', 'modulesets',
                                   href)
                inc_moduleset = _parse_module_set(config, inc_uri)

            moduleset.modules.update(inc_moduleset.modules)
        elif node.nodeName in ['repository', 'cvsroot', 'svnroot',
                               'arch-archive']:
            pass
        else:
            module = modtypes.parse_xml_node(node, config, uri,
                    repositories, default_repo)
            if moduleset_name:
                module.tags.append(moduleset_name)
            module.moduleset_name = moduleset_name
            module.config = config
            moduleset.add(module)

    # keep default repository around, used when creating automatic modules
    global _default_repo
    if default_repo:
        _default_repo = repositories[default_repo]

    return moduleset

def warn_local_modulesets(config):
    if config.use_local_modulesets:
        return

    moduleset_local_path = os.path.join(SRCDIR, 'modulesets')
    if not os.path.exists(moduleset_local_path):
        # moduleset-less checkout
        return

    if not os.path.exists(os.path.join(moduleset_local_path, '..', '.git')):
        # checkout was not done via git
        return

    if type(config.moduleset) == type([]):
        modulesets = config.moduleset
    else:
        modulesets = [ config.moduleset ]

    if not [x for x in modulesets if x.find('/') == -1]:
        # all modulesets have a slash; they are URI
        return

    try:
        git_diff = get_output(['git', 'diff', 'origin/master', '--', '.'],
                cwd=moduleset_local_path).strip()
    except CommandError:
        # git error, ignore
        return

    if not git_diff:
        # no locally modified moduleset
        return

    logging.info(
            _('Modulesets were edited locally but JHBuild is configured '\
              'to get them from the network, perhaps you need to add '\
              'use_local_modulesets = True to your .jhbuildrc.'))

