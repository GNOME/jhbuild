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

from jhbuild.errors import FatalError, CommandError, BuildStateError, SkipToEnd
from jhbuild.utils.sxml import sxml

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


class Package:
    type = 'base'
    PHASE_START = 'start'
    PHASE_APT_GET_UPDATE = 'apt_get_update'
    PHASE_BUILD_DEPS     = 'build_deps'
    PHASE_DONE  = 'done'
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

    def skip_phase(self, buildscript, phase, last_phase):
        try:
            skip_phase_method = getattr(self, 'skip_' + phase)
        except AttributeError:
            return False
        return skip_phase_method(buildscript, last_phase)

    def run_phase(self, buildscript, phase):
        """run a particular part of the build for this package.

        Returns a tuple of the following form:
          (error-flag, [other-phases])
        """
        method = getattr(self, 'do_' + phase)
        try:
            method(buildscript)
        except (CommandError, BuildStateError), e:
            error_phases = None
            if hasattr(method, 'error_phases'):
                error_phases = method.error_phases
            return (e, error_phases)
        else:
            return (None, None)

    def check_build_policy(self, buildscript):
        if not buildscript.config.build_policy in ('updated', 'updated-deps'):
            return
        if not buildscript.packagedb.check(self.name, self.get_revision() or ''):
            # package has not been updated
            return

        # module has not been updated
        if buildscript.config.build_policy == 'updated':
            buildscript.message(_('Skipping %s (not updated)') % self.name)
            return self.PHASE_DONE

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
                return self.PHASE_DONE

    def checkout(self, buildscript):
        srcdir = self.get_srcdir(buildscript)
        buildscript.set_action(_('Checking out'), self)
        self.branch.checkout(buildscript)
        # did the checkout succeed?
        if not os.path.exists(srcdir):
            raise BuildStateError(_('source directory %s was not created') % srcdir)

        if self.check_build_policy(buildscript) == self.PHASE_DONE:
            raise SkipToEnd()

    def skip_checkout(self, buildscript, last_phase):
        # skip the checkout stage if the nonetwork flag is set
        if buildscript.config.nonetwork:
            if self.check_build_policy(buildscript) == self.PHASE_DONE:
                raise SkipToEnd()
            return True
        return False

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
                    raise SkipToEnd()

            if deb_available >= ext_minimum:
                buildscript.message(
                        'external dependency, available (but recommended version is not)')
                if not buildscript.config.build_external_deps in ('always', 'recommended'):
                    raise SkipToEnd()
            else:
                buildscript.message('external dependency, no version high enough')
                if buildscript.config.build_external_deps == 'never':
                    raise SkipToEnd()
    do_deb_start.error_phases = []

    def skip_deb_apt_get_update(self, buildscript, last_state):
        return False

    def do_deb_apt_get_update(self, buildscript):
        if not buildscript.config.nonetwork:
            buildscript.set_action('Updating packages database for', self)
            try:
                buildscript.execute(['sudo', 'apt-get', 'update'])
            except CommandError:
                pass
    do_deb_apt_get_update.error_phases = []

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
    do_deb_build_deps.error_phases = []

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

    def to_sxml(self):
        return [sxml.metamodule(id=self.name),
                [sxml.dependencies]
                + [[sxml.dep(package=d)] for d in self.dependencies]]


    def do_deb_start(self, buildscript):
        pass
    do_deb_start.error_phases = []


def parse_metamodule(node, config, url, repos, default_repo):
    id = node.getAttribute('id')
    dependencies, after, suggests = get_dependencies(node)
    return MetaModule(id, dependencies=dependencies, after=after, suggests=suggests)
register_module_type('metamodule', parse_metamodule)


register_lazy_module_type('autotools', 'jhbuild.modtypes.autotools')
register_lazy_module_type('cvsmodule', 'jhbuild.modtypes.autotools')
register_lazy_module_type('svnmodule', 'jhbuild.modtypes.autotools')
register_lazy_module_type('archmodule', 'jhbuild.modtypes.autotools')
