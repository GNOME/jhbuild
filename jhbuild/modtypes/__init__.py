# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   __init__.py: package to hold module type defintions
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

__metaclass__ = type

__all__ = [
    'register_module_type',
    'parse_xml_node',
    'Package',
    'get_dependencies'
    'get_branch'
    ]

import os

from jhbuild.errors import FatalError, CommandError, BuildStateError

_module_types = {}
def register_module_type(name, parse_func):
    _module_types[name] = parse_func

def register_lazy_module_type(name, module):
    def parse_func(node, config, uri, repositories, default_repo):
        old_func = _module_types[name]
        mod = __import__(module)
        assert _module_types[name] != old_func, (
            'module did not register new parser_func for %s' % name)
        return _module_types[name](node, config, uri, repositories, default_repo)
    _module_types[name] = parse_func

def parse_xml_node(node, config, uri, repositories, default_repo):
    if not _module_types.has_key(node.nodeName):
        try:
            __import__('jhbuild.modtypes.%s' % node.nodeName)
        except ImportError:
            pass
    if not _module_types.has_key(node.nodeName):
        raise FatalError('unknown module type %s' % node.nodeName)

    parser = _module_types[node.nodeName]
    return parser(node, config, uri, repositories, default_repo)

def get_dependencies(node):
    """Scan for dependencies in <dependencies>, <suggests> and <after> elements."""
    dependencies = []
    after = []
    suggests = []
    for childnode in node.childNodes:
        if childnode.nodeType != childnode.ELEMENT_NODE: continue
        if childnode.nodeName == 'dependencies':
            for dep in childnode.childNodes:
                if dep.nodeType == dep.ELEMENT_NODE and dep.nodeName == 'dep':
                    dependencies.append(dep.getAttribute('package'))
        elif childnode.nodeName == 'suggests':
            for dep in childnode.childNodes:
                if dep.nodeType == dep.ELEMENT_NODE and dep.nodeName == 'dep':
                    suggests.append(dep.getAttribute('package'))
        elif childnode.nodeName == 'after':
            for dep in childnode.childNodes:
                if dep.nodeType == dep.ELEMENT_NODE and dep.nodeName == 'dep':
                    after.append(dep.getAttribute('package'))
    return dependencies, after, suggests

def get_branch(node, repositories, default_repo):
    """Scan for a <branch> element and create a corresponding Branch object."""
    name = node.getAttribute('id')
    for childnode in node.childNodes:
        if (childnode.nodeType == childnode.ELEMENT_NODE and
            childnode.nodeName == 'branch'):
            break
    else:
        raise FatalError('no <branch> element found for %s' % name)

    # look up the repository for this branch ...
    if childnode.hasAttribute('repo'):
        try:
            repo = repositories[childnode.getAttribute('repo')]
        except KeyError:
            raise FatalError('Repository=%s not found for module id=%s. Possible repositories are %s' % (childnode.getAttribute('repo'), name, repositories))
    else:
        try:
            repo = repositories[default_repo]
        except KeyError:
            raise FatalError('Default Repository=%s not found for module id=%s. Possible repositories are %s' % (default_repo, name, repositories))

    return repo.branch_from_xml(name, childnode, repositories, default_repo)

def checkout(package, buildscript):
    srcdir = package.get_srcdir(buildscript)
    builddir = package.get_builddir(buildscript)
    buildscript.set_action('Checking out', package)
    package.branch.checkout(buildscript)
    # did the checkout succeed?
    if not os.path.exists(srcdir):
        raise BuildStateError('source directory %s was not created'
                              % srcdir)

def check_build_policy(package, buildscript):
    if buildscript.config.force_policy:
        return
    if buildscript.config.build_policy in ('updated', 'updated-deps'):
        # has this module been updated ?
        if buildscript.packagedb.check(package.name, package.get_revision() or ''):
            # module has not been updated
            if buildscript.config.build_policy == 'updated':
                buildscript.message('Skipping %s (not updated)' % package.name)
                raise SkipToState(Package.STATE_DONE)
            elif buildscript.config.build_policy == 'updated-deps':
                install_date = buildscript.packagedb.installdate(package.name)
                for dep in package.dependencies:
                    install_date_dep = buildscript.packagedb.installdate(dep)
                    if install_date_dep > install_date:
                        break
                else:
                    buildscript.message(
                            'Skipping %s (package and dependencies not updated)' % package.name)
                    raise SkipToState(Package.STATE_DONE)


class SkipToState(Exception):
    def __init__(self, state):
        Exception.__init__(self)
        self.state = state


class Package:
    type = 'base'
    STATE_START = 'start'
    STATE_DONE  = 'done'
    def __init__(self, name, dependencies=[], after=[], suggests=[]):
        self.name = name
        self.dependencies = dependencies
        self.after = after
        self.suggests = suggests
        self.tags = []

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.name)

    def get_srcdir(self, buildscript):
        raise NotImplementedError
    def get_builddir(self, buildscript):
        raise NotImplementedError

    def get_revision(self):
        return None

    def _next_state(self, buildscript, last_state):
        """Work out what state to go to next, possibly skipping some states.

        This function executes skip_$state() to decide whether to run that
        state or not.  If it returns True, go to do_$state.next_state and
        repeat.  If it returns False, return that state.
        """
        seen_states = []
        state = getattr(self, 'do_' + last_state).next_state
        while True:
            seen_states.append(state)
            if state == self.STATE_DONE:
                return state
            do_method = getattr(self, 'do_' + state)
            if hasattr(self, 'skip_' + state):
                skip_method = getattr(self, 'skip_' + state)
                if skip_method(buildscript, last_state):
                    state = do_method.next_state
                    assert state not in seen_states, (
                        'state %s should not appear in list of '
                        'skipped states: %r' % (state, seen_states))
                else:
                    return state
            else:
                # no skip rule
                return state

    def run_state(self, buildscript, state):
        """run a particular part of the build for this package.

        Returns a tuple of the following form:
          (next-state, error-flag, [other-states])
        """
        method = getattr(self, 'do_' + state)
        # has the state been updated to the new system?
        if hasattr(method, 'next_state'):
            try:
                method(buildscript)
            except SkipToState, e:
                return (e.state, None, None)
            except (CommandError, BuildStateError), e:
                return (self._next_state(buildscript, state),
                        str(e), method.error_states)
            else:
                return (self._next_state(buildscript, state),
                        None, None)
        else:
            return method(buildscript)


class MetaModule(Package):
    """A simple module type that consists only of dependencies."""
    type = 'meta'
    def get_srcdir(self, buildscript):
        return buildscript.config.checkoutroot
    def get_builddir(self, buildscript):
        return buildscript.config.buildroot or \
               self.get_srcdir(buildscript)

    # nothing to actually build in a metamodule ...
    def do_start(self, buildscript):
        pass
    do_start.next_state = Package.STATE_DONE
    do_start.error_states = []

def parse_metamodule(node, config, url, repos, default_repo):
    id = node.getAttribute('id')
    dependencies, after, suggests = get_dependencies(node)
    return MetaModule(id, dependencies=dependencies, after=after, suggests=suggests)
register_module_type('metamodule', parse_metamodule)


register_lazy_module_type('autotools', 'jhbuild.modtypes.autotools')
register_lazy_module_type('cvsmodule', 'jhbuild.modtypes.autotools')
register_lazy_module_type('svnmodule', 'jhbuild.modtypes.autotools')
register_lazy_module_type('archmodule', 'jhbuild.modtypes.autotools')
