# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   bootstrap.py: The bootstrap command installs a set of build utilities
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

from jhbuild.commands import register_command
from jhbuild.commands.base import cmd_build
from jhbuild.utils import N_

class cmd_bootstrap(cmd_build):
    doc = N_('Build support tools')

    name = 'bootstrap'

    def run(self, config, options, args, help=None):
        config.moduleset = 'bootstrap'
        # load the bootstrap module set
        if not args:
            args = ['meta-bootstrap']

        for item in options.skip:
            config.skip += item.split(',')
        options.skip = []

        rc = cmd_build.run(self, config, options, args)
        return rc

register_command(cmd_bootstrap)
