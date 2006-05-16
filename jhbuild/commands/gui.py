# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2003-2004  Seth Nickell
#
#   gui.py: the GTK interface for jhbuild
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

from jhbuild.commands import Command, register_command
import jhbuild.frontends
from jhbuild.frontends.gtkui import Configuration


class cmd_gui(Command):
    """GTK frontend for jhbuild"""

    name = 'gui'
    usage_args = ''

    def run(self, config, options, args):
        # request GTK build script.
        config.buildscript = 'gtkui'

        configuration = Configuration(config, args)
        (module_list, start_at,
         run_autogen, cvs_update, no_build) = configuration.run()

        if start_at:
            while module_list and module_list[0].name != start_at:
                del module_list[0]

        if run_autogen:
            config.alwaysautogen = True
        elif not cvs_update:
            config.nonetwork = True

        if no_build:
            config.nobuild = True

        if module_list != None:
            build = jhbuild.frontends.get_buildscript(config, module_list)
            build.build()

register_command(cmd_gui)
