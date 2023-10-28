# jhbuild - a tool to ease building collections of source packages
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
import hashlib
from urllib.parse import urljoin

from jhbuild.errors import FatalError, CommandError
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.utils import inpath, _

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
            module = self.config.branches[name]
            if not module:
                raise FatalError(_('branch for %(name)s has wrong override, check your %(filename)s') % \
                                 {'name'     : name,
                                  'filename' : self.config.filename})
        else:
            if module is None:
                module = name
            module = urljoin(self.href, module)
        return DarcsBranch(self, module, checkoutdir)


class DarcsBranch(Branch):
    """A class representing a Darcs branch."""

    @property
    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.checkoutroot,
                                os.path.basename(self.module))

    @property
    def branchname(self):
        return None

    def _checkout(self, buildscript):
        cmd = ['darcs', 'get', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        buildscript.execute(cmd, 'darcs', cwd=self.checkoutroot)

    def _update(self, buildscript):
        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))
        buildscript.execute(['darcs', 'pull', '-a', '--no-set-default', self.module],
                            'darcs', cwd=self.srcdir)

    def _fix_permissions(self):
        # This is a hack to make the autogen.sh and/or configure
        # scripts executable.  This is needed because Darcs does not
        # version the executable bit.
        for filename in ['autogen.sh', 'configure']:
            path = os.path.join(self.srcdir, filename)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            os.chmod(path, stat.st_mode | 0o111)

    def checkout(self, buildscript):
        if not inpath('darcs', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'darcs')
        Branch.checkout(self, buildscript)
        self._fix_permissions()

    def tree_id(self):
        # XXX: check with some darcs expert if there is not a command to get
        # this
        if not os.path.exists(self.srcdir):
            return None
        return hashlib.md5(open(os.path.join(self.srcdir, '_darcs', 'inventory')).read()).hexdigest()

register_repo_type('darcs', DarcsRepository)
