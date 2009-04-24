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
import sys

from jhbuild.errors import FatalError, CommandError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
import jhbuild.versioncontrol.svn
from jhbuild.commands.sanitycheck import inpath
from jhbuild.utils.sxml import sxml

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
        if module is None:
            module = name

        mirror_module = None
        if self.config.dvcs_mirror_dir:
            mirror_module = os.path.join(self.config.dvcs_mirror_dir, module)

        # allow remapping of branch for module
        if name in self.config.branches:
            try:
                new_module, revision = self.config.branches.get(name)
            except (ValueError, TypeError):
                print >> sys.stderr, _('W: ignored bad branch redefinition for module:'), name
            else:
                if new_module:
                    module = new_module
        if not (urlparse.urlparse(module)[0] or module[0] == '/'):
            module = urlparse.urljoin(self.href, module)

        if mirror_module:
            return GitBranch(self, mirror_module, subdir, checkoutdir,
                    revision, tag, unmirrored_module=module)
        else:
            return GitBranch(self, module, subdir, checkoutdir, revision, tag)

    def to_sxml(self):
        return [sxml.repository(type='git', name=self.name, href=self.href)]


class GitBranch(Branch):
    """A class representing a GIT branch."""

    def __init__(self, repository, module, subdir, checkoutdir=None,
                 branch=None, tag=None, unmirrored_module=None):
        Branch.__init__(self, repository, module, checkoutdir)
        self.subdir = subdir
        self.branch = branch
        self.tag = tag
        self.unmirrored_module = unmirrored_module

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

    def local_branch_exist(self, branch, buildscript=None):
        try:
            cmd = ['git', 'show-ref', '--quiet', '--verify', 'refs/heads/' + branch]
            if buildscript:
                buildscript.execute(cmd, cwd=self.get_checkoutdir())
            else:
                get_output(cmd, cwd=self.get_checkoutdir())
        except CommandError:
            return False
        return True

    def branchname(self):
        return self.branch
    branchname = property(branchname)

    def get_current_branch(self):
        for line in get_output(['git', 'branch'], cwd=self.srcdir).splitlines():
            if line[0] == '*':
                return line[2:]
        return None

    def get_remote_branches_list(self):
        return [x.strip() for x in get_output(['git', 'branch', '-r'],
                cwd=self.srcdir).splitlines()]

    def exists(self):
        try:
            refs = get_output(['git', 'ls-remote', self.module])
        except:
            return False

        #FIXME: Parse output from ls-remote to work out if tag/branch is present

        return True

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

    def update_dvcs_mirror(self, buildscript):
        if not self.config.dvcs_mirror_dir:
            return

        mirror_dir = os.path.join(self.config.dvcs_mirror_dir,
                os.path.basename(self.module) + '.git')

        if os.path.exists(mirror_dir):
            buildscript.execute(['git', 'fetch'], cwd=mirror_dir)
        else:
            buildscript.execute(
                    ['git', 'clone', '--mirror', self.unmirrored_module],
                    cwd=self.config.dvcs_mirror_dir)

    def _checkout(self, buildscript, copydir=None):

        if self.config.quiet_mode:
            quiet = ['-q']
        else:
            quiet = []

        self.update_dvcs_mirror(buildscript)

        cmd = ['git', 'clone'] + quiet + [self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if copydir:
            buildscript.execute(cmd, cwd=copydir)
        else:
            buildscript.execute(cmd, cwd=self.config.checkoutroot)

        self._update(buildscript, copydir=copydir, update_mirror=False)


    def _update(self, buildscript, copydir=None, update_mirror=True):
        cwd = self.get_checkoutdir(copydir)

        if not os.path.exists(os.path.join(cwd, '.git')):
            if os.path.exists(os.path.join(cwd, '.svn')):
                raise CommandError(_('Failed to update module as it switched to git (you should check for changes then remove the directory).'))
            raise CommandError(_('Failed to update module (missing .git) (you should check for changes then remove the directory).'))

        if self.config.quiet_mode:
            quiet = ['-q']
        else:
            quiet = []

        if update_mirror:
            self.update_dvcs_mirror(buildscript)

        stashed = False
        if get_output(['git', 'diff'], cwd=cwd):
            stashed = True
            buildscript.execute(['git', 'stash', 'save', 'jhbuild-stash'], cwd=cwd)

        buildscript.execute(['git', 'pull', '--rebase'], cwd=cwd)

        if stashed:
            buildscript.execute(['git', 'stash', 'pop'], cwd=cwd)

        current_branch = self.get_current_branch()
        would_be_branch = self.branch or 'master'
        if current_branch != would_be_branch:
            # if current branch doesn't exist as origin/$branch it is assumed
            # a local work branch, and it won't be changed
            if ('origin/' + current_branch) in self.get_remote_branches_list():
                if self.local_branch_exist(would_be_branch, buildscript):
                    buildscript.execute(['git', 'checkout', would_be_branch], cwd=cwd)
                else:
                    buildscript.execute(['git', 'checkout', '--track', '-b',
                            would_be_branch, 'origin/' + would_be_branch], cwd=cwd)

        if self.config.sticky_date:
            commit = self._get_commit_from_date()
            branch = 'jhbuild-date-branch'
            branch_cmd = ['git', 'checkout'] + quiet + [branch]
            try:
                buildscript.execute(branch_cmd, cwd=cwd)
            except CommandError:
                branch_cmd = ['git', 'checkout'] + quiet + ['-b', branch]
                buildscript.execute(branch_cmd, cwd=cwd)
            buildscript.execute(['git', 'reset', '--hard', commit], cwd=cwd)

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

    def to_sxml(self):
        attrs = {}
        if self.branch:
            attrs['branch'] = self.branch
        return [sxml.branch(repo=self.repository.name,
                            module=self.module,
                            tag=self.tree_id(),
                            **attrs)]


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

        if self.config.quiet_mode:
            quiet = ['-q']
        else:
            quiet = []

        cwd = self.get_checkoutdir()

        last_revision = get_output(['git', 'svn', 'find-rev', 'HEAD'], cwd=cwd)

        stashed = False
        if get_output(['git', 'diff'], cwd=cwd):
            # stash uncommitted changes on the current branch
            stashed = True
            buildscript.execute(['git', 'stash', 'save', 'jhbuild-stash'], cwd=cwd)

        buildscript.execute(['git', 'checkout'] + quiet + ['master'], cwd=cwd)
        buildscript.execute(['git', 'svn', 'rebase'], cwd=cwd)

        if stashed:
            buildscript.execute(['git', 'stash', 'pop'], cwd=cwd)

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

        cmd = ['git', 'cvsimport', '-r', 'cvs', '-p', 'b,HEAD',
               '-k', '-m', '-a', '-v', '-d', self.repository.cvsroot, '-C']

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

        cwd = self.get_checkoutdir()

        stashed = False
        # stash uncommitted changes on the current branch
        if get_output(['git', 'diff'], cwd=cwd):
            # stash uncommitted changes on the current branch
            stashed = True
            buildscript.execute(['git', 'stash', 'save', 'jhbuild-stash'], cwd=cwd)

        self._checkout(buildscript, cwd=cwd)

        if stashed:
            buildscript.execute(['git', 'stash', 'pop'], cwd=cwd)

register_repo_type('git', GitRepository)
