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
from jhbuild.utils.sxml import sxml

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
        raise FatalError(_('unknown module type %s') % node.nodeName)

    parser = _module_types[node.nodeName]
    return parser(node, config, uri, repositories, default_repo)

def get_dependencies(node):
    """Scan for dependencies in <dependencies>, <suggests> and <after> elements."""
    dependencies = []
    after = []
    suggests = []

    def add_to_list(list, childnode):
        for dep in childnode.childNodes:
            if dep.nodeType == dep.ELEMENT_NODE and dep.nodeName == 'dep':
                package = dep.getAttribute('package')
                if not package:
                    raise FatalError(_('dep node for module %s is missing package attribute') % \
                            node.getAttribute('id'))
                list.append(package)

    for childnode in node.childNodes:
        if childnode.nodeType != childnode.ELEMENT_NODE: continue
        if childnode.nodeName == 'dependencies':
            add_to_list(dependencies, childnode)
        elif childnode.nodeName == 'suggests':
            add_to_list(suggests, childnode)
        elif childnode.nodeName == 'after':
            add_to_list(after, childnode)

    return dependencies, after, suggests

def get_branch(node, repositories, default_repo, config):
    """Scan for a <branch> element and create a corresponding Branch object."""
    name = node.getAttribute('id')
    for childnode in node.childNodes:
        if (childnode.nodeType == childnode.ELEMENT_NODE and
            childnode.nodeName == 'branch'):
            break
    else:
        raise FatalError(_('no <branch> element found for %s') % name)

    # look up the repository for this branch ...
    if childnode.hasAttribute('repo'):
        try:
            repo = repositories[childnode.getAttribute('repo')]
        except KeyError:
            raise FatalError(_('Repository=%s not found for module id=%s. Possible repositories are %s' )
                             % (childnode.getAttribute('repo'), name, repositories))
    else:
        try:
            repo = repositories[default_repo]
        except KeyError:
            raise FatalError(_('Default Repository=%s not found for module id=%s. Possible repositories are %s')
                             % (default_repo, name, repositories))

    if repo.mirrors:
        mirror_type = config.mirror_policy
        if name in config.module_mirror_policy:
            mirror_type = config.module_mirror_policy[name]
        if mirror_type in repo.mirrors:
            repo = repo.mirrors[mirror_type]

    return repo.branch_from_xml(name, childnode, repositories, default_repo)


class SkipToState(Exception):
    def __init__(self, state):
        Exception.__init__(self)
        self.state = state


class Package:
    type = 'base'
    STATE_START = 'start'
    STATE_DONE  = 'done'
    def __init__(self, name, dependencies = [], after = [], suggests = []):
        self.name = name
        self.dependencies = dependencies
        self.after = after
        self.suggests = suggests
        self.tags = []
        self.moduleset_name = None

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.name)

    def get_extra_env(self):
        return self.config.module_extra_env.get(self.name)
    extra_env = property(get_extra_env)

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

            skip_method = getattr(self, 'skip_' + state)
            try:
                if skip_method(buildscript, last_state):
                    state = do_method.next_state
                    assert state not in seen_states, (
                        'state %s should not appear in list of '
                        'skipped states: %r' % (state, seen_states))
                else:
                    return state
            except SkipToState, e:
                return e.state

    def run_state(self, buildscript, state):
        """run a particular part of the build for this package.

        Returns a tuple of the following form:
          (next-state, error-flag, [other-states])
        """
        method = getattr(self, 'do_' + state)
        try:
            method(buildscript)
        except SkipToState, e:
            return (e.state, None, None)
        except (CommandError, BuildStateError), e:
            return (self._next_state(buildscript, state),
                    e, method.error_states)
        else:
            return (self._next_state(buildscript, state), None, None)

    def check_build_policy(self, buildscript):
        if not buildscript.config.build_policy in ('updated', 'updated-deps'):
            return
        if not buildscript.packagedb.check(self.name, self.get_revision() or ''):
            # package has not been updated
            return

        # module has not been updated
        if buildscript.config.build_policy == 'updated':
            buildscript.message(_('Skipping %s (not updated)') % self.name)
            return self.STATE_DONE

        if buildscript.config.build_policy == 'updated-deps':
            install_date = buildscript.packagedb.installdate(self.name)
            for dep in self.dependencies:
                install_date_dep = buildscript.packagedb.installdate(dep)
                if install_date_dep > install_date:
                    # a dependency has been updated
                    return None
            else:
                buildscript.message(
                        _('Skipping %s (package and dependencies not updated)') % self.name)
                return self.STATE_DONE

    def checkout(self, buildscript):
        srcdir = self.get_srcdir(buildscript)
        buildscript.set_action(_('Checking out'), self)
        self.branch.checkout(buildscript)
        # did the checkout succeed?
        if not os.path.exists(srcdir):
            raise BuildStateError(_('source directory %s was not created') % srcdir)

        if self.check_build_policy(buildscript) == self.STATE_DONE:
            raise SkipToState(self.STATE_DONE)

    def skip_checkout(self, buildscript, last_state):
        # skip the checkout stage if the nonetwork flag is set
        if buildscript.config.nonetwork:
            if self.check_build_policy(buildscript) == self.STATE_DONE:
                raise SkipToState(self.STATE_DONE)
            return True
        return False

    def xml_tag_and_attrs(self):
        """Return a (tag, attrs) pair, describing how to serialize this
        module.

        "attrs" is expected to be a list of (xmlattrname, pyattrname,
        default) tuples. The xmlattr will be serialized iff
        getattr(self, pyattrname) != default. See AutogenModule for an
        example."""
        raise NotImplementedError

    def to_sxml(self):
        """Serialize this module as sxml.

        By default, calls sxml_tag_and_attrs() to get the tag name and
        attributes, serializing those attribute values that are
        different from their defaults, and embedding the dependencies
        and checkout branch. You may however override this method to
        implement a different behavior."""
        tag, attrs = self.xml_tag_and_attrs()
        xmlattrs = {}
        for xmlattr, pyattr, default in attrs:
            val = getattr(self, pyattr)
            if val != default:
                if type(val) == bool:
                    val = val and 'true' or 'no'
                xmlattrs[xmlattr] = val
        return [getattr(sxml, tag)(**xmlattrs), self.deps_to_sxml(),
                self.branch_to_sxml()]

    def deps_to_sxml(self):
        """Serialize this module's dependencies as sxml."""
        return ([sxml.dependencies]
                + [[sxml.dep(package=d)] for d in self.dependencies])

    def branch_to_sxml(self):
        """Serialize this module's checkout branch as sxml."""
        return self.branch.to_sxml()


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

    def to_sxml(self):
        return [sxml.metamodule(id=self.name),
                [sxml.dependencies]
                + [[sxml.dep(package=d)] for d in self.dependencies]]


def parse_metamodule(node, config, url, repos, default_repo):
    id = node.getAttribute('id')
    dependencies, after, suggests = get_dependencies(node)
    return MetaModule(id, dependencies=dependencies, after=after, suggests=suggests)
register_module_type('metamodule', parse_metamodule)


register_lazy_module_type('autotools', 'jhbuild.modtypes.autotools')
register_lazy_module_type('cvsmodule', 'jhbuild.modtypes.autotools')
register_lazy_module_type('svnmodule', 'jhbuild.modtypes.autotools')
register_lazy_module_type('archmodule', 'jhbuild.modtypes.autotools')
