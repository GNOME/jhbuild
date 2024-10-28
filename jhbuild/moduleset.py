# jhbuild - a tool to ease building collections of source packages
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

import fnmatch
import os
import sys
import logging
from urllib.parse import urlparse, urljoin
import xml.dom.minidom
import xml.parsers.expat

from jhbuild.utils import _
from jhbuild.errors import UsageError, FatalError, \
             CommandError, UndefinedRepositoryError
from jhbuild import modtypes
from jhbuild.versioncontrol import get_repo_type
from jhbuild.utils import httpcache
from jhbuild.utils import packagedb
from jhbuild.utils.cmds import compare_version, get_output
from jhbuild.modtypes.testmodule import TestModule
from jhbuild.modtypes.systemmodule import SystemModule
from jhbuild.versioncontrol.tarball import TarballBranch
from jhbuild.versioncontrol.git import GitBranch
from jhbuild.utils import systeminstall
from jhbuild.utils import fileutils

__all__ = ['load', 'load_tests', 'get_default_repo']

virtual_sysdeps = [
    'automake',
    'bzr',
    'cmake',
    'cvs',
    'git',
    'gmake',
    'hg',
    'libtool',
    'make',
    'ninja',
    'pkg-config',
    'svn',
    'xmlcatalog'
]

_default_repo = None
def get_default_repo():
    return _default_repo

class ModuleSet:
    def __init__(self, config = None, db=None):
        self.config = config
        self.modules = {}
        self.raise_exception_on_warning=False

        if db is None:
            legacy_pkgdb_path = os.path.join(self.config.prefix, 'share', 'jhbuild', 'packagedb.xml')
            new_pkgdb_path = os.path.join(self.config.top_builddir, 'packagedb.xml')
            if os.path.isfile(legacy_pkgdb_path):
                fileutils.rename(legacy_pkgdb_path, new_pkgdb_path)
            self.packagedb = packagedb.PackageDB(new_pkgdb_path, config)
        else:
            self.packagedb = db

    def add(self, module):
        '''add a Module object to this set of modules'''
        self.modules[module.name] = module

    def get_module(self, module_name, ignore_case = False):
        module_name = module_name.rstrip(os.sep)
        if module_name in self.modules or not ignore_case:
            return self.modules[module_name]
        module_name_lower = module_name.lower()
        for module in self.modules.keys():
            if module.lower() == module_name_lower:
                logging.info(_('fixed case of module \'%(orig)s\' to '
                               '\'%(new)s\'') % {'orig': module_name,
                                                 'new': module})
                return self.modules[module]
        raise KeyError(module_name)

    def get_module_list(self, module_names, skip=[], tags=[],
                        include_suggests=True, include_afters=False):
        module_list = self.get_full_module_list(module_names, skip,
                                                include_suggests,
                                                include_afters)
        module_list = self.remove_system_modules(module_list)
        module_list = self.remove_tag_modules(module_list, tags)
        return module_list

    def get_full_module_list(self, module_names='all', skip=[],
                             include_suggests=True, include_afters=False,
                             warn_about_circular_dependencies=True):

        def skip_module(module):
            # '*' has special meaning which overrides any other values
            if skip and '*' not in skip:
                if any(fnmatch.fnmatch(module, exp) for exp in skip):
                    return True
            return False

        def dep_resolve(node, resolved, seen, after):
            ''' Recursive depth-first search of the dependency tree. Creates
            the build order into the list 'resolved'. <after/> modules are
            added to the dependency tree but flagged. When search finished
            <after/> modules not a real dependency are removed.
            '''
            circular = False
            seen.append(node)
            if include_suggests:
                edges = node.dependencies + node.suggests + node.after
            else:
                edges = node.dependencies + node.after
            # do not include <after> modules because a previous visited <after>
            # module may later be a hard dependency
            resolved_deps = [module for module, after_module in resolved \
                             if not after_module]
            for edge_name in edges:
                edge = self.modules.get(edge_name)
                if edge is None:
                    if node not in [i[0] for i in resolved]:
                        self._warn(_('%(module)s has a dependency on unknown'
                                     ' "%(invalid)s" module') % \
                                   {'module'  : node.name,
                                    'invalid' : edge_name})
                elif not skip_module(edge_name) and edge not in resolved_deps:
                    if edge in seen:
                        # circular dependency detected
                        circular = True
                        if self.raise_exception_on_warning:
                            # Translation of string not required - used in
                            # unit tests only
                            raise UsageError('Circular dependencies detected')
                        if warn_about_circular_dependencies:
                            self._warn(_('Circular dependencies detected: %s') \
                                       % ' -> '.join([i.name for i in seen] \
                                                     + [edge.name]))
                        break
                    else:
                        if edge_name in node.after:
                            dep_resolve(edge, resolved, seen, True)
                        elif edge_name in node.suggests:
                            dep_resolve(edge, resolved, seen, after)
                        elif edge_name in node.dependencies:
                            dep_resolve(edge, resolved, seen, after)
                            # hard dependency may be missed if a cyclic
                            # dependency. Add it:
                            if edge not in [i[0] for i in resolved]:
                                resolved.append((edge, after))

            seen.remove(node)

            if not circular:
                if node not in [i[0] for i in resolved]:
                    resolved.append((node, after))
                elif not after:
                    # a dependency exists for an after, flag to keep
                    for index, item in enumerate(resolved):
                        if item[1] is True and item[0] == node:
                            resolved[index] = (node, False)

        config_modules = getattr(self.config, 'modules', [])

        if module_names == 'all':
            module_names = self.modules.keys()
        try:
            modules = [self.get_module(module, ignore_case = True) \
                       for module in module_names \
                       if module in config_modules or not skip_module(module)]
        except KeyError as e:
            raise UsageError(_("A module called '%s' could not be found.") % e)

        resolved = []
        for module in modules:
            dep_resolve(module, resolved, [], False)

        if include_afters:
            module_list = [module[0] for module in resolved]
        else:
            module_list = [module for module, after_module in resolved \
                           if not after_module]

        if '*' in skip:
            module_list = [module for module in module_list \
                           if module.name in config_modules]

        return module_list

    def get_test_module_list (self, seed, skip=[]):
        test_modules = []
        if seed == []:
            return
        for mod in self.modules.values():
            for test_app in seed:
                if test_app in mod.tested_pkgs:
                    test_modules.append(mod)
        return test_modules

    def get_module_state(self, modules):
        installed_pkgconfig = systeminstall.get_installed_pkgconfigs(self.config)
        
        module_state = {}
        for module in modules:
            # only consider SystemModules or tarball and git branches with <pkg-config>
            if (isinstance(module, SystemModule) or
                (isinstance(module.branch, (TarballBranch, GitBranch)) and
                 module.pkg_config is not None)):
                required_version = module.branch.version
                installed_version = None
                new_enough = False
                systemmodule = isinstance(module, SystemModule)
                if module.pkg_config is not None:
                    # strip off the .pc
                    module_pkg = module.pkg_config[:-3]
                    if module_pkg in installed_pkgconfig:
                        installed_version = installed_pkgconfig[module_pkg]
                        if required_version is None:
                            new_enough = True
                        else:
                            new_enough = compare_version(installed_version,
                                                         required_version)
                elif systemmodule:
                    new_enough = systeminstall.systemdependencies_met \
                                     (module.name, module.systemdependencies,
                                      self.config)
                    if new_enough:
                        installed_version = 'unknown'
                module_state[module] = (required_version, installed_version,
                                        new_enough, systemmodule)
        return module_state

    def remove_system_modules(self, modules):
        if not self.config.partial_build:
            return [module for module in modules \
                    if not isinstance(module, SystemModule)]

        return_list = []

        installed_pkgconfig = systeminstall.get_installed_pkgconfigs(self.config)

        for module in modules:
            if isinstance(module, SystemModule):
                continue
            skip = False

            if (isinstance(module.branch, (TarballBranch, GitBranch)) and
                    module.pkg_config is not None):
                # Strip off the .pc
                module_pkg = module.pkg_config[:-3]
                required_version = module.branch.version
                if required_version and module_pkg in installed_pkgconfig:
                    installed_version = installed_pkgconfig[module_pkg]
                    skip = compare_version(installed_version, required_version)
            if not skip:
                return_list.append(module)
        return return_list

    def remove_tag_modules(self, modules, tags):
        if tags:
            return_list = []
            for module in modules:
                for tag in tags:
                    if tag in self.modules[module.name].tags:
                        return_list.append(module)
            return return_list
        else:
            return modules

    def write_dot(self, modules=None, fp=sys.stdout, suggests=False, clusters=False):
        from jhbuild.modtypes import MetaModule
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
            elif isinstance(mod, SystemModule):
                label = mod.name
                if mod.branch.version:
                    label += '\\n(%s)' % mod.branch.version
                attrs = '[color="palegreen",style="filled",label="%s"]' % label
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
                if dep not in inlist:
                    modules.append(dep)
                inlist[dep] = None

            if suggests:
                for dep in self.modules[modname].after + self.modules[modname].suggests:
                    if dep in self.modules:
                        fp.write('  "%s" -> "%s" [style=dotted];\n' % (modname, dep))
                        if dep not in inlist:
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

    def _warn(self, msg):
        if self.raise_exception_on_warning:
            raise UsageError(msg)
        else:
            logging.warning(msg)


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
        elif not urlparse(uri)[0]:
            uri = 'https://gitlab.gnome.org/GNOME/jhbuild/raw/master/modulesets' \
                  '/%s.modules' % uri
        ms.modules.update(_parse_module_set(config, uri).modules)

    # create virtual sysdeps
    system_repo_class = get_repo_type('system')
    virtual_repo = system_repo_class(config, 'virtual-sysdeps')
    virtual_branch = virtual_repo.branch('virtual-sysdeps') # just reuse this
    for name in virtual_sysdeps:
        # don't override it if it's already there
        if name in ms.modules:
            continue

        virtual = SystemModule.create_virtual(name, virtual_branch, 'path', name)
        ms.add(virtual)

    return ms

def load_tests (config, uri=None):
    ms = load (config, uri)
    ms_tests = ModuleSet(config = config)
    for app, module in ms.modules.items():
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

def _handle_conditions(config, element):
    """
    If we encounter an <if> tag, consult the conditions set in the config
    in order to decide if we should include its content or not.  If the
    condition is met, the child elements are added to the parent of the
    <if/> tag as if the condition tag were not there at all.  If the
    condition is not met, the entire content is simply dropped.

    We do the processing as a transformation on the DOM as a whole,
    immediately after parsing the moduleset XML, before doing any additional
    processing.  This allows <if> to be used for anything and it means we
    don't need to deal with it separately from each place.

    Although the tool itself will accept <if> anywhere we use the schemas to
    restrict its use to the purposes of conditionalising dependencies
    (including suggests) and {autogen,make,makeinstall}args.
    """

    for condition_tag in _child_elements_matching(element, ['if']):
        # In all cases, we remove the element from the parent
        element.childNodes.remove(condition_tag)

        # grab the condition from the attributes
        c_if = condition_tag.getAttribute('condition-set')
        c_unless = condition_tag.getAttribute('condition-unset')

        if (not c_if) == (not c_unless):
            raise FatalError(_("<if> must have exactly one of condition-set='' or condition-unset=''"))

        # check the condition
        condition_true = ((c_if and c_if in config.conditions) or
                          (c_unless and c_unless not in config.conditions))

        if condition_true:
            # add the child elements of <condition> back into the parent
            for condition_child in _child_elements(condition_tag):
                element.childNodes.append(condition_child)

    # now, recurse
    for c in _child_elements(element):
        _handle_conditions(config, c)

def _parse_module_set(config, uri):
    try:
        filename = httpcache.load(uri, nonetwork=config.nonetwork, age=0)
    except Exception as e:
        raise FatalError(_('could not download %s: %s') % (uri, e))
    filename = os.path.normpath(filename)
    try:
        document = xml.dom.minidom.parse(filename)
    except IOError as e:
        raise FatalError(_('failed to parse %s: %s') % (filename, e))
    except xml.parsers.expat.ExpatError as e:
        raise FatalError(_('failed to parse %s: %s') % (uri, e))

    assert document.documentElement.nodeName == 'moduleset'

    for node in _child_elements_matching(document.documentElement, ['redirect']):
        new_url = node.getAttribute('href')
        logging.info('moduleset is now located at %s', new_url)
        return _parse_module_set(config, new_url)

    _handle_conditions(config, document.documentElement)

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
                # mirrors[mirror_type].moduleset_uri = uri
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
            inc_uri = urljoin(uri, href)
            try:
                inc_moduleset = _parse_module_set(config, inc_uri)
            except UndefinedRepositoryError:
                raise
            except FatalError as e:
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

    if isinstance(config.moduleset, list):
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
              'use_local_modulesets = True to your %s.' % config.filename))

