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
import shutil
import logging

from jhbuild.errors import FatalError, CommandError, BuildStateError, \
             SkipToEnd, UndefinedRepositoryError
from jhbuild.utils.sxml import sxml
import jhbuild.utils.fileutils as fileutils

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

def get_node_content(node):
    node.normalize()
    value = ''
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            value += child.nodeValue
    return value

def find_first_child_node(node, name):
    for childnode in node.childNodes:
        if (childnode.nodeType == childnode.ELEMENT_NODE and
            childnode.nodeName == name):
            return childnode
    return None

def find_first_child_node_content(node, name):
    childnode = find_first_child_node(node, name)
    if childnode is None:
        return None
    return get_node_content(childnode)

def get_branch(node, repositories, default_repo, config):
    """Scan for a <branch> element and create a corresponding Branch object."""
    name = node.getAttribute('id')
    childnode = find_first_child_node(node, 'branch')
    if childnode is None:
        raise FatalError(_('no <branch> element found for %s') % name)

    # look up the repository for this branch ...
    if childnode.hasAttribute('repo'):
        try:
            repo = repositories[childnode.getAttribute('repo')]
        except KeyError:
            raise UndefinedRepositoryError(
                _('Repository=%(missing)s not found for module id=%(module)s. Possible repositories are %(possible)s'
                  % {'missing': childnode.getAttribute('repo'), 'module': name, 'possible': repositories}))
    else:
        try:
            repo = repositories[default_repo]
        except KeyError:
            raise UndefinedRepositoryError(
                _('Default repository=%(missing)s not found for module id=%(module)s. Possible repositories are %(possible)s'
                  % {'missing': default_repo, 'module': name, 'possible': repositories}))

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
    PHASE_DONE  = 'done'
    def __init__(self, name, branch=None, dependencies = [], after = [], suggests = [], pkg_config=None):
        self.name = name
        self.branch = branch
        self.dependencies = dependencies
        self.after = after
        self.suggests = suggests
        self.pkg_config = pkg_config
        self.tags = []
        self.moduleset_name = None
        self.supports_install_destdir = False
        self.supports_parallel_build = True

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.name)

    def get_extra_env(self):
        return self.config.module_extra_env.get(self.name)
    extra_env = property(get_extra_env)

    def get_srcdir(self, buildscript):
        raise NotImplementedError
    def get_builddir(self, buildscript):
        raise NotImplementedError

    def get_destdir(self, buildscript):
        return os.path.join(buildscript.config.top_builddir, 'root-%s' % (self.name, ))

    def prepare_installroot(self, buildscript):
        assert self.supports_install_destdir
        """Return a directory suitable for use as e.g. DESTDIR with "make install"."""
        destdir = self.get_destdir(buildscript)
        if os.path.exists(destdir):
            shutil.rmtree(destdir)
        os.makedirs(destdir)
        return destdir

    def _clean_la_files_in_dir(self, buildscript, path):
        for name in os.listdir(path):
            subpath = os.path.join(path, name)
            if os.path.isdir(subpath):
                self._clean_la_files_in_dir(buildscript, subpath)
            elif name.endswith('.la'):
                    try:
                        logging.info(_('Deleting .la file: %r') % (subpath, ))
                        os.unlink(subpath)
                    except OSError:
                        pass

    def _clean_la_files(self, buildscript, installroot):
        """This method removes all .la files. See bug 654013."""
        assert os.path.isabs(installroot)
        assert os.path.isabs(buildscript.config.prefix)
        prefixdir = os.path.join(installroot, buildscript.config.prefix[1:])
        if os.path.isdir(prefixdir):
            self._clean_la_files_in_dir(self, prefixdir)

    def _process_install_files(self, installroot, curdir, prefix):
        """Strip the prefix from all files in the install root, and move
them into the prefix."""
        assert os.path.isdir(installroot) and os.path.isabs(installroot)
        assert os.path.isdir(curdir) and os.path.isabs(curdir)
        assert os.path.isdir(prefix) and os.path.isabs(prefix)

        if prefix.endswith('/'):
            prefix = prefix[:-1]

        num_copied = 0
        names = os.listdir(curdir)
        for filename in names:
            src_path = os.path.join(curdir, filename)
            assert src_path.startswith(installroot)
            dest_path = src_path[len(installroot):]
            if os.path.isdir(src_path):
                if os.path.exists(dest_path):
                    if not os.path.isdir(dest_path):
                        os.unlink(dest_path)
                        os.mkdir(dest_path)
                else:
                    os.mkdir(dest_path)
                num_copied += self._process_install_files(installroot, src_path, prefix)
                os.rmdir(src_path)
            else:
                num_copied += 1
                try:
                    os.rename(src_path, dest_path)
                except OSError, e:
                    logging.error(_('Failed to rename %(src)r to %(dest)r: %(msg)s') %
                                  {'src': src_path,
                                   'dest': dest_path,
                                   'msg': e.message})
                    raise
                    
        return num_copied

    def process_install(self, buildscript, revision):
        assert self.supports_install_destdir
        destdir = self.get_destdir(buildscript)
        self._clean_la_files(buildscript, destdir)

        stripped_prefix = buildscript.config.prefix[1:]

        previous_entry = buildscript.moduleset.packagedb.get(self.name)
        if previous_entry:
            previous_contents = previous_entry.get_manifest()
        else:
            previous_contents = None

        new_contents = fileutils.accumulate_dirtree_contents(destdir)

        install_succeeded = False
        save_broken_tree = False
        broken_name = destdir + '-broken'
        destdir_prefix = os.path.join(destdir, stripped_prefix)
        if os.path.isdir(destdir_prefix):
            destdir_install = True
            logging.info(_('Moving temporary DESTDIR %r into build prefix') % (destdir, ))
            num_copied = self._process_install_files(destdir, destdir_prefix, buildscript.config.prefix)
            logging.info(_('Install complete: %d files copied') % (num_copied, ))
        
            # Now the destdir should have a series of empty directories:
            # $JHBUILD_PREFIX/_jhbuild/root-foo/$JHBUILD_PREFIX
            # Remove them one by one to clean the tree to the state we expect,
            # so we can better spot leftovers or broken things.
            prefix_dirs = filter(lambda x: x != '', stripped_prefix.split(os.sep))
            while len(prefix_dirs) > 0:
                dirname = prefix_dirs.pop()
                subprefix = os.path.join(*([destdir] + prefix_dirs))
                target = os.path.join(subprefix, dirname)
                assert target.startswith(buildscript.config.prefix)
                try:
                    os.rmdir(target)
                except OSError, e:
                    pass

            remaining_files = os.listdir(destdir)
            if len(remaining_files) > 0:
                logging.warn(_("Files remaining in buildroot %(dest)r; module may have installed files outside of prefix.") % {'num': len(remaining_files),
                                                                                                                               'dest': broken_name})
                save_broken_tree = True
            # Even if there are some files outside the DESTDIR, count that as success for now; we just warn
            install_succeeded = True
        else:
            save_broken_tree = True

        if save_broken_tree:
            if os.path.exists(broken_name):
                assert broken_name.startswith(buildscript.config.top_builddir)
                shutil.rmtree(broken_name)
            os.rename(destdir, broken_name)
        else:
            assert destdir.startswith(buildscript.config.prefix)
            os.rmdir(destdir)

        if not install_succeeded:
            raise CommandError(_("Module failed to install into DESTDIR %(dest)r") % {'dest': broken_name})
        else:
            absolute_new_contents = map(lambda x: '/' + x, new_contents)
            to_delete = []
            if previous_contents is not None:
                for path in previous_contents:
                    if path not in absolute_new_contents:
                        to_delete.append(path)
                # Ensure we're only attempting to delete files in the prefix
                to_delete = fileutils.filter_files_by_prefix(self.config, to_delete)
                logging.info(_('%d files remaining from previous build') % (len(to_delete),))
                for (path, was_deleted, error_string) in fileutils.remove_files_and_dirs(to_delete, allow_nonempty_dirs=True):
                    if was_deleted:
                        logging.info(_('Deleted: %(file)r') % { 'file': path, })
                    elif error_string is None:
                        # We don't warn on not-empty directories
                        pass
                    else:
                        logging.warn(_("Failed to delete no longer installed file %(file)r: %(msg)s") % { 'file': path,
                                                                                                          'msg': error_string})

            buildscript.moduleset.packagedb.add(self.name, revision or '', absolute_new_contents)

    def get_revision(self):
        return self.branch.tree_id()

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
            error_phases = []
            if hasattr(method, 'error_phases'):
                error_phases = method.error_phases
            return (e, error_phases)
        else:
            return (None, None)

    def has_phase(self, phase):
        return hasattr(self, 'do_' + phase)

    def check_build_policy(self, buildscript):
        if not buildscript.config.build_policy in ('updated', 'updated-deps'):
            return

        # Always trigger a build for dirty branches if supported by the version
        # control module.
        if hasattr(self.branch, 'is_dirty') and self.branch.is_dirty():
            return

        if not buildscript.moduleset.packagedb.check(self.name, self.get_revision() or ''):
            # package has not been updated
            return

        # module has not been updated
        if buildscript.config.build_policy == 'updated':
            buildscript.message(_('Skipping %s (not updated)') % self.name)
            return self.PHASE_DONE

        if buildscript.config.build_policy == 'updated-deps':
            install_date = buildscript.moduleset.packagedb.installdate(self.name)
            for dep in self.dependencies:
                install_date_dep = buildscript.moduleset.packagedb.installdate(dep)
                if install_date_dep > install_date:
                    # a dependency has been updated
                    return None
            else:
                buildscript.message(
                        _('Skipping %s (package and dependencies not updated)') % self.name)
                return self.PHASE_DONE

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

    @classmethod
    def parse_from_xml(cls, node, config, uri, repositories, default_repo):
        """Create a new Package instance from a DOM XML node."""
        name = node.getAttribute('id')
        instance = cls(name)
        instance.branch = get_branch(node, repositories, default_repo, config)
        instance.dependencies, instance.after, instance.suggests = get_dependencies(node)
        instance.supports_parallel_build = (node.getAttribute('supports-parallel-builds') != 'no')
        pkg_config = find_first_child_node_content(node, 'pkg-config')
        if pkg_config != '':
            instance.pkg_config = pkg_config
        return instance

class DownloadableModule:
    PHASE_CHECKOUT = 'checkout'
    PHASE_FORCE_CHECKOUT = 'force_checkout'

    def do_checkout(self, buildscript):
        self.checkout(buildscript)
    do_checkout.error_phases = [PHASE_FORCE_CHECKOUT]

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
        if not self.branch.may_checkout(buildscript):
            if self.check_build_policy(buildscript) == self.PHASE_DONE:
                raise SkipToEnd()
            return True
        return False

    def do_force_checkout(self, buildscript):
        buildscript.set_action(_('Checking out'), self)
        self.branch.force_checkout(buildscript)
    do_force_checkout.error_phases = [PHASE_FORCE_CHECKOUT]
    do_force_checkout.label = N_('wipe directory and start over')
    do_force_checkout.needs_confirmation = True


class MetaModule(Package):
    """A simple module type that consists only of dependencies."""
    type = 'meta'
    def get_srcdir(self, buildscript):
        return buildscript.config.checkoutroot
    def get_builddir(self, buildscript):
        return buildscript.config.buildroot or \
               self.get_srcdir(buildscript)
    def get_revision(self):
        return None

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
