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

try:
    import apt_pkg
except ImportError:
    apt_pkg = None

import os
import re

from jhbuild.errors import FatalError, CommandError, BuildStateError

def lax_int(s):
    try:
        return int(s)
    except ValueError:
        return -1


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
    STATE_APT_GET_UPDATE = 'apt_get_update'
    STATE_BUILD_DEPS     = 'build_deps'
    STATE_DONE  = 'done'
    def __init__(self, name, dependencies = [], after = [], suggests = [],
            extra_env = None):
        self.name = name
        self.dependencies = dependencies
        self.after = after
        self.suggests = suggests
        self.tags = []
        self.moduleset_name = None
        self.extra_env = extra_env

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.name)

    def get_srcdir(self, buildscript):
        raise NotImplementedError
    def get_builddir(self, buildscript):
        raise NotImplementedError

    def get_builddebdir(self, buildscript):
        return os.path.normpath(os.path.join(self.get_builddir(buildscript), '..', 'debian'))

    def get_debian_name(self, buildscript):
        debian_name = buildscript.config.debian_names.get(self.name)
        if not debian_name:
            debian_name = self.name
        return debian_name

    def get_one_binary_package_name(self, buildscript):
        debian_name = self.get_debian_name(buildscript)
        sources = apt_pkg.GetPkgSrcRecords()
        sources.Restart()
        t = []
        while sources.Lookup(debian_name):
            try:
                t.append((sources.Package, sources.Binaries, sources.Version))
            except AttributeError:
                pass
        if not t:
            raise KeyError
        t.sort(lambda x, y: apt_pkg.VersionCompare(x[-1],y[-1]))
        return t[-1][1][0]

    def get_available_debian_version(self, buildscript):
        apt_cache = apt_pkg.GetCache()
        binary_name = self.get_one_binary_package_name(buildscript)
        for pkg in apt_cache.Packages:
            if pkg.Name == binary_name:
                t = list(pkg.VersionList)
                t.sort(lambda x, y: apt_pkg.VersionCompare(x.VerStr, y.VerStr))
                return t[-1].VerStr
        return None

    def get_installed_debian_version(self):
        apt_cache = apt_pkg.GetCache()
        for pkg in apt_cache.Packages:
            if pkg.Name == self.name:
                return pkg.CurrentVer.VerStr
        return None

    def create_a_debian_dir(self, buildscript):
        buildscript.set_action('Getting a debian/ directory for', self)
        builddir = self.get_builddir(buildscript)
        deb_sources = os.path.expanduser('~/.jhdebuild/apt-get-sources/')
        if not os.path.exists(deb_sources):
            os.makedirs(deb_sources)

        debian_name = self.get_debian_name(buildscript)

        try:
            buildscript.execute(['apt-get', 'source', debian_name], cwd = deb_sources)
        except CommandError:
            raise BuildStateError('No debian source package for %s' % self.name)

        dir = [x for x in os.listdir(deb_sources) if (
                x.startswith(debian_name) and os.path.isdir(os.path.join(deb_sources, x)))][0]
        buildscript.execute(['rm', '-rf', 'debian/*'], cwd = builddir)
        if not os.path.exists(os.path.join(builddir, 'debian')):
            os.mkdir(os.path.join(builddir, 'debian'))
        buildscript.execute('cp -R %s/* debian/' % os.path.join(deb_sources, dir, 'debian'),
                cwd = builddir)
        file(os.path.join(builddir, 'debian', 'APPROPRIATE_FOR_JHDEBUILD'), 'w').write('')

    def get_makefile_var(self, buildscript, variable_name):
        builddir = self.get_builddir(buildscript)
        makefile = os.path.join(builddir, 'Makefile')
        if not os.path.exists(makefile):
            return None
        v = re.findall(r'\b%s *= *(.*)' % variable_name, open(makefile).read())
        if v:
            return v[0]
        else:
            return None


    def get_revision(self):
        return None

    def _next_state(self, buildscript, last_state):
        """Work out what state to go to next, possibly skipping some states.

        This function executes skip_$state() to decide whether to run that
        state or not.  If it returns True, go to do_$state.next_state and
        repeat.  If it returns False, return that state.
        """

        if buildscript.config.debuild:
            self.do_prefix = 'do_deb_'
            self.skip_prefix = 'skip_deb_'
        else:
            self.do_prefix = 'do_'
            self.skip_prefix = 'skip_'

        seen_states = []
        state = getattr(self, self.do_prefix + last_state).next_state
        while True:
            seen_states.append(state)
            if state == self.STATE_DONE:
                return state

            do_method = getattr(self, self.do_prefix + state)
            skip_method = getattr(self, self.skip_prefix + state)
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

        if buildscript.config.debuild:
            self.do_prefix = 'do_deb_'
            self.skip_prefix = 'skip_deb_'
        else:
            self.do_prefix = 'do_'
            self.skip_prefix = 'skip_'

        method = getattr(self, self.do_prefix + state)
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
    skip_deb_checkout = skip_checkout

    def do_deb_start(self, buildscript):
        buildscript.set_action('Starting building', self)
        ext_dep = buildscript.config.external_dependencies.get(self.name)
        if ext_dep:
            available = self.get_available_debian_version(buildscript).split('-')[0]
            if ':' in available: # remove epoch
                available = available.split(':')[-1]

            deb_available = [lax_int(x) for x in available.split('.')]
            ext_minimum = [lax_int(x) for x in ext_dep.get('minimum').split('.')]
            ext_recommended = [lax_int(x) for x in ext_dep.get('recommended').split('.')]

            if deb_available >= ext_recommended:
                buildscript.message('external dependency, available')
                if not buildscript.config.build_external_deps == 'always':
                    raise SkipToState(self.STATE_DONE)

            if deb_available >= ext_minimum:
                buildscript.message(
                        'external dependency, available (but recommended version is not)')
                if not buildscript.config.build_external_deps in ('always', 'recommended'):
                    raise SkipToState(self.STATE_DONE)
            else:
                buildscript.message('external dependency, no version high enough')
                if buildscript.config.build_external_deps == 'never':
                    raise SkipToState(self.STATE_DONE)
    do_deb_start.next_state = STATE_APT_GET_UPDATE
    do_deb_start.error_states = []

    def skip_deb_apt_get_update(self, buildscript, last_state):
        return False

    def do_deb_apt_get_update(self, buildscript):
        if not buildscript.config.nonetwork:
            buildscript.set_action('Updating packages database for', self)
            try:
                buildscript.execute(['sudo', 'apt-get', 'update'])
            except CommandError:
                pass
    do_deb_apt_get_update.next_state = STATE_DONE
    do_deb_apt_get_update.error_states = []

    def skip_deb_build_deps(self, buildscript, last_state):
        return False

    def do_deb_build_deps(self, buildscript):
        buildscript.set_action('Installing build deps for', self)
        debian_name = self.get_debian_name(buildscript)
        v = None
        try:
            v = self.get_available_debian_version(buildscript)
        except KeyError:
            pass
        if v:
            try:
                buildscript.execute(['sudo', 'apt-get', '--yes', 'build-dep', debian_name])
            except CommandError:
                raise BuildStateError('Failed to install build deps')
    do_deb_build_deps.next_state = STATE_DONE
    do_deb_build_deps.error_states = []


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

    def do_deb_start(self, buildscript):
        pass
    do_deb_start.next_state = Package.STATE_DONE
    do_deb_start.error_states = []


def parse_metamodule(node, config, url, repos, default_repo):
    id = node.getAttribute('id')
    dependencies, after, suggests = get_dependencies(node)
    return MetaModule(id, dependencies=dependencies, after=after, suggests=suggests)
register_module_type('metamodule', parse_metamodule)


register_lazy_module_type('autotools', 'jhbuild.modtypes.autotools')
register_lazy_module_type('cvsmodule', 'jhbuild.modtypes.autotools')
register_lazy_module_type('svnmodule', 'jhbuild.modtypes.autotools')
register_lazy_module_type('archmodule', 'jhbuild.modtypes.autotools')
