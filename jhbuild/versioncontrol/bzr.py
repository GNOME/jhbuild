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

from jhbuild.errors import FatalError, CommandError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.commands.sanitycheck import inpath

# Make sure that the urlparse module considers sftp://
# scheme to be netloc aware and set to allow relative URIs.
if 'sftp' not in urlparse.uses_netloc:
    urlparse.uses_netloc.append('sftp')
if 'sftp' not in urlparse.uses_relative:
    urlparse.uses_relative.append('sftp')


class BzrRepository(Repository):
    """A class representing a Bzr repository.

    It can be a parent of a number of Bzr repositories or branches.
    """

    init_xml_attrs = ['href', 'trunk-template', 'branches-template']

    def __init__(self, config, name, href, trunk_template='%(module)s', branches_template=''):
        Repository.__init__(self, config, name)
        # allow user to adjust location of branch.
        self.href = config.repos.get(name, href)
        self.trunk_template = trunk_template
        self.branches_template = branches_template

    branch_xml_attrs = ['module', 'checkoutdir', 'revision', 'tag']

    def branch(self, name, module=None, checkoutdir=None, revision=None, tag=None):
        module_href = None
        if name in self.config.branches:
            module_href = self.config.branches[name]
            if not module_href:
                raise FatalError(_('branch for %s has wrong override, check your .jhbuildrc') % name)

        if module is None:
            module = name

        if revision and not revision.isdigit():
            template = urlparse.urljoin(self.href, self.branches_template)
        else:
            template = urlparse.urljoin(self.href, self.trunk_template)

        if not module_href:
            module_href = template % {
                'module': module,
                'revision': revision,
                'branch': revision,
                'tag': tag
            }

        if checkoutdir is None:
            checkoutdir = name

        return BzrBranch(self, module_href, checkoutdir, tag)


class BzrBranch(Branch):
    """A class representing a Bazaar branch."""

    def __init__(self, repository, module_href, checkoutdir, tag):
        Branch.__init__(self, repository, module_href, checkoutdir)
        self.tag = tag

    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.checkoutroot,
                                os.path.basename(self.module))
    srcdir = property(srcdir)

    def branchname(self):
        return None
    branchname = property(branchname)

    def exists(self):
        try:
            get_output(['bzr', 'ls', self.module])
            return True
        except:
            return False

    def _checkout(self, buildscript):
        cmd = ['bzr', 'branch', self.module]
        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.tag:
            cmd.append('-rtag:%s' % self.tag)

        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))

        buildscript.execute(cmd, 'bzr', cwd=self.checkoutroot)

    def _update(self, buildscript, overwrite=False):
        if self.config.sticky_date:
            raise FatalError(_('date based checkout not yet supported\n'))
        cmd = ['bzr', 'pull']
        if overwrite:
            cmd.append('--overwrite')
        if self.tag:
            cmd.append('-rtag:%s' % self.tag)
        cmd.append(self.module)
        buildscript.execute(cmd, 'bzr', cwd=self.srcdir)

    def checkout(self, buildscript):
        if not inpath('bzr', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'bzr')
        if os.path.exists(self.srcdir):
            self._update(buildscript)
        else:
            self._checkout(buildscript)

    def force_checkout(self, buildscript):
        if os.path.exists(self.srcdir):
            self._update(buildscript, overwrite=True)
        else:
            self._checkout(buildscript)

    def tree_id(self):
        if not os.path.exists(self.srcdir):
            return None
        output = get_output(['bzr', 'revno'], cwd = self.srcdir)
        return output.strip()


register_repo_type('bzr', BzrRepository)
