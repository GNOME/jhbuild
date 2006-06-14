# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   arch.py: some code to handle various arch operations
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

__metaclass__ = type
__all__ = []

import os, sys

from jhbuild.errors import FatalError, BuildStateError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type

def is_registered(archive):
    location = os.path.join(os.environ['HOME'], '.arch-params',
                            '=locations', archive)
    return os.path.exists(location)

def register(archive, uri):
    if not is_registered(archive):
        assert uri is not None, 'can not register archive without uri'
        res = os.system('baz register-archive %s' % uri)
        if res != 0:
            raise jhbuild.errors.FatalError('could not register archive %s'
                                            % archive)

def get_version(directory):
    '''Gets the tree version for a particular directory.'''
    data = get_output(['baz', 'tree-version', '-d', directory])
    archive, version = data.strip().split('/')
    return archive, version

def split_name(version):
    '''Returns an (archive, version) pair for the string passed in.  If
    no archive is mentioned, use the default archive name.'''
    if '/' in version:
        (archive, version) = version.split('/')
    else:
        # no archive specified -- use default.
        archive = open(os.path.join(os.environ['HOME'], '.arch-params',
                                    '=default-archive'), 'r').read().strip()
    return (archive, version)


class ArchRepository(Repository):
    """A class representing an Arch archive."""

    init_xml_attrs = ['archive', 'href']

    def __init__(self, config, name, archive, href=None):
        Repository.__init__(self, config, name)
        self.archive = archive
        self.href = href

    def _ensure_registered(self):
        # has the archive been registered?
        location = os.path.join(os.environ['HOME'], '.arch-params',
                                '=locations', self.archive)
        is_registered = os.path.exists(location)
        if is_registered:
            return

        if self.href is None:
            raise BuildStateError('archive %s not registered' % self.href)
        res = os.system('baz register-archive %s' % self.href)
        if res != 0:
            raise BuildStateError('could not register archive %s'
                                  % self.archive)

    branch_xml_attrs = ['module', 'checkoutdir']

    def branch(self, name, module=None, checkoutdir=None):
        if name in self.config.branches:
            module = self.config.branches[module]
        else:
            if module is None:
                module = name
            module = '%s/%s' % (self.archive, module)
        return ArchBranch(self, module, checkoutdir)


class ArchBranch(Branch):
    """A class representing an Arch branch"""

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
        return self.module
    branchname = property(branchname)

    def _checkout(self, buildscript):
        # if the archive name hasn't been overridden, ensure that it
        # has been registered.
        archive, version = split_name(self.module)
        if archive == self.repository.archive:
            self.repository._ensure_registered()
        
        cmd = ['baz', 'get', self.module]

        if checkoutdir:
            cmd.append(checkoutdir)

        if date:
            raise BuildStageError('date based checkout not yet supported\n')

        buildscript.execute(cmd, 'arch', cwd=self.config.checkoutroot)

    def _update(self, buildscript):
        '''Perform a "baz update" (or possibly a checkout)'''
        # if the archive name hasn't been overridden, ensure that it
        # has been registered.
        archive, version = split_name(self.module)
        if archive == self.repository.archive:
            self.repository._ensure_registered()

        if date:
            raise BuildStageError('date based checkout not yet supported\n')

        archive, version = split_name(self.module)
        # how do you move a working copy to another branch?
        wc_archive, wc_version = get_version(self.srcdir)
        if (wc_archive, wc_version) != (archive, version):
            cmd = ['baz', 'switch', self.module]
        else:
            cmd = ['baz', 'update']

        buildscript.execute(cmd, 'arch', cwd=self.srcdir)

    def checkout(self, buildscript):
        if os.path.exists(self.srcdir):
            self._update(buildscript)
        else:
            self._checkout(buildscript)

    def force_checkout(self, buildscript):
        self._checkout(buildscript)

    def tree_id(self):
        data = get_output(['baz', 'tree-id', '-d', self.srcdir])
        return data.strip()



register_repo_type('arch', ArchRepository)
