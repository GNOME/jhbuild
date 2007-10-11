# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
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
from stat import *
import urlparse
import subprocess

from jhbuild.errors import FatalError, CommandError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
import jhbuild.versioncontrol.svn

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


class GitRepository(Repository):
    """A class representing a GIT repository.

    Note that this is just the parent directory for a bunch of darcs
    branches, making it easy to switch to a mirror URI.
    """

    init_xml_attrs = ['href']

    def __init__(self, config, name, href):
        Repository.__init__(self, config, name)
        # allow user to adjust location of branch.
        self.href = config.repos.get(name, href)

    branch_xml_attrs = ['module', 'subdir', 'checkoutdir']

    def branch(self, name, module=None, subdir="", checkoutdir=None):
        if name in self.config.branches:
            module = self.config.branches[module]
        else:
            if module is None:
                module = name
            module = urlparse.urljoin(self.href, module)
        return GitBranch(self, module, subdir, checkoutdir)


class GitBranch(Branch):
    """A class representing a GIT branch."""

    def __init__(self, repository, module, subdir, checkoutdir):
        Branch.__init__(self, repository, module, checkoutdir)
        self.subdir = subdir

    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir, self.subdir)
        else:
            return os.path.join(self.checkoutroot,
                                os.path.basename(self.module), self.subdir)
    srcdir = property(srcdir)

    def get_checkoutdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.checkoutroot,
                                os.path.basename(self.module))

    def branchname(self):
        return None
    branchname = property(branchname)

    def _get_commit_from_date(self):
        cmd = ['git', 'log', '--max-count=1',
               '--until=%s' % self.config.sticky_date]
        cmd_desc = ' '.join(cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                cwd=self.get_checkoutdir())
        stdout = proc.communicate()[0]
        if not stdout.strip():
            raise CommandError('Command %s returned no output' % cmd_desc)
        for line in stdout.splitlines():
            if line.startswith('commit '):
                commit = line.split(None, 1)[1].strip()
                return commit
        raise CommandError('Command %s did not include commit line: %r'
                           % (cmd_desc, stdout))

    def _export(self, buildscript):
        # FIXME: should implement this properly
        self._checkout(buildscript)

    def _checkout(self, buildscript, copydir = None):
        cmd = ['git', 'clone', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if copydir:
            buildscript.execute(cmd, 'git', cwd=copydir)
        else:
            buildscript.execute(cmd, 'git', cwd=self.config.checkoutroot)

        if self.config.sticky_date:
            self._update(buildscript)

    def _update(self, buildscript, copydir=None):
        if copydir:
            cwd = os.path.join(copydir, os.path.basename(self.module))
        else:
            cwd = self.get_checkoutdir()
        if self.config.sticky_date:
            commit = self._get_commit_from_date()
            branch = 'jhbuild-date-branch'
            branch_cmd = ['git', 'checkout', branch]
            try:
                buildscript.execute(branch_cmd, 'git', cwd=cwd)
            except CommandError:
                branch_cmd = ['git', 'checkout', '-b', branch]
                buildscript.execute(branch_cmd, 'git', cwd=cwd)
            buildscript.execute(['git', 'reset', '--hard', commit],
                                'git', cwd=cwd)
                
        buildscript.execute(['git', 'pull'], 'git', cwd=cwd)

    def checkout(self, buildscript):
         if self.checkout_mode in ('clobber', 'export'):
             self._wipedir(buildscript)
             if self.checkout_mode == 'clobber':
                 self._checkout(buildscript)
             else:
                 self._checkout(buildscript)
         elif self.checkout_mode in ('update', 'copy'):
             copydir = None
             if self.checkout_mode == 'copy' and self.config.copy_dir:
                 copydir = self.config.copy_dir
             else:
                 copydir = self.config.checkoutroot

             if os.path.exists(os.path.join(copydir, 
                               os.path.basename(self.get_checkoutdir()), '.git')):
                 self._update(buildscript, copydir)
             else:
                 self._wipedir(buildscript)
                 self._checkout(buildscript, copydir)
             if self.checkout_mode == 'copy' and self.config.copy_dir:
                 self._copy(buildscript, copydir)

    def tree_id(self):
        if not os.path.exists(self.get_checkoutdir()):
            return None
        output = get_output(['git-rev-parse', 'master'],
                            cwd=self.get_checkoutdir())
        return output.strip()

class GitSvnBranch(GitBranch):
    def __init__(self, repository, module, checkoutdir, revision=None):
        GitBranch.__init__(self, repository, module, "", checkoutdir)
        self.revision = revision

    def _get_externals(self, buildscript):
        subdirs = jhbuild.versioncontrol.svn.get_subdirs (self.module)
        for subdir in subdirs:
            externals = jhbuild.versioncontrol.svn.get_externals (self.module + '/' + subdir)
            for external in externals:
                extdir = os.path.join (self.get_checkoutdir(), subdir, external)
                extbranch = GitSvnBranch(self.repository, externals[external], extdir)
                try:
                    os.stat(extdir)[ST_MODE]
                    extbranch._update(buildscript)
                except OSError:
                    extbranch._checkout(buildscript)

    def _checkout(self, buildscript):
        cmd = ['git-svn', 'init', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')

        buildscript.execute(cmd, 'git-svn', cwd=self.checkoutroot)

        last_revision = jhbuild.versioncontrol.svn.get_info (self.module)['last changed rev']

        cmd = ['git-svn', 'fetch']
        #fixme (add self.revision support)
        if not self.revision:
            cmd.extend(['-r', last_revision])
            
        buildscript.execute(cmd, 'git-svn', cwd=self.get_checkoutdir())
        
        cmd = ['git', 'checkout', '.']
        buildscript.execute(cmd, 'git checkout', cwd=self.get_checkoutdir())

        cmd = ['git-svn', 'show-ignore', '>>', '.git/info/exclude']
        buildscript.execute(cmd, 'git-svn', cwd=self.get_checkoutdir())

        #fixme, git-svn should support externals
        # self._get_externals(buildscript)
        
    def _update(self, buildscript):
        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')

        cmd = ['git-svn', 'fetch']
        buildscript.execute(cmd, 'git-svn', cwd=self.get_checkoutdir())

        cmd = ['git', 'merge', 'remotes/git-svn']
        buildscript.execute(cmd, 'git merge', cwd=self.get_checkoutdir())

        #fixme, git rebase does 'fetch'+'merge' only in recents releases
        # cmd = ['git', 'rebase', 'remotes/git-svn']
        # buildscript.execute(cmd, 'git rebase', cwd=self.get_checkoutdir())

        cmd = ['git-svn', 'show-ignore', '>>', '.git/info/exclude']
        buildscript.execute(cmd, 'git-svn', cwd=self.get_checkoutdir())

        #fixme, git-svn should support externals
        # self._get_externals(buildscript)

class GitCvsBranch(GitBranch):
    def __init__(self, repository, module, checkoutdir, revision=None):
        GitBranch.__init__(self, repository, module, "", checkoutdir)
        self.revision = revision

    def _checkout(self, buildscript):
        cmd = ['git-cvsimport', '-k', '-omaster', '-v', '-d', self.repository.cvsroot, '-C']
            
        if self.checkoutdir:
            cmd.append(self.checkoutdir)
        else:
            cmd.append(self.module)

        if self.revision:
            cmd.append('-p b,' + self.revision)
        else:
            cmd.append('-p b,HEAD')
            
        cmd.append(self.module)
            
        buildscript.execute(cmd, 'git-cvsimport', cwd=self.checkoutroot)

        cmd = ['git', 'checkout', 'origin']
        buildscript.execute(cmd, 'git checkout', cwd=self.get_checkoutdir())

    def _update(self, buildscript):
        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')

        cmd = ['git-cvsimport', '-k', '-omaster', '-v', '-d', self.repository.cvsroot, '-C']
            
        if self.checkoutdir:
            cmd.append(self.checkoutdir)
        else:
            cmd.append(self.module)

        if self.revision:
            cmd.append('-p b,' + self.revision)
        else:
            cmd.append('-p b,HEAD')
            
        cmd.append(self.module)
            
        buildscript.execute(cmd, 'git-cvsimport', cwd=self.checkoutroot)
        
register_repo_type('git', GitRepository)
