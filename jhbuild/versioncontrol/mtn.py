# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007  Gary Kramlich <grim@reaperworld.com>
#
#   mtn.py: some code to handle various Monotone operations
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

from jhbuild.errors import CommandError, FatalError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.commands.sanitycheck import inpath

class MonotoneRepository(Repository):
    """A class representing a Monotone database."""

    init_xml_attrs = ['server', 'database', 'defbranch']

    def __init__(self, config, name, server, database, defbranch):
        Repository.__init__(self, config, name)

        self.server = config.repos.get(name, server)

        self.database = os.path.join(self.config.checkoutroot,
                                     config.repos.get(name, database))

        self.defbranch = config.repos.get(name, defbranch)

    branch_xml_attrs = ['branch', 'module', 'checkoutdir']

    def branch(self, name, branch=None, module=None, checkoutdir=None):
        if name in self.config.branches:
            module = self.config.branches[module]
            if not module:
                raise FatalError(_('branch for %(name)s has wrong override, check your %(filename)s') % \
                                   {'name'     : name,
                                    'filename' : self.config.filename})

        if not branch:
            branch = self.defbranch

        return MonotoneBranch(self, name, checkoutdir, branch, module)

class MonotoneBranch(Branch):
    """A class representing a Monotone branch."""

    def __init__(self, repository, name, checkoutdir, branch, module=None):
        Branch.__init__(self, repository, branch, checkoutdir)
        self.name = name
        self.branch = branch
        self.mtn_module = module

    def _codir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        elif self.mtn_module:
            return os.path.join(self.checkoutroot, self.branch)
        else:
            return os.path.join(self.checkoutroot, self.name)
    _codir = property(_codir)

    def srcdir(self):
        if self.mtn_module:
            return os.path.join(self._codir, self.mtn_module)
        else:
            return self._codir
    srcdir = property(srcdir)

    def branchname(self):
        return self.branch
    branchname = property(branchname)

    def _init(self, buildscript):
        """Initializes the monotone database"""

        buildscript.message(_('Initializing %s') % (self.repository.database))

        cmd = ['mtn', '-d', self.repository.database, 'db', 'init']
        buildscript.execute(cmd, 'mtn')

    def _pull(self, buildscript):
        """Pulls new revs into the database from the given server"""

        buildscript.message(_('Pulling branch %(branch)s from %(server)s') %
                            {'branch':self.branch, 'server':self.repository.server})

        cmd = ['mtn', '-d', self.repository.database, 'pull',
               self.repository.server, self.branch]

        buildscript.execute(cmd, 'mtn')

    def _check_for_conflict(self):
        """Checks 'mtn automate heads' for more than 1 head which would mean we have
          conflicts"""

        output = get_output(['mtn', 'automate', 'heads'],
                            cwd=self.srcdir)

        heads = len(output.splitlines())

        if heads > 1:
            raise CommandError(_('branch %(branch)s has %(num)d heads') %
                               {'branch':self.branch, 'num':heads})

    def _checkout(self, buildscript):
        """Checks out a branch from a repository."""

        buildscript.message(_('Checking out branch \'%(branch)s\' to directory \'%(dir)s\'') %
                            {'branch':self.branch, 'dir':self.srcdir})
        cmd = ['mtn', '-d', self.repository.database, 'co', '-b', self.branch,
               self._codir]
        buildscript.execute(cmd, 'mtn')

    def _update(self, buildscript):
        """Updates a monotone working directory."""

        buildscript.message(_('Updating working copy %s') % (self.srcdir))

        cmd = ['mtn', 'up']
        buildscript.execute(cmd, 'mtn', cwd=self._codir)

    def checkout(self, buildscript):
        # XXX: doesn't support alternative checkout modes
        if not inpath('mtn', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'mtn')

        if not os.path.exists(self.repository.database):
            self._init(buildscript)

        self._pull(buildscript)

        if os.path.exists(self.srcdir):
            try:
                self._check_for_conflict()
            except CommandError:
                buildscript.execute(['mtn', 'heads'], 'mtn', cwd=self.srcdir)
                raise

            self._update(buildscript)
        else:
            self._checkout(buildscript)

    def tree_id(self):
        try:
            output = get_output(['mtn', 'automate', 'get_base_revision_id'],
                                cwd=self.srcdir)
        except CommandError:
            return None
        return output[0]


register_repo_type('mtn', MonotoneRepository)
