# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   darcs.py: some code to handle various darcs operations
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

class DarcsRepository(Repository):
    """A class representing a Darcs repository.

    Note that this is just the parent directory for a bunch of darcs
    branches, making it easy to switch to a mirror URI.
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
        return DarcsBranch(self, module, checkoutdir)


class DarcsBranch(Branch):
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
        cmd = ['darcs', 'get', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')

        buildscript.execute(cmd, 'darcs', cwd=self.config.checkoutroot)

    def _update(self, buildscript):
        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')
        buildscript.execute(['darcs', 'pull', '-a'], 'darcs', cwd=self.srcdir)

    def _fix_permissions(self):
        # This is a hack to make the autogen.sh and/or configure
        # scripts executable.  This is needed because Darcs does not
        # version the executable bit.
        for filename in ['autogen.sh', 'configure']:
            path = os.path.join(self.srcdir, filename)
            try:
                stat = os.stat(path)
            except OSError, e:
                continue
            os.chmod(path, stat.st_mode | 0111)

    def checkout(self, buildscript):
        if os.path.exists(self.srcdir):
            self._update(buildscript)
        else:
            self._checkout(buildscript)
        self._fix_permissions()

register_repo_type('darcs', DarcsRepository)
