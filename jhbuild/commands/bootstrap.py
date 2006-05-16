# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   bootstrap.py: code to check whether prerequisite modules are installed
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

import os
import urllib

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.commands import Command, register_command

class cmd_bootstrap(Command):
    """Build required support tools."""

    name = 'bootstrap'
    usage_args = ''

    def run(self, config, options, args):
        # load the bootstrap module set
        module_set = jhbuild.moduleset.load(config, 'bootstrap')
        module_list = module_set.get_module_list(['meta-bootstrap'])

        build = jhbuild.frontends.get_buildscript(config, module_list)
        build.build()

register_command(cmd_bootstrap)
