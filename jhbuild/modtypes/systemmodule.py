# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2011-2012  Craig Keogh
#
#   systemmodule.py: systemmodule type definitions.
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

from jhbuild.modtypes import Package, register_module_type

__all__ = [ 'SystemModule' ]


class SystemModule(Package):
    @classmethod
    def create_virtual(cls, name, branch, deptype, value):
        return cls(name, branch=branch, systemdependencies=[(deptype, value, [])])

def parse_systemmodule(node, config, uri, repositories, default_repo):
    instance = SystemModule.parse_from_xml(node, config, uri, repositories,
                                           default_repo)

    if any(deptype == 'xml' for deptype, value, altdeps in instance.systemdependencies):
        instance.dependencies += ['xmlcatalog']

    return instance

register_module_type('systemmodule', parse_systemmodule)
