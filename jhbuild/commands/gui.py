# jhbuild - a tool to ease building collections of source packages
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
from jhbuild.utils import N_
import jhbuild.frontends

class cmd_gui(Command):
    doc = N_('Build targets from a GUI app')

    name = 'gui'
    usage_args = ''

    def run(self, config, options, args, help=None):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        # request GTK build script.
        config.buildscript = 'gtkui'

        build = jhbuild.frontends.get_buildscript(config)
        build.show()
        Gtk.main()

register_command(cmd_gui)
