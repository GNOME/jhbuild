# jhbuild - a build script for GNOME 1.x and 2.x
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
import urlparse
import subprocess
import re
import urllib

from jhbuild.errors import FatalError, CommandError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
import jhbuild.versioncontrol.svn
from jhbuild.commands.sanitycheck import inpath

# Make sure that the urlparse module considers git:// and git+ssh://
# schemes to be netloc aware and set to allow relative URIs.
if 'git' not in urlparse.uses_netloc:
    urlparse.uses_netloc.append('git')
if 'git' not in urlparse.uses_relative:
    urlparse.uses_relative.append('git')
if 'git+ssh' not in urlparse.uses_netloc:
    urlparse.uses_netloc.append('git+ssh')
if 'git+ssh' not in urlparse.uses_relative:
    urlparse.uses_relative.append('git+ssh')
if 'ssh' not in urlparse.uses_relative:
    urlparse.uses_relative.append('ssh')


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

    branch_xml_attrs = ['module', 'subdir', 'checkoutdir', 'revision', 'tag']

    def branch(self, name, module = None, subdir="", checkoutdir = None,
               revision = None, tag = None):
        if name in self.config.branches:
            module = self.config.branches[name]
            if not module:
                raise FatalError(_('branch for %s has wrong override, check your .jhbuildrc') % name)
        else:
            if module is None:
                module = name
            module = urlparse.urljoin(self.href, module)
        return GitBranch(self, module, subdir, checkoutdir, revision, tag)


class GitBranch(Branch):
    """A class representing a GIT branch."""

    def __init__(self, repository, module, subdir, checkoutdir=None, branch=None, tag=None):
        Branch.__init__(self, repository, module, checkoutdir)
        self.subdir = subdir
        self.branch = branch
        self.tag = tag

    def srcdir(self):
        path_elements = [self.checkoutroot]
        if self.checkoutdir:
            path_elements.append(self.checkoutdir)
        else:
            path_elements.append(os.path.basename(self.module))
        if self.subdir:
            path_elements.append(self.subdir)
        return os.path.join(*path_elements)
    srcdir = property(srcdir)

    def get_checkoutdir(self, copydir=None):
        if copydir:
            return os.path.join(copydir, os.path.basename(self.module))
        elif self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.checkoutroot,
                                os.path.basename(self.module))

    def branch_exist(self, branch):
        if not branch:
            return False
        try:
            get_output(['git', 'rev-parse', branch], cwd = self.srcdir)
            return True
        except:
            return False

    def branchname(self):
        for b in [self.tag, 'origin/' + str(self.branch), self.branch,
                  'origin/master', 'origin/trunk', 'master', 'trunk']:
            if self.branch_exist(b):
                return b
        raise GitUnknownBranchNameError()
    branchname = property(branchname)

    def _get_commit_from_date(self):
        cmd = ['git', 'log', '--max-count=1',
               '--until=%s' % self.config.sticky_date]
        cmd_desc = ' '.join(cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                cwd=self.get_checkoutdir())
        stdout = proc.communicate()[0]
        if not stdout.strip():
            raise CommandError(_('Command %s returned no output') % cmd_desc)
        for line in stdout.splitlines():
            if line.startswith('commit '):
                commit = line.split(None, 1)[1].strip()
                return commit
        raise CommandError(_('Command %s did not include commit line: %r')
                           % (cmd_desc, stdout))

    def _export(self, buildscript):
        # FIXME: should implement this properly
        self._checkout(buildscript)

    def _update_submodules(self, buildscript):
        if os.path.exists(os.path.join(self.srcdir, '.gitmodules')):
            cmd = ['git', 'submodule', 'init']
            buildscript.execute(cmd, cwd=self.srcdir)
            cmd = ['git', 'submodule', 'update']
            buildscript.execute(cmd, cwd=self.srcdir)

    def _checkout(self, buildscript, copydir=None):
        cmd = ['git', 'clone', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if copydir:
            buildscript.execute(cmd, cwd=copydir)
        else:
            buildscript.execute(cmd, cwd=self.config.checkoutroot)

        if self.branch:
            # don't try to create a new branch if we already got a local branch
            # with that name during the initial git-clone
            try:
                buildscript.execute(['git', 'show-branch', self.branch],
                                    cwd=self.srcdir)
            except CommandError:
                buildscript.execute(['git', 'checkout', '-b', self.branch, self.branchname],
                                    cwd=self.srcdir)

        if self.config.sticky_date:
            self._update(buildscript)

        self._update_submodules(buildscript)


    def _update(self, buildscript, copydir=None):
        cwd = self.get_checkoutdir(copydir)
        buildscript.execute(['git', 'fetch'], cwd=cwd)

        # stash uncommitted changes on the current branch
        buildscript.execute(['git', 'stash', 'save', 'jhbuild-build'], cwd=self.get_checkoutdir())

        if self.config.sticky_date:
            commit = self._get_commit_from_date()
            branch = 'jhbuild-date-branch'
            branch_cmd = ['git', 'checkout', branch]
            try:
                buildscript.execute(branch_cmd, cwd=cwd)
            except CommandError:
                branch_cmd = ['git', 'checkout', '-b', branch]
                buildscript.execute(branch_cmd, cwd=cwd)
            buildscript.execute(['git', 'reset', '--hard', commit], cwd=cwd)

        if self.branch:
            buildscript.execute(['git', 'checkout', self.branch], cwd=self.srcdir)
        else:
            buildscript.execute(['git', 'checkout'], cwd=self.srcdir)

        if not self.tag:
            if self.branch:
                buildscript.execute(['git', 'rebase', 'origin', self.branch], cwd=cwd)
            else:
                buildscript.execute(['git', 'rebase', 'origin', 'master'], cwd=cwd)

        self._update_submodules(buildscript)


    def checkout(self, buildscript):
        if not inpath('git', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'git')
        if self.checkout_mode in ('clobber', 'export'):
            self._wipedir(buildscript)
            self._checkout(buildscript)
        elif self.checkout_mode in ('update', 'copy'):
            if self.checkout_mode == 'copy' and self.config.copy_dir:
                copydir = self.config.copy_dir
                if os.path.exists(os.path.join(copydir,
                        os.path.basename(self.get_checkoutdir()), '.git')):
                    self._update(buildscript, copydir)
                else:
                    self._wipedir(buildscript)
                    self._checkout(buildscript, copydir)
                self._copy(buildscript, copydir)
            else:
                if os.path.exists(self.get_checkoutdir()):
                    self._update(buildscript)
                else:
                    self._checkout(buildscript)

    def force_checkout(self, buildscript):
        self.checkout(buildscript)

    def tree_id(self):
        if not os.path.exists(self.srcdir):
            return None
        try:
            output = get_output(['git', 'rev-parse', 'HEAD'],
                    cwd = self.srcdir)
        except CommandError:
            return None
        except GitUnknownBranchNameError:
            return None
        return output.strip()


class GitSvnBranch(GitBranch):
    def __init__(self, repository, module, checkoutdir, revision=None):
        GitBranch.__init__(self, repository, module, "", checkoutdir, branch="git-svn")
        self.revision = revision

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
            # we couldn't find an unhandled.log to parse so try
            # git svn show-externals - note this is broken in git < 1.5.6
            try:
                output = get_output(['git', 'svn', 'show-externals'], cwd=cwd)
                # we search for comment lines to strip them out
                comment_line = re.compile(r"^#.*")
                ext = ''
                for line in output.splitlines():
                    if not comment_line.search(line):
                        ext += ' ' + line

                match = re.compile("^(\.) (.+)").search(". " + ext)
            except OSError:
                raise FatalError(_("External handling failed\n If you are running git version < 1.5.6 it is recommended you update.\n"))

        # only parse the final match
        if match:
            branch = match.group(1)
            external = urllib.unquote(match.group(2).replace("%0A", " ").strip("%20 ")).split()
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
        
        for extdir in externals.iterkeys():
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
        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        cmd = ['git', 'svn', 'clone', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        # FIXME (add self.revision support)
        try:
            last_revision = jhbuild.versioncontrol.svn.get_info (self.module)['last changed rev']
            if not self.revision:
                cmd.extend(['-r', last_revision])
        except KeyError:
            raise FatalError(_('Cannot get last revision from %s. Check the module location.') % self.module)

        if copydir:
            buildscript.execute(cmd, cwd=copydir)
        else:
            buildscript.execute(cmd, cwd=self.config.checkoutroot)

        try:
            # is known to fail on some versions
            cmd = ['git', 'svn', 'show-ignore']
            s = get_output(cmd, cwd = self.get_checkoutdir(copydir))
            fd = file(os.path.join(
                        self.get_checkoutdir(copydir), '.git/info/exclude'), 'a')
            fd.write(s)
            fc.close()
            buildscript.execute(cmd, cwd=self.get_checkoutdir(copydir))
        except:
            pass

        # FIXME, git-svn should support externals
        self._get_externals(buildscript, self.branch)

    def _update(self, buildscript, copydir=None):
        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        cwd = self.get_checkoutdir()

        last_revision = get_output(['git', 'svn', 'find-rev', 'HEAD'], cwd=cwd)

        # stash uncommitted changes on the current branch
        cmd = ['git', 'stash', 'save', 'jhbuild-build']
        buildscript.execute(cmd, cwd=cwd)

        cmd = ['git', 'checkout', 'master']
        buildscript.execute(cmd, cwd=cwd)

        cmd = ['git', 'svn', 'rebase']
        buildscript.execute(cmd, cwd=cwd)

        current_revision = get_output(['git', 'svn', 'find-rev', 'HEAD'], cwd=cwd)

        if last_revision != current_revision:
            try:
                # is known to fail on some versions
                cmd = "git svn show-ignore >> .git/info/exclude"
                buildscript.execute(cmd, cwd=cwd)
            except:
                pass

        # FIXME, git-svn should support externals
        self._get_externals(buildscript, self.branch)

class GitCvsBranch(GitBranch):
    def __init__(self, repository, module, checkoutdir, revision=None):
        GitBranch.__init__(self, repository, module, "", checkoutdir)
        self.revision = revision

    def branchname(self):
        for b in ['remotes/' + str(self.branch), self.branch, 'trunk', 'master']:
            if self.branch_exist(b):
                return b
        raise
    branchname = property(branchname)

    def _checkout(self, buildscript, copydir=None):

        cmd = ['git', 'cvsimport', '-r', 'cvs', '-p', 'b,HEAD', '-k', '-m', '-a', '-v', '-d', self.repository.cvsroot, '-C']

        if self.checkoutdir:
            cmd.append(self.checkoutdir)
        else:
            cmd.append(self.module)

        cmd.append(self.module)

        if copydir:
            buildscript.execute(cmd, cwd=copydir)
        else:
            buildscript.execute(cmd, cwd=self.config.checkoutroot)

    def _update(self, buildscript, copydir=None):
        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        # stash uncommitted changes on the current branch
        cmd = ['git', 'stash', 'save', 'jhbuild-build']
        buildscript.execute(cmd, cwd=self.get_checkoutdir())

        self._checkout(buildscript, copydir)

register_repo_type('git', GitRepository)
