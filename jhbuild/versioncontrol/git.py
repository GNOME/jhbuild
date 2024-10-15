# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007-2008  Marc-Andre Lureau
#
#   git.py: some code to handle various GIT operations
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

__all__ = []
__metaclass__ = type

import os
import stat
import subprocess
import re
import logging
import urllib.parse
import sys

from jhbuild.errors import FatalError, CommandError
from jhbuild.utils.cmds import get_output, check_version
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.utils import inpath, _, uprint
from jhbuild.utils.sxml import sxml
from jhbuild.utils import udecode

# Make sure that the urlparse module considers git:// and git+ssh://
# schemes to be netloc aware and set to allow relative URIs.
if 'git' not in urllib.parse.uses_netloc:
    urllib.parse.uses_netloc.append('git')
if 'git' not in urllib.parse.uses_relative:
    urllib.parse.uses_relative.append('git')
if 'git+ssh' not in urllib.parse.uses_netloc:
    urllib.parse.uses_netloc.append('git+ssh')
if 'git+ssh' not in urllib.parse.uses_relative:
    urllib.parse.uses_relative.append('git+ssh')
if 'ssh' not in urllib.parse.uses_relative:
    urllib.parse.uses_relative.append('ssh')

def get_git_extra_env():
    # we run git without the JHBuild LD_LIBRARY_PATH and PATH, as it can
    # lead to errors if it picks up jhbuilded libraries, such as nss
    return { 'LD_LIBRARY_PATH': os.environ.get('UNMANGLED_LD_LIBRARY_PATH'),
             'PATH': os.environ.get('UNMANGLED_PATH')}

def get_git_mirror_directory(mirror_root, checkoutdir, module):
    """Calculate the mirror directory from the arguments and return it."""
    mirror_dir = os.path.join(mirror_root, checkoutdir or
            os.path.basename(module))
    if mirror_dir.endswith('.git'):
        return mirror_dir
    else:
        return mirror_dir + '.git'

class GitUnknownBranchNameError(Exception):
    pass


class GitRepository(Repository):
    """A class representing a GIT repository.

    Note that this is just the parent directory for a bunch of git
    branches, making it easy to switch to a mirror URI.
    """

    init_xml_attrs = ['href']

    def __init__(self, config, name, href):
        Repository.__init__(self, config, name)
        # allow user to adjust location of branch.
        self.href = config.repos.get(name, href)

    branch_xml_attrs = ['module', 'subdir', 'checkoutdir', 'revision', 'tag', 'version']

    def branch(self, name, module = None, subdir="", checkoutdir = None,
               revision = None, tag = None, version = None):
        module = module or name
        module, checkoutdir = self.eval_version(module, checkoutdir, version)
        mirror_module = None
        if self.config.dvcs_mirror_dir:
            mirror_module = get_git_mirror_directory(
                    self.config.dvcs_mirror_dir, checkoutdir, module)

        # allow remapping of branch for module, it supports two modes of
        # operation
        if name in self.config.branches:
            branch_mapping = self.config.branches.get(name)
            if type(branch_mapping) is str:
                # passing a single string will override the branch name
                revision = branch_mapping
            else:
                # otherwise it is assumed it is a pair, redefining both
                # git URI and the branch to use
                try:
                    new_module, revision = self.config.branches.get(name)
                except (ValueError, TypeError):
                    logging.warning(_('ignored bad branch redefinition for module:') + ' ' + name)
                else:
                    if new_module:
                        module = new_module
        if not (urllib.parse.urlparse(module)[0] or module[0] == '/'):
            if self.href.endswith('/'):
                base_href = self.href
            else:
                base_href = self.href + '/'
            module = base_href + module

        if mirror_module:
            return GitBranch(self, mirror_module, subdir, checkoutdir,
                    revision, tag, version, unmirrored_module=module)
        else:
            return GitBranch(self, module, subdir, checkoutdir, revision, tag, version)

    def to_sxml(self):
        return [sxml.repository(type='git', name=self.name, href=self.href)]

    def get_sysdeps(self):
        return ['git']


class GitBranch(Branch):
    """A class representing a GIT branch."""

    dirty_branch_suffix = '-dirty'
    git_minimum_version = '1.5.6'

    def __init__(self, repository, module, subdir, checkoutdir=None,
                 branch=None, tag=None, version=None, unmirrored_module=None):
        if not self.check_version_git(self.git_minimum_version):
            raise FatalError(_('Need at least git-%s to operate' % self.git_minimum_version))
        Branch.__init__(self, repository, module, checkoutdir)
        self.subdir = subdir
        self.branch = branch
        self.tag = tag
        self.version = version or tag
        if version and not tag:
            raise FatalError(_('Cannot set "version" of a git branch without "tag"'))
        self.unmirrored_module = unmirrored_module

    def check_version_git(self, version_spec):
        return check_version(['git', '--version'], r'git version ([\d.]+)',
                version_spec, extra_env=get_git_extra_env())

    def get_module_basename(self):
        # prevent basename() from returning empty strings on trailing '/'
        name = self.module.rstrip(os.sep)
        name = os.path.basename(name)
        if name.endswith('.git'):
            name = name[:-4]
        return name
 
    @property
    def srcdir(self):
        path_elements = [self.checkoutroot]
        if self.checkoutdir:
            path_elements.append(self.checkoutdir)
        else:
            path_elements.append(self.get_module_basename())
        if self.subdir:
            path_elements.append(self.subdir)
        return os.path.join(*path_elements)

    @property
    def branchname(self):
        return self.branch

    def execute_git_predicate(self, predicate):
        """A git command wrapper for the cases, where only the boolean outcome
        is of interest.
        """
        try:
            get_output(predicate, cwd=self.get_checkoutdir(),
                    extra_env=get_git_extra_env())
        except CommandError:
            return False
        return True

    def is_local_branch(self, branch):
        is_local_head = self.execute_git_predicate( ['git', 'show-ref', '--quiet',
                                                     '--verify', 'refs/heads/' + branch])
        if is_local_head:
            return True
        return self.execute_git_predicate(['git', 'rev-parse', branch])

    def is_inside_work_tree(self):
        return self.execute_git_predicate(
                ['git', 'rev-parse', '--is-inside-work-tree'])

    def is_tracking_a_remote_branch(self, local_branch):
        if not local_branch:
            return False
        current_branch_remote_config = 'branch.%s.remote' % local_branch
        return self.execute_git_predicate(
                ['git', 'config', '--get', current_branch_remote_config])

    def is_dirty(self, ignore_submodules=True):
        submodule_options = []
        if ignore_submodules:
            submodule_options = ['--ignore-submodules']
        return not self.execute_git_predicate(
                ['git', 'diff', '--exit-code', '--quiet'] + submodule_options
                + ['HEAD'])

    def get_current_branch(self):
        """Returns either a branchname or None if head is detached"""
        if not self.is_inside_work_tree():
            raise CommandError(_('Unexpected: Checkoutdir is not a git '
                    'repository:' + self.get_checkoutdir()))
        try:
            full_branch = get_output(['git', 'symbolic-ref', '-q', 'HEAD'],
                            cwd=self.get_checkoutdir(),
                            extra_env=get_git_extra_env()).strip()
            # strip refs/heads/ to get the branch name only
            return full_branch.replace('refs/heads/', '')
        except CommandError:
            return None

    def find_remote_branch_online_if_necessary(self, buildscript,
            remote_name, branch_name):
        """Try to find the given branch first, locally, then remotely, and state
        the availability in the return value."""
        wanted_ref = remote_name + '/' + branch_name
        if self.execute_git_predicate( ['git', 'show-ref', wanted_ref]):
            return True
        buildscript.execute(['git', 'fetch'], cwd=self.get_checkoutdir(),
                extra_env=get_git_extra_env())
        return self.execute_git_predicate( ['git', 'show-ref', wanted_ref])

    def get_default_branch_name(self):
        try:
            out = get_output(['git', 'ls-remote', '--symref', 'origin', 'HEAD'],
                    cwd=self.get_checkoutdir(),
                    extra_env=get_git_extra_env()).strip()
        except CommandError:
            logging.warning('get_default_branch_name() command error, so defaulting to \'main\'')
            return 'main'

        ind = out.find("ref: ")
        if ind == -1:
            logging.warning('Unexpected get_default_branch_name() output, so defaulting to \'main\'')
            return 'main'

        tmp = out[ind:].split("\t", maxsplit=1)
        if len(tmp) == 2 and tmp[1][0:4] == "HEAD":
            default_branch = tmp[0].split("/")[-1]
        else:
            logging.warning('Unexpected get_default_branch_name() output, so defaulting to \'main\'')
            default_branch = 'main'

        return default_branch

    def get_branch_switch_destination(self):
        current_branch = self.get_current_branch()
        wanted_branch = self.branch or self.get_default_branch_name()

        # Always switch away from a detached head.
        if not current_branch:
            return wanted_branch

        assert(current_branch and wanted_branch)
        # If the current branch is not tracking a remote branch it is assumed to
        # be a local work branch, and it won't be considered for a change.
        if current_branch != wanted_branch \
                and self.is_tracking_a_remote_branch(current_branch):
            return wanted_branch

        return None

    def switch_branch_if_necessary(self, buildscript):
        """
        The switch depends on the requested tag, the requested branch, and the
        state and type of the current branch.

        An imminent branch switch generates an error if there are uncommited
        changes.
        """
        wanted_branch = self.get_branch_switch_destination()
        switch_command = []
        if self.tag:
            switch_command= ['git', 'checkout', self.tag]
        elif wanted_branch:
            if self.is_local_branch(wanted_branch):
                switch_command = ['git', 'checkout', wanted_branch]
            else:
                if not self.find_remote_branch_online_if_necessary(
                        buildscript, 'origin', wanted_branch):
                    raise CommandError(_('The requested branch "%s" is '
                            'not available. Neither locally, nor remotely '
                            'in the origin remote.' % wanted_branch))
                switch_command = ['git', 'checkout', '--track', '-b',
                        wanted_branch, 'origin/' + wanted_branch]

        if switch_command:
            if self.is_dirty():
                raise CommandError(_('Refusing to switch a dirty tree.'))
            buildscript.execute(switch_command, cwd=self.get_checkoutdir(),
                    extra_env=get_git_extra_env())

    def rebase_current_branch(self, buildscript):
        """Pull the current branch if it is tracking a remote branch."""
        branch = self.get_current_branch()
        if not self.is_tracking_a_remote_branch(branch):
            return

        git_extra_args = {'cwd': self.get_checkoutdir(),
                'extra_env': get_git_extra_env()}

        buildscript.execute(['git', 'rebase', 'origin/' + branch],
                            **git_extra_args)

    def move_to_sticky_date(self, buildscript):
        if self.config.quiet_mode:
            quiet = ['-q']
        else:
            quiet = []
        commit = self._get_commit_from_date()
        branch = 'jhbuild-date-branch'
        branch_cmd = ['git', 'checkout'] + quiet + [branch]
        git_extra_args = {'cwd': self.get_checkoutdir(),
                'extra_env': get_git_extra_env()}
        if self.config.sticky_date == 'none':
            current_branch = self.get_current_branch()
            if current_branch and current_branch == branch:
                buildscript.execute(['git', 'checkout'] + quiet + ['master'],
                        **git_extra_args)
            return
        try:
            buildscript.execute(branch_cmd, **git_extra_args)
        except CommandError:
            branch_cmd = ['git', 'checkout'] + quiet + ['-b', branch]
            buildscript.execute(branch_cmd, **git_extra_args)
        buildscript.execute(['git', 'reset', '--hard', commit], **git_extra_args)

    def get_remote_branches_list(self):
        return [x.strip() for x in get_output(['git', 'branch', '-r'],
                cwd=self.get_checkoutdir(),
                extra_env=get_git_extra_env()).splitlines()]

    def exists(self):
        try:
            get_output(['git', 'ls-remote', self.module],
                       extra_env=get_git_extra_env())
        except CommandError:
            return False

        # FIXME: Parse output from ls-remote to work out if tag/branch is present

        return True

    def _get_commit_from_date(self):
        cmd = ['git', 'log', '--max-count=1', '--first-parent',
               '--until=%s' % self.config.sticky_date, 'master']
        cmd_desc = ' '.join(cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                cwd=self.get_checkoutdir(),
                                env=get_git_extra_env())
        stdout = udecode(proc.communicate()[0])
        if not stdout.strip():
            raise CommandError(_('Command %s returned no output') % cmd_desc)
        for line in stdout.splitlines():
            if line.startswith('commit '):
                commit = line.split(None, 1)[1].strip()
                return commit
        raise CommandError(_('Command %s did not include commit line: %r')
                           % (cmd_desc, stdout))

    def _export(self, buildscript):
        self._checkout(buildscript)

        try:
            output = get_output(['git', 'rev-parse', 'HEAD'],
                    cwd = self.get_checkoutdir(), get_stderr=False,
                    extra_env=get_git_extra_env())
            tag = output.strip()
        except CommandError:
            tag = 'unknown'

        filename = self.get_module_basename() + '-' + tag + '.zip'

        if self.config.export_dir is not None:
            path = os.path.join(self.config.export_dir, filename)
        else:
            path = os.path.join(self.checkoutroot, filename)

        git_extra_args = {'cwd': self.get_checkoutdir(), 'extra_env': get_git_extra_env()}
        buildscript.execute(['git', 'archive', '-o', path, 'HEAD'], **git_extra_args)

    def _update_submodules(self, buildscript):
        if os.path.exists(os.path.join(self.get_checkoutdir(), '.gitmodules')):
            cmd = ['git', 'submodule', 'init']
            buildscript.execute(cmd, cwd=self.get_checkoutdir(),
                    extra_env=get_git_extra_env())
            cmd = ['git', 'submodule', 'update']
            buildscript.execute(cmd, cwd=self.get_checkoutdir(),
                    extra_env=get_git_extra_env())

    def update_dvcs_mirror(self, buildscript):
        if not self.config.dvcs_mirror_dir:
            return
        if self.config.nonetwork:
            return

        # Calculate a new in case a configuration reload changed the mirror root.
        mirror_dir = get_git_mirror_directory(self.config.dvcs_mirror_dir,
                self.checkoutdir, self.unmirrored_module)

        if os.path.exists(mirror_dir):
            buildscript.execute(['git', 'remote', 'set-url', 'origin',
                    self.unmirrored_module], cwd=mirror_dir,
                    extra_env=get_git_extra_env())
            buildscript.execute(['git', 'fetch'], cwd=mirror_dir,
                    extra_env=get_git_extra_env())
        else:
            buildscript.execute(
                    ['git', 'clone', '--mirror', self.unmirrored_module,
                    mirror_dir], extra_env=get_git_extra_env())

    def _checkout(self, buildscript, copydir=None):

        extra_opts = []
        if self.config.quiet_mode:
            extra_opts.append('-q')

        if self.config.shallow_clone:
            extra_opts += ['--depth=1', '--no-single-branch']

        self.update_dvcs_mirror(buildscript)

        cmd = ['git', 'clone'] + extra_opts + [self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.tag:
            cmd.extend(['--branch', self.tag])
        elif self.branch:
            cmd.extend(['--branch', self.branch])

        if copydir:
            buildscript.execute(cmd, cwd=copydir, extra_env=get_git_extra_env())
        else:
            buildscript.execute(cmd, cwd=self.config.checkoutroot,
                    extra_env=get_git_extra_env())

        self._update(buildscript, copydir=copydir, update_mirror=False)


    def _update(self, buildscript, copydir=None, update_mirror=True):
        cwd = self.get_checkoutdir()
        git_extra_args = {'cwd': cwd, 'extra_env': get_git_extra_env()}

        if not os.path.exists(os.path.join(cwd, '.git')):
            if os.path.exists(os.path.join(cwd, '.svn')):
                raise CommandError(_('Failed to update module as it switched to git (you should check for changes then remove the directory).'))
            raise CommandError(_('Failed to update module (missing .git) (you should check for changes then remove the directory).'))

        if update_mirror:
            self.update_dvcs_mirror(buildscript)

        buildscript.execute(['git', 'remote', 'set-url', 'origin',
                self.module], **git_extra_args)

        buildscript.execute(['git', 'remote', 'update', 'origin'],
                **git_extra_args)

        stashed = False
        if self.is_dirty(ignore_submodules=True):
            stashed = True
            buildscript.execute(['git', 'stash', 'save', 'jhbuild-stash'], **git_extra_args)

        if self.config.sticky_date:
            self.move_to_sticky_date(buildscript)

        self.switch_branch_if_necessary(buildscript)

        self.rebase_current_branch(buildscript)

        self._update_submodules(buildscript)

        if stashed:
            buildscript.execute(['git', 'stash', 'pop'], **git_extra_args)

        if self.patches:
            self._do_patches(buildscript)

    def _do_patches(self, buildscript):
        patch_files = self.get_patch_files(buildscript)
        for (patchfile, patch, patchstrip) in patch_files:
            self._do_patch(buildscript, patchfile, patch)

    def _do_patch(self, buildscript, patchfile, patch):
        git_extra_args = {'cwd': self.get_checkoutdir(), 'extra_env': get_git_extra_env()}
        buildscript.set_action(_('Applying patch'), self, action_target=patch)
        can_apply = self.execute_git_predicate(['git', 'am', os.path.abspath(patchfile)])
        if not can_apply:
            self.execute_git_predicate(['git', 'am', '--abort'])
            already_applied = self.execute_git_predicate(['git', 'apply', '--reverse', '--check', os.path.abspath(patchfile)])
            if already_applied:
                uprint(_("Skipping patch '%s' (already applied)") % patchfile, file=sys.stderr)
            else:
                can_apply = self.execute_git_predicate(['git', 'apply', '--check', os.path.abspath(patchfile)])
                if can_apply:
                    buildscript.execute(['git', 'apply', os.path.abspath(patchfile)], **git_extra_args)
                else:
                    raise FatalError(_("Could not apply patch '%s'\n") % patchfile)

    def may_checkout(self, buildscript):
        if buildscript.config.nonetwork and not buildscript.config.dvcs_mirror_dir:
            return False
        return True

    def checkout(self, buildscript):
        if not inpath('git', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'git')
        Branch.checkout(self, buildscript)

    def delete_unknown_files(self, buildscript):
        git_extra_args = {'cwd': self.get_checkoutdir(), 'extra_env': get_git_extra_env()}
        buildscript.execute(['git', 'clean', '-d', '-f', '-x'], **git_extra_args)

    def tree_id(self):
        if not os.path.exists(self.get_checkoutdir()):
            return None
        try:
            output = get_output(['git', 'rev-parse', 'HEAD'],
                    cwd = self.get_checkoutdir(), get_stderr=False,
                    extra_env=get_git_extra_env())
        except CommandError:
            return None
        except GitUnknownBranchNameError:
            return None
        id_suffix = ''
        if self.is_dirty():
            id_suffix = self.dirty_branch_suffix
        return output.strip() + id_suffix

    def to_sxml(self):
        attrs = {}
        if self.branch:
            attrs['revision'] = self.branch
        if self.checkoutdir:
            attrs['checkoutdir'] = self.checkoutdir
        if self.subdir:
            attrs['subdir'] = self.subdir
        return [sxml.branch(repo=self.repository.name,
                            module=self.module,
                            tag=self.tree_id(),
                            **attrs)]


class GitSvnBranch(GitBranch):
    def __init__(self, repository, module, checkoutdir, revision=None):
        GitBranch.__init__(self, repository, module, "", checkoutdir, branch="git-svn")
        self.revision = revision

    def may_checkout(self, buildscript):
        return Branch.may_checkout(self, buildscript)

    def _get_externals(self, buildscript, branch="git-svn"):
        cwd = self.get_checkoutdir()
        try:
            externals = {}
            match = None
            external_expr = re.compile(r"\+dir_prop: (.*?) svn:externals (.*)$")
            rev_expr = re.compile(r"^r(\d+)$")
            # the unhandled.log file has the revision numbers
            # encoded as r#num we should only parse as far as self.revision
            for line in open(os.path.join(cwd, '.git', 'svn', branch, 'unhandled.log')):
                m = external_expr.search(line)
                if m:
                    match = m
                rev_match = rev_expr.search(line)
                if self.revision and rev_match:
                    if rev_match.group(1) > self.revision:
                        break
        except IOError:
            try:
                output = get_output(['git', 'svn', 'show-externals'], cwd=cwd,
                        extra_env=get_git_extra_env())
                # we search for comment lines to strip them out
                comment_line = re.compile(r"^#.*")
                ext = ''
                for line in output.splitlines():
                    if not comment_line.search(line):
                        ext += ' ' + line

                match = re.compile("^(\\.) (.+)").search(". " + ext)
            except OSError:
                raise FatalError(_("External handling failed\n"))

        # only parse the final match
        if match:
            branch = match.group(1)
            external = urllib.parse.unquote(match.group(2).replace("%0A", " ").strip("%20 ")).split()
            revision_expr = re.compile(r"-r(\d*)")
            i = 0
            while i < len(external):
                # see if we have a revision number
                match = revision_expr.search(external[i+1])
                if match:
                    externals[external[i]] = (external[i+2], match.group(1))
                    i = i+3
                else:
                    externals[external[i]] = (external[i+1], None)
                    i = i+2
        
        for extdir in externals.keys():
            uri = externals[extdir][0]
            revision = externals[extdir][1]
            extdir = cwd+os.sep+extdir
            # FIXME: the "right way" is to use submodules
            extbranch = GitSvnBranch(self.repository, uri, extdir, revision)
            
            try:
                os.stat(extdir)[stat.ST_MODE]
                extbranch._update(buildscript)
            except OSError:
                extbranch._checkout(buildscript)

    def _checkout(self, buildscript, copydir=None):
        from . import svn

        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        cmd = ['git', 'svn', 'clone', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        # FIXME (add self.revision support)
        try:
            last_revision = svn.get_info (self.module)['last changed rev']
            if not self.revision:
                cmd.extend(['-r', last_revision])
        except KeyError:
            raise FatalError(_('Cannot get last revision from %s. Check the module location.') % self.module)

        if copydir:
            buildscript.execute(cmd, cwd=copydir,
                    extra_env=get_git_extra_env())
        else:
            buildscript.execute(cmd, cwd=self.config.checkoutroot,
                    extra_env=get_git_extra_env())

        try:
            # is known to fail on some versions
            cmd = ['git', 'svn', 'show-ignore']
            s = get_output(cmd, cwd = self.get_checkoutdir(copydir),
                    extra_env=get_git_extra_env())
            fd = open(os.path.join(
                        self.get_checkoutdir(copydir), '.git/info/exclude'), 'a')
            fd.write(s)
            fd.close()
            buildscript.execute(cmd, cwd=self.get_checkoutdir(copydir),
                    extra_env=get_git_extra_env())
        except (CommandError, EnvironmentError):
            pass

        # FIXME, git-svn should support externals
        self._get_externals(buildscript, self.branch)

    def _update(self, buildscript, copydir=None):
        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        if self.config.quiet_mode:
            quiet = ['-q']
        else:
            quiet = []

        cwd = self.get_checkoutdir()
        git_extra_args = {'cwd': cwd, 'extra_env': get_git_extra_env()}

        last_revision = get_output(['git', 'svn', 'find-rev', 'HEAD'],
                **git_extra_args)

        stashed = False
        if get_output(['git', 'diff'], **git_extra_args):
            # stash uncommitted changes on the current branch
            stashed = True
            buildscript.execute(['git', 'stash', 'save', 'jhbuild-stash'],
                    **git_extra_args)

        buildscript.execute(['git', 'checkout'] + quiet + ['master'],
                **git_extra_args)
        buildscript.execute(['git', 'svn', 'rebase'], **git_extra_args)

        if stashed:
            buildscript.execute(['git', 'stash', 'pop'], **git_extra_args)

        current_revision = get_output(['git', 'svn', 'find-rev', 'HEAD'],
                **git_extra_args)

        if last_revision != current_revision:
            try:
                # is known to fail on some versions
                cmd = "git svn show-ignore >> .git/info/exclude"
                buildscript.execute(cmd, **git_extra_args)
            except CommandError:
                pass

        # FIXME, git-svn should support externals
        self._get_externals(buildscript, self.branch)

class GitCvsBranch(GitBranch):
    def __init__(self, repository, module, checkoutdir, revision=None):
        GitBranch.__init__(self, repository, module, "", checkoutdir)
        self.revision = revision

    def may_checkout(self, buildscript):
        return Branch.may_checkout(self, buildscript)

    @property
    def branchname(self):
        for b in ['remotes/' + str(self.branch), self.branch, 'trunk', 'master']:
            if self.branch_exist(b):
                return b
        raise

    def _checkout(self, buildscript, copydir=None):

        cmd = ['git', 'cvsimport', '-r', 'cvs', '-p', 'b,HEAD',
               '-k', '-m', '-a', '-v', '-d', self.repository.cvsroot, '-C']

        if self.checkoutdir:
            cmd.append(self.checkoutdir)
        else:
            cmd.append(self.module)

        cmd.append(self.module)

        if copydir:
            buildscript.execute(cmd, cwd=copydir, extra_env=get_git_extra_env())
        else:
            buildscript.execute(cmd, cwd=self.config.checkoutroot,
                    extra_env=get_git_extra_env())

    def _update(self, buildscript, copydir=None):
        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        cwd = self.get_checkoutdir()
        git_extra_args = {'cwd': cwd, 'extra_env': get_git_extra_env()}

        stashed = False
        # stash uncommitted changes on the current branch
        if get_output(['git', 'diff'], **git_extra_args):
            # stash uncommitted changes on the current branch
            stashed = True
            buildscript.execute(['git', 'stash', 'save', 'jhbuild-stash'],
                    **git_extra_args)

        self._checkout(buildscript, copydir=copydir)

        if stashed:
            buildscript.execute(['git', 'stash', 'pop'], **git_extra_args)

register_repo_type('git', GitRepository)
