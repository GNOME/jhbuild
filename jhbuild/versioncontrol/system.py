# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2012  Craig Keogh
#
#   systemm.py: system module support code.
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

from jhbuild.versioncontrol import Branch, Repository, register_repo_type
from jhbuild.utils.sxml import sxml

class SystemRepository(Repository):

    branch_xml_attrs = ['version']

    def branch(self, name, version = None):
        instance = SystemBranch(self, version)
        return instance

    def to_sxml(self):
        return [sxml.repository(type='system', name=self.name)]

class SystemBranch(Branch):

    def __init__(self, repository, version):
        Branch.__init__(self, repository, module = None, checkoutdir = None)
        self.version = version

    @property
    def branchname(self):
        return self.version

    def to_sxml(self):
        return ([sxml.branch(module=self.module,
                             repo=self.repository,
                             version=self.version)])


register_repo_type('system', SystemRepository)
