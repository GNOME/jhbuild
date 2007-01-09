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
import urlparse

from jhbuild.errors import FatalError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type

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
        self.repository = repository
        self.config = repository.config
        self.module = module
        self.subdir = subdir
        self.checkoutdir = checkoutdir

    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.config.checkoutroot, self.checkoutdir, self.subdir)
        else:
            return os.path.join(self.config.checkoutroot,
                                os.path.basename(self.module), self.subdir)
    srcdir = property(srcdir)

    def get_checkoutdir(self):
        if self.checkoutdir:
            return os.path.join(self.config.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.config.checkoutroot,
                                os.path.basename(self.module))

    def branchname(self):
        return None
    branchname = property(branchname)

    def _checkout(self, buildscript):
        cmd = ['git', 'clone', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')

        buildscript.execute(cmd, 'git', cwd=self.config.checkoutroot)

    def _update(self, buildscript):
        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')
        buildscript.execute(['git', 'pull'], 'git', cwd=self.get_checkoutdir())

    def checkout(self, buildscript):
        if os.path.exists(self.get_checkoutdir()):
            self._update(buildscript)
        else:
            self._checkout(buildscript)

    def tree_id(self):
        if not os.path.exists(self.get_checkoutdir()):
            return None
        output = get_output(['git-rev-parse', 'master'],
                            cwd=self.get_checkoutdir())
        return output.strip()

register_repo_type('git', GitRepository)
