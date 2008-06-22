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

from jhbuild.errors import UsageError, FatalError, DependencyCycleError

try:
    import xml.dom.minidom
except ImportError:
    raise FatalError(_('Python xml packages are required but could not be found'))

from jhbuild import modtypes
from jhbuild.versioncontrol import get_repo_type
from jhbuild.utils import httpcache

__all__ = ['load', 'load_tests']

class ModuleSet:
    def __init__(self, config = None):
        self.config = config
        self.modules = {}
    def add(self, module):
        '''add a Module object to this set of modules'''
        self.modules[module.name] = module

    def get_module(self, module_name, ignore_case = False):
        if self.modules.has_key(module_name) or not ignore_case:
            return self.modules[module_name]
        module_name = module_name.lower()
        for module in self.modules.keys():
            if module.lower() == module_name:
                if self.config is None or not self.config.quiet_mode:
                    print >> sys.stderr, uencode(
                            _('I: fixed case of module \'%(orig)s\' to \'%(new)s\'') % {
                            'orig': module_name, 'new': module})
                return self.modules[module]
        raise KeyError()

    def get_module_list(self, seed, skip=[], tags=[], ignore_cycles = False,
                include_optional_modules = False):
        '''gets a list of module objects (in correct dependency order)
        needed to build the modules in the seed list'''

        if seed == 'all': seed = self.modules.keys()
        try:
            all_modules = [self.get_module(mod, ignore_case = True) for mod in seed if mod not in skip]
        except KeyError, e:
            raise UsageError(_('module "%s" not found') % str(e))

        asked_modules = all_modules[:]

        # 1st: get all modules that will be needed
        # note this is only needed to skip "after" modules that would not
        # otherwise be built
        i = 0
        while i < len(all_modules):
            for modname in all_modules[i].dependencies:
                depmod = self.modules.get(modname)
                if not depmod:
                    raise UsageError(_('dependent module "%s" not found') % modname)
                if not depmod in all_modules:
                    all_modules.append(depmod)

            # suggests can be ignored if not in moduleset
            for modname in all_modules[i].suggests:
                depmod = self.modules.get(modname)
                if not depmod:
                    continue
                if not depmod in all_modules:
                    all_modules.append(depmod)
            i += 1

        # 2nd: order them, raise an exception on hard dependency cycle, ignore
        # them for soft dependencies
        ordered = []
        state = {}

        for modname in skip:
            # mark skipped modules as already processed
            state[self.modules.get(modname)] = 'processed'

        if tags:
            for modname in self.modules:
                for tag in tags:
                    if tag in self.modules[modname].tags:
                        break
                else:
                    # no tag matched, mark module as processed
                    state[self.modules[modname]] = 'processed'

        def order(modules, module, mode = 'dependencies'):
            if state.get(module, 'clean') == 'processed':
                # already seen
                return
            if state.get(module, 'clean') == 'in-progress':
                # dependency circle, abort when processing hard dependencies
                if mode == 'dependencies' and not ignore_cycles:
                    raise DependencyCycleError()
                else:
                    state[module] = 'in-progress'
                    return
            state[module] = 'in-progress'
            for modname in module.dependencies:
                depmod = self.modules[modname]
                order([self.modules[x] for x in depmod.dependencies], depmod, mode)
            for modname in module.suggests:
                depmod = self.modules.get(modname)
                if not depmod:
                    continue
                order([self.modules[x] for x in depmod.dependencies], depmod, 'suggests')
            for modname in module.after:
                depmod = self.modules.get(modname)
                if not depmod in all_modules and not include_optional_modules:
                    # skipping modules that would not be built otherwise
                    # (build_optional_modules being the argument to force them
                    # to be included nevertheless)
                    continue
                if not depmod:
                    continue
                order([self.modules[x] for x in depmod.dependencies], depmod, 'after')
            state[module] = 'processed'
            ordered.append(module)

        for i, module in enumerate(all_modules):
            order([], module)
            if i+1 == len(asked_modules): 
                break

        return ordered
    
    def get_full_module_list(self, skip=[], ignore_cycles=False):
        return self.get_module_list(self.modules.keys(), skip=skip,
                ignore_cycles=ignore_cycles)

    def get_test_module_list (self, seed, skip=[]):
        test_modules = []
        if seed == []:
            return
        for mod in self.modules.values():
            for test_app in seed:
                if test_app in mod.tested_pkgs:
                    test_modules.append(mod)
        return test_modules
    
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
                print >> sys.stderr, _('W: Unknown module:'), modname
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
    elif type(config.moduleset) == type([]):
        modulesets = config.moduleset
    else:
        modulesets = [ config.moduleset ]
    ms = ModuleSet(config = config)
    for uri in modulesets:
        if '/' not in uri:
            uri = os.path.join(os.path.dirname(__file__), '..', 'modulesets',
                               uri + '.modules')
        ms.modules.update(_parse_module_set(config, uri).modules)
    return ms

def load_tests (config, uri=None):
    ms = load (config, uri)
    ms_tests = ModuleSet(config = config)
    for app, module in ms.modules.iteritems():
        if module.__class__ == testmodule.TestModule:
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
        filename = httpcache.load(uri, nonetwork=config.nonetwork)
    except Exception, e:
        raise FatalError(_('could not download %s: %s') % (uri, str(e)))
    filename = os.path.normpath(filename)
    try:
        document = xml.dom.minidom.parse(filename)
    except xml.parsers.expat.ExpatError, e:
        raise FatalError(_('failed to parse %s: %s') % (filename, str(e)))

    assert document.documentElement.nodeName == 'moduleset'
    moduleset = ModuleSet(config = config)
    moduleset_name = document.documentElement.getAttribute('name')
    if not moduleset_name and uri.endswith('.modules'):
        moduleset_name = os.path.basename(uri)[:-len('.modules')]    

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
            repositories[name] = repo_class(config, name, **kws)
            repositories[name].moduleset_uri = uri
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
            moduleset.add(module)

    return moduleset
