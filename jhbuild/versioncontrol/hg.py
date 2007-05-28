# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007  Marco Barisione <marco@barisione.org>
#
#   hg.py: some code to handle various Mercurial operations
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
import sys
import urlparse
from subprocess import Popen, PIPE

from jhbuild.errors import FatalError
from jhbuild.versioncontrol import Repository, Branch, register_repo_type

class HgRepository(Repository):
    """A class representing a Mercurial repository.

    Note that this is just the parent directory for a bunch of hg
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
        return HgBranch(self, module, checkoutdir)


class HgBranch(Branch):
    """A class representing a Mercurial branch."""

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
        cmd = ['hg', 'clone', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')

        buildscript.execute(cmd, 'hg', cwd=self.config.checkoutroot)

    def _update(self, buildscript):
        if self.config.sticky_date:
            raise FatalError('date based checkout not yet supported\n')
        hg_update = 'hg-update.py'
        hg_update_path = os.path.join(os.path.dirname(__file__), '..',
                                      '..', 'scripts', hg_update)
        hg_update_path = os.path.normpath(hg_update_path)
        buildscript.execute([hg_update_path], hg_update, cwd=self.srcdir)

    def checkout(self, buildscript):
        if os.path.exists(self.srcdir):
            self._update(buildscript)
        else:
            self._checkout(buildscript)

    def get_revision_id(self):
        # Return the id of the tip, see bug #313997.
        try:
            hg = Popen(['hg', 'ti', '--template', '{node}'], stdout=PIPE,
                       cwd=self.srcdir)
        except OSError, e:
            sys.stderr.write('Error: %s\n' % str(e))
            raise CommandError(str(e))
        return hg.stdout.read().strip()

register_repo_type('hg', HgRepository)
