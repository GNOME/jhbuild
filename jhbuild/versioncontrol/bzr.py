# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   bzr.py: some code to handle various bazaar-ng operations
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
import errno
import urlparse

from jhbuild.errors import FatalError
from jhbuild.versioncontrol import Repository, Branch, register_repo_type

# Make sure that the urlparse module considers sftp://
# scheme to be netloc aware and set to allow relative URIs.
if 'sftp' not in urlparse.uses_netloc:
    urlparse.uses_netloc.append('sftp')
if 'sftp' not in urlparse.uses_relative:
    urlparse.uses_relative.append('sftp')


class BzrRepository(Repository):
    """A class representing a Bzr repository.

    Note that this is just the parent directory for a bunch of darcs
    branches, making it easy to switch to a mirror URI.

    It can be a parent of a number of Bzr repositories or branches.
    """

    init_xml_attrs = ['href']

    def __init__(self, config, name, href):
        Repository.__init__(self, config, name)
        # allow user to adjust location of branch.
        self.href = config.repos.get(name, href)

    branch_xml_attrs = ['module', 'checkoutdir']

    def branch(self, name, module=None, checkoutdir=None):
        if name in self.config.branches:
            module = self.config.branches[module]
        else:
            if module is None:
                module = name
            module = urlparse.urljoin(self.href, module)
        return BzrBranch(self, module, checkoutdir)


class BzrBranch(Branch):
    """A class representing a Darcs branch."""

    def __init__(self, repository, module, checkoutdir):
        self.repository = repository
        self.config = repository.config
        self.module = module
        self.checkoutdir = checkoutdir

    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.config.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.config.checkoutroot,
                                os.path.basename(self.module))
    srcdir = property(srcdir)

    def branchname(self):
        return None
    branchname = property(branchname)

    def _checkout(self, buildscript):
        cmd = ['bzr', 'branch', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')

        buildscript.execute(cmd, 'bzr', cwd=self.config.checkoutroot)

    def _update(self, buildscript, overwrite=False):
        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')
        cmd = ['bzr', 'pull']
        if overwrite:
            cmd.append('--overwrite')
        cmd.append(self.module)
        buildscript.execute(cmd, 'bzr', cwd=self.srcdir)

    def checkout(self, buildscript):
        if os.path.exists(self.srcdir):
            self._update(buildscript)
        else:
            self._checkout(buildscript)

    def force_checkout(self, buildscript):
        if os.path.exists(self.srcdir):
            self._update(buildscript, overwrite=True)
        else:
            self._checkout(buildscript)


register_repo_type('bzr', BzrRepository)
