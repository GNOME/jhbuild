# jhbuild - a tool to ease building collections of source packages
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
    'get_dependencies',
    'get_branch'
    ]

import os
import re
import shutil
import logging
import importlib

from jhbuild.errors import FatalError, CommandError, BuildStateError, \
             SkipToEnd, UndefinedRepositoryError
from jhbuild.utils.sxml import sxml
from jhbuild.utils import inpath, try_import_module, N_, _
import jhbuild.utils.fileutils as fileutils

_module_types = {}
def register_module_type(name, parse_func):
    _module_types[name] = parse_func

def register_lazy_module_type(name, module):
    def parse_func(node, config, uri, repositories, default_repo):
        old_func = _module_types[name]
        importlib.import_module(module)
        assert _module_types[name] != old_func, (
            'module did not register new parser_func for %s' % name)
        return _module_types[name](node, config, uri, repositories, default_repo)
    _module_types[name] = parse_func

def parse_xml_node(node, config, uri, repositories, default_repo):
    if node.nodeName not in _module_types:
        try_import_module('jhbuild.modtypes.%s' % node.nodeName)
    if node.nodeName not in _module_types:
        raise FatalError(_('unknown module type %s') % node.nodeName)

    parser = _module_types[node.nodeName]
    return parser(node, config, uri, repositories, default_repo)

def get_dependencies(node):
    """Scan for dependencies in <dependencies>, <suggests> and <after> elements."""
    dependencies = []
    after = []
    suggests = []
    systemdependencies = []

    def add_to_list(list, childnode):
        for dep in childnode.childNodes:
            if dep.nodeType == dep.ELEMENT_NODE and dep.nodeName == 'dep':
                package = dep.getAttribute('package')
                if not package:
                    raise FatalError(_('dep node for module %s is missing package attribute') % \
                            node.getAttribute('id'))
                list.append(package)

    def add_to_system_dependencies(lst, childnode, tag='dep'):
        for dep in childnode.childNodes:
            if dep.nodeType == dep.ELEMENT_NODE and dep.nodeName == tag:
                typ = dep.getAttribute('type')
                if not typ:
                    raise FatalError(_('%(node)s node for %(module)s module is'
                                       ' missing %(attribute)s attribute') % \
                                     {'node_name'   : 'dep',
                                      'module_name' : node.getAttribute('id'),
                                      'attribute'   : 'type'})
                name = dep.getAttribute('name')
                if not name:
                    raise FatalError(_('%(node)s node for %(module)s module is'
                                       ' missing %(attribute)s attribute') % \
                                     {'node_name'   : 'dep',
                                      'module_name' : node.getAttribute('id'),
                                      'attribute'   : 'name'})
                altdeps = []
                if dep.childNodes:
                    add_to_system_dependencies(altdeps, dep, 'altdep')
                lst.append((typ, name, altdeps))

    for childnode in node.childNodes:
        if childnode.nodeType != childnode.ELEMENT_NODE:
            continue
        if childnode.nodeName == 'dependencies':
            add_to_list(dependencies, childnode)
        elif childnode.nodeName == 'suggests':
            add_to_list(suggests, childnode)
        elif childnode.nodeName == 'after':
            add_to_list(after, childnode)
        elif childnode.nodeName == 'systemdependencies':
            add_to_system_dependencies(systemdependencies, childnode)

    return dependencies, after, suggests, systemdependencies

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
            repo_names = ', '.join([r.name for r in repositories.values()])
            raise UndefinedRepositoryError(
                _('Repository=%(missing)s not found for module id=%(module)s. Possible repositories are %(possible)s'
                  % {'missing': childnode.getAttribute('repo'), 'module': name,
                     'possible': repo_names}))
    elif default_repo:
        repo = repositories[default_repo]
    else:
        raise UndefinedRepositoryError(
                _('No repository for module id=%(module)s. Either set branch/repo or default repository.'
                  % {'module': name}))

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
    def __init__(self, name, branch=None, dependencies = [], after = [],
                 suggests = [], systemdependencies = [], pkg_config=None):
        self.name = name
        self.branch = branch
        self.dependencies = dependencies
        self.after = after
        self.suggests = suggests
        self.systemdependencies = systemdependencies
        self.pkg_config = pkg_config
        self.tags = []
        self.moduleset_name = None
        self.supports_install_destdir = False
        self.supports_parallel_build = True
        self.configure_cmd = None

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.name)

    def eval_args(self, args):
        args = args.replace('${prefix}', self.config.prefix)
        libdir = os.path.join(self.config.prefix, 'lib')
        args = args.replace('${libdir}', libdir)
        return args

    @property
    def extra_env(self):
        return self.config.module_extra_env.get(self.name)

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

    def _clean_texinfo_dir_files(self, buildscript, installroot):
        """This method removes GNU Texinfo dir files."""
        assert os.path.isabs(installroot)
        assert os.path.isabs(buildscript.config.prefix)
        prefixdir = os.path.join(installroot, buildscript.config.prefix[1:])
        if os.path.isdir(prefixdir):
            dirfile = os.path.join(prefixdir, 'share/info/dir')
            if os.path.isfile(dirfile):
                try:
                    logging.info(_('Deleting dir file: %r') % (dirfile, ))
                    os.unlink(dirfile)
                except OSError:
                    pass

    def _process_install_files(self, installroot, curdir, prefix, errors):
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
            try:
                if os.path.islink(src_path):
                    linkto = os.readlink(src_path)
                    if os.path.islink(dest_path) or os.path.isfile(dest_path):
                        os.unlink(dest_path)
                    os.symlink(linkto, dest_path)
                    os.unlink(src_path)
                    num_copied += 1
                elif os.path.isdir(src_path):
                    if os.path.exists(dest_path):
                        if not os.path.isdir(dest_path):
                            os.unlink(dest_path)
                            os.mkdir(dest_path)
                    else:
                        os.mkdir(dest_path)
                    num_copied += self._process_install_files(installroot,
                                                              src_path, prefix,
                                                              errors)
                    try:
                        os.rmdir(src_path)
                    except OSError:
                        # files remaining in buildroot, errors reported below
                        pass
                else:
                    try:
                        fileutils.rename(src_path, dest_path)
                        num_copied += 1
                    except OSError as e:
                        errors.append("%s: '%s'" % (str(e), dest_path))
            except OSError as e:
                errors.append(str(e))
        return num_copied

    def process_install(self, buildscript, revision):
        assert self.supports_install_destdir
        destdir = self.get_destdir(buildscript)
        self._clean_la_files(buildscript, destdir)
        self._clean_texinfo_dir_files(buildscript, destdir)

        prefix_without_drive = os.path.splitdrive(buildscript.config.prefix)[1]
        stripped_prefix = prefix_without_drive[1:]

        install_succeeded = False
        save_broken_tree = False
        broken_name = destdir + '-broken'
        destdir_prefix = os.path.join(destdir, stripped_prefix)
        new_contents = fileutils.accumulate_dirtree_contents(destdir_prefix)
        errors = []
        if os.path.isdir(destdir_prefix):
            logging.info(_('Moving temporary DESTDIR %r into build prefix') % (destdir, ))
            num_copied = self._process_install_files(destdir, destdir_prefix,
                                                     buildscript.config.prefix,
                                                     errors)

            # Now the destdir should have a series of empty directories:
            # $JHBUILD_PREFIX/_jhbuild/root-foo/$JHBUILD_PREFIX
            # Remove them one by one to clean the tree to the state we expect,
            # so we can better spot leftovers or broken things.
            prefix_dirs = list(filter(lambda x: x != '', stripped_prefix.split(os.sep)))
            while len(prefix_dirs) > 0:
                dirname = prefix_dirs.pop()
                subprefix = os.path.join(*([destdir] + prefix_dirs))
                target = os.path.join(subprefix, dirname)
                assert target.startswith(buildscript.config.prefix)
                try:
                    os.rmdir(target)
                except OSError:
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
            fileutils.rename(destdir, broken_name)
        else:
            assert destdir.startswith(buildscript.config.prefix)
            os.rmdir(destdir)

        if not install_succeeded:
            raise CommandError(_("Module failed to install into DESTDIR %(dest)r") % {'dest': broken_name})
        else:
            to_delete = set()
            previous_entry = buildscript.moduleset.packagedb.get(self.name)
            if previous_entry:
                previous_contents = previous_entry.manifest
                if previous_contents:
                    to_delete.update(fileutils.filter_files_by_prefix(self.config, previous_contents))

            for filename in new_contents:
                to_delete.discard (os.path.join(self.config.prefix, filename))

            if to_delete:
                # paranoid double-check
                assert to_delete == set(fileutils.filter_files_by_prefix(self.config, to_delete))

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

            buildscript.moduleset.packagedb.add(self.name, revision or '',
                                                new_contents,
                                                self.configure_cmd)

        if errors:
            raise CommandError(_('Install encountered errors: %(num)d '
                                 'errors raised, %(files)d files copied. '
                                 'The errors are:\n  %(err)s') %
                               {'num'   : len(errors),
                                'files' : num_copied,
                                'err'   : '\n  '.join(errors)})
        else:
            logging.info(_('Install complete: %d files copied') %
                         (num_copied, ))

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
        except (CommandError, BuildStateError) as e:
            error_phases = []
            if hasattr(method, 'error_phases'):
                error_phases = method.error_phases
            return (e, error_phases)
        else:
            return (None, None)

    def has_phase(self, phase):
        return hasattr(self, 'do_' + phase)

    def check_build_policy(self, buildscript):
        if buildscript.config.build_policy not in ('updated', 'updated-deps'):
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
                if install_date_dep is not None and install_date is not None and install_date_dep > install_date:
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
        if self.branch is None:
            return [sxml.branch]
        return self.branch.to_sxml()

    @classmethod
    def parse_from_xml(cls, node, config, uri, repositories, default_repo):
        """Create a new Package instance from a DOM XML node."""
        name = node.getAttribute('id')
        instance = cls(name)
        instance.branch = get_branch(node, repositories, default_repo, config)
        instance.dependencies, instance.after, instance.suggests, instance.systemdependencies = get_dependencies(node)
        instance.supports_parallel_build = (node.getAttribute('supports-parallel-builds') != 'no')
        instance.config = config
        pkg_config = find_first_child_node_content(node, 'pkg-config')
        if pkg_config:
            instance.pkg_config = pkg_config
            instance.dependencies += ['pkg-config']
        instance.dependencies += instance.branch.repository.get_sysdeps()
        return instance

class NinjaModule(Package):
    '''A base class for modules that use the command 'ninja' within the build
    process.'''
    def __init__(self, name, branch=None,
                 ninjaargs='',
                 ninjainstallargs='',
                 ninjafile='build.ninja'):
        Package.__init__(self, name, branch=branch)
        self.ninjacmd = None
        self.ninjaargs = ninjaargs
        self.ninjainstallargs = ninjainstallargs
        self.ninjafile = ninjafile

    def get_ninjaargs(self, buildscript):
        ninjaargs = ' %s %s' % (self.ninjaargs,
                                self.config.module_ninjaargs.get(
                                    self.name, self.config.ninjaargs))
        if not self.supports_parallel_build:
            ninjaargs = re.sub(r'-j\w*\d+', '', ninjaargs) + ' -j 1'
        return self.eval_args(ninjaargs).strip()

    def get_ninjacmd(self, config):
        if self.ninjacmd:
            return self.ninjacmd
        for cmd in ['ninja', 'ninja-build']:
            if inpath(cmd, os.environ['PATH'].split(os.pathsep)):
                self.ninjacmd = cmd
                break
        return self.ninjacmd

    def ninja(self, buildscript, target='', ninjaargs=None, env=None):
        ninjacmd = os.environ.get('NINJA', self.get_ninjacmd(buildscript.config))
        if ninjacmd is None:
            raise BuildStateError(_('ninja not found; use NINJA to point to a specific ninja binary'))

        if ninjaargs is None:
            ninjaargs = self.get_ninjaargs(buildscript)

        extra_env = (self.extra_env or {}).copy()
        for k in (env or {}):
            extra_env[k] = env[k]

        cmd = '{ninja} {ninjaargs} {target}'.format(ninja=ninjacmd,
                                                    ninjaargs=ninjaargs,
                                                    target=target)
        buildscript.execute(cmd, cwd=self.get_builddir(buildscript), extra_env=extra_env)

class MakeModule(Package):
    '''A base class for modules that use the command 'make' within the build
    process.'''
    def __init__(self, name, branch=None, makeargs='', makeinstallargs='',
                 makefile='Makefile', needs_gmake=False):
        Package.__init__(self, name, branch=branch)
        self.makeargs = makeargs
        self.makeinstallargs = makeinstallargs
        self.makefile = makefile
        self.needs_gmake = needs_gmake

    def get_makeargs(self, buildscript, add_parallel=True):
        makeargs = ' %s %s' % (self.makeargs,
                              self.config.module_makeargs.get(
                                  self.name, self.config.makeargs))
        if self.supports_parallel_build and add_parallel:
            # Propagate job count into makeargs, unless -j is already set
            if ' -j' not in makeargs:
                arg = '-j %s' % (buildscript.config.jobs, )
                makeargs = makeargs + ' ' + arg
        elif not self.supports_parallel_build:
            makeargs = re.sub(r'-j\w*\d+', '', makeargs) + ' -j 1'
        return self.eval_args(makeargs).strip()

    def get_makecmd(self, config):
        if self.needs_gmake and 'gmake' in config.conditions:
            return 'gmake'
        else:
            return 'make'

    def make(self, buildscript, target='', pre='', makeargs=None):
        makecmd = os.environ.get('MAKE', self.get_makecmd(buildscript.config))

        if makeargs is None:
            makeargs = self.get_makeargs(buildscript)

        cmd = '{pre}{make} {makeargs} {target}'.format(pre=pre,
                                                       make=makecmd,
                                                       makeargs=makeargs,
                                                       target=target)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript), extra_env = self.extra_env)

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
        # Try to wipe the build directory. Ignore exceptions if the child class
        # does not implement get_builddir().
        try:
            builddir = self.get_builddir(buildscript)
            if os.path.exists(builddir):
                shutil.rmtree(builddir)
        except Exception:
            pass
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
    dependencies, after, suggests, systemdependencies = get_dependencies(node)
    return MetaModule(id, dependencies=dependencies, after=after,
                      suggests=suggests, systemdependencies=systemdependencies)
register_module_type('metamodule', parse_metamodule)


register_lazy_module_type('autotools', 'jhbuild.modtypes.autotools')
register_lazy_module_type('cvsmodule', 'jhbuild.modtypes.autotools')
register_lazy_module_type('svnmodule', 'jhbuild.modtypes.autotools')
