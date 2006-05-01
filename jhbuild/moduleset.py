# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
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

import os
import sys
import urlparse

from jhbuild.errors import UsageError, FatalError

try:
    import xml.dom.minidom
except ImportError:
    raise FatalError('Python xml packages are required but could not be found')

from jhbuild import modtypes
from jhbuild.versioncontrol import get_repo_type
from jhbuild.utils import httpcache

__all__ = [ 'load' ]

class ModuleSet:
    def __init__(self):
        self.modules = {}
    def add(self, module):
        '''add a Module object to this set of modules'''
        self.modules[module.name] = module

    # functions for handling dep expansion
    def __expand_mod_list(self, modlist, skip):
        '''expands a list of names to a list of Module objects.  Expands
        dependencies.  Does not handle loops in deps''' #"
        ret = [self.modules[modname]
                   for modname in modlist
                       if modname not in skip]
        i = 0
        while i < len(ret):
            depadd = []
            for depmod in [self.modules[modname]
                               for modname in ret[i].dependencies]:
                if depmod not in ret[:i+1] and depmod.name not in skip:
                    depadd.append(depmod)
            if depadd:
                ret[i:i] = depadd
            else:
                i = i + 1
        i = 0
        while i < len(ret):
            if ret[i] in ret[:i]:
                del ret[i]
            else:
                i = i + 1
        return ret

    def get_module_list(self, seed, skip=[]):
        '''gets a list of module objects (in correct dependency order)
        needed to build the modules in the seed list''' #"

        if seed == 'all': seed = self.modules.keys()
        # we don't just use a simple list comprehension here, since we
        # want to control the exception message.
        ret = []
        for modname in seed:
            if modname not in skip:
                if self.modules.has_key(modname):
                    ret.append(self.modules[modname])
                else:
                    raise UsageError('module "%s" not found' % modname)
        # expand dependencies
        i = 0
        while i < len(ret):
            depadd = []
            for modname in ret[i].dependencies:
                if self.modules.has_key(modname):
                    depmod = self.modules[modname]
                else:
                    raise UsageError('dependent module "%s" not found'
                                     % modname)
                if depmod not in ret[:i+1] and depmod.name not in skip:
                    depadd.append(depmod)
            if depadd:
                ret[i:i] = depadd
            else:
                i = i + 1
        # and now suggestions.
        i = 0
        while i < len(ret):
            depadd = []
            for modname in ret[i].dependencies + ret[i].suggests:
                if self.modules.has_key(modname):
                    depmod = self.modules[modname]
                else:
                    continue # don't care about unknown suggestions
                if depmod in ret and depmod not in ret[:i+1]:
                    depadd.append(depmod)
            if depadd:
                ret[i:i] = depadd
            else:
                i = i + 1
        # remove duplicates
        i = 0
        while i < len(ret):
            if ret[i] in ret[:i]:
                del ret[i]
            else:
                i = i + 1
        return ret
    
    def get_full_module_list(self, skip=[]):
        return self.get_module_list(self.modules.keys(), skip=skip)
    
    def write_dot(self, modules=None, fp=sys.stdout):
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
            mod = self.modules[modname]
            if isinstance(mod, modtypes.base.CVSModule):
                label = mod.cvsmodule
                if mod.revision:
                    label = label + '\\nrv: ' + mod.revision
                attrs = '[color="lightskyblue",style="filled",label="%s"]' % \
                        label
            elif isinstance(mod, modtypes.base.MetaModule):
                attrs = '[color="lightcoral",style="filled",' \
                        'label="%s"]' % mod.name
            elif isinstance(mod, modtypes.tarball.Tarball):
                attrs = '[color="lightgoldenrod",style="filled",' \
                        'label="%s\\n%s"]' % (mod.name, mod.version)
            fp.write('  "%s" %s;\n' % (modname, attrs))
            del modules[0]
            
            for dep in self.modules[modname].dependencies:
                fp.write('  "%s" -> "%s";\n' % (modname, dep))
                if not inlist.has_key(dep):
                    modules.append(dep)
                inlist[dep] = None
        fp.write('}\n')

def load(config, uri=None):
    if uri is not None:
        modulesets = [ uri ]
    elif type(config.moduleset) == type([]):
        modulesets = config.moduleset
    else:
        modulesets = [ config.moduleset ]
    ms = ModuleSet()
    for uri in modulesets:
        if '/' not in uri:
            uri = os.path.join(os.path.dirname(__file__), '..', 'modulesets',
                               uri + '.modules')
        ms.modules.update(_parse_module_set(config, uri).modules)
    return ms

def _parse_module_set(config, uri):
    try:
        filename = httpcache.load(uri, nonetwork=config.nonetwork)
    except Exception, e:
        raise FatalError('could not download %s: %s' % (uri, str(e)))
    document = xml.dom.minidom.parse(filename)

    assert document.documentElement.nodeName == 'moduleset'
    moduleset = ModuleSet()

    # load up list of repositories
    repositories = {}
    default_repo = None
    for node in document.documentElement.childNodes:
        if node.nodeType != node.ELEMENT_NODE: continue
        if node.nodeName == 'repository':
            repo_type = node.getAttribute('type')
            name = node.getAttribute('name')
            if node.getAttribute('default') == 'yes':
                default_repo = name
            repo = get_repo_type(repo_type)
            kws = {}
            for attr in repo.init_xml_attrs:
                if node.hasAttribute(attr):
                    kws[attr] = node.getAttribute(attr)
            repo_class = get_repo_type(repo_type)
            repositories[name] = repo_class(config, name, **kws)
        if node.nodeName == 'cvsroot':
            name = node.getAttribute('name')
            if node.getAttribute('default') == 'yes':
                default_repo = name
            cvsroot = node.getAttribute('root')
            if node.hasAttribute('password'):
                password = node.getAttribute('password')
            else:
                password = None
            repo_type = get_repo_type('cvs')
            repositories[name] = repo_type(config, name,
                                           cvsroot=cvsroot, password=password)
        elif node.nodeName == 'svnroot':
            name = node.getAttribute('name')
            if node.getAttribute('default') == 'yes':
                default_repo = name
            svnroot = node.getAttribute('href')
            repo_type = get_repo_type('svn')
            repositories[name] = repo_type(config, name, href=svnroot)
        elif node.nodeName == 'arch-archive':
            name = node.getAttribute('name')
            if node.getAttribute('default') == 'yes':
                default_repo = name
            archive = name
            archive_uri = node.getAttribute('href')
            repo_type = get_repo_type('arch')
            repositories[name] = repo_type(config, name, archive, archive_uri)

    # and now module definitions
    for node in document.documentElement.childNodes:
        if node.nodeType != node.ELEMENT_NODE: continue
        if node.nodeName == 'include':
            href = node.getAttribute('href')
            inc_uri = urlparse.urljoin(uri, href)
            inc_moduleset = _parse_module_set(config, inc_uri)
            moduleset.modules.update(inc_moduleset.modules)
        elif node.nodeName in ['repository', 'cvsroot', 'svnroot', 'arch-archive']:
            pass
        else:
            # only one default root in the file.  Is this a good thing?
            if node.hasAttribute('cvsroot'):
                repo = repositories[node.getAttribute('cvsroot')]
            elif node.hasAttribute('root'):
                repo = repositories[node.getAttribute('root')]
            elif node.hasAttribute('repo'):
                repo = repositories[node.getAttribute('repo')]
            else:
                repo = repositories.get(default_repo, None)

            # deps
            dependencies = []
            suggests = []
            for childnode in node.childNodes:
                if childnode.nodeType != childnode.ELEMENT_NODE: continue
                if childnode.nodeName == 'dependencies':
                    for dep in childnode.childNodes:
                        if dep.nodeType == dep.ELEMENT_NODE:
                            assert dep.nodeName == 'dep'
                            dependencies.append(dep.getAttribute('package'))
                elif childnode.nodeName == 'suggests':
                    for dep in childnode.childNodes:
                        if dep.nodeType == dep.ELEMENT_NODE:
                            assert dep.nodeName == 'dep'
                            suggests.append(dep.getAttribute('package'))

            moduleset.add(modtypes.parse_xml_node(node, config,
                                                  dependencies, suggests,
                                                  repo))


    return moduleset
