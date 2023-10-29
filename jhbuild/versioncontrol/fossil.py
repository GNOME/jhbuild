# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2010  Marc-Andre Lureau <marcandre.lureau@gmail.com>
#
#   fossil.py: some code to handle various Fossil operations
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
from urllib.parse import urljoin
from subprocess import Popen, PIPE

from jhbuild.errors import FatalError, CommandError
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.utils import inpath, _

class FossilRepository(Repository):
    """A class representing a Fossil repository."""

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
        return FossilBranch(self, module, checkoutdir)


class FossilBranch(Branch):
    """A class representing a Fossil branch."""

    @property
    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.checkoutroot,
                                os.path.basename(self.module))

    @property
    def repositoryfile(self):
        return os.path.join(self.checkoutroot,
                            os.path.basename(self.checkoutdir)  + '.fossil')

    @property
    def branchname(self):
        return None

    def _checkout(self, buildscript):
        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        if not os.path.exists(self.repositoryfile):
            cmd = ['fossil', 'clone', self.module, self.repositoryfile]
            buildscript.execute(cmd, 'fossil', cwd=self.checkoutroot)

        os.mkdir(self.srcdir)

        cmd = ['fossil', 'open', self.repositoryfile]
        buildscript.execute(cmd, 'fossil', cwd=self.srcdir)

    def _update(self, buildscript):
        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        cmd = ['fossil', 'pull', self.module]
        buildscript.execute(cmd, 'fossil', cwd=self.srcdir)

        cmd = ['fossil', 'update']
        buildscript.execute(cmd, 'fossil', cwd=self.srcdir)

    def checkout(self, buildscript):
        if not inpath('fossil', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'fossil')
        Branch.checkout(self, buildscript)

    def get_revision_id(self):
        import re

        try:
            infos = Popen(['fossil', 'info'], stdout=PIPE, cwd=self.srcdir)
        except OSError as e:
            raise CommandError(str(e))
        infos = infos.stdout.read().strip()
        return re.search(r"checkout: +(\w+)", infos).group(1)

    def tree_id(self):
        if not os.path.exists(self.srcdir):
            return None
        return self.get_revision_id()

register_repo_type('fossil', FossilRepository)
