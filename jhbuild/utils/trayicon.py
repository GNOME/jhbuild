# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   trayicon.py: simple wrapper for zenity based tray icons
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

# the command used to start the notification icon
zenity_command = '{ zenity --notification --listen; } >/dev/null 2>&1'


class TrayIcon:
    def __init__(self):
        self.fp = os.popen(zenity_command, 'w')
    def close(self):
        if not self.fp: return
        ret = self.fp.close()
        self.fp = None
        return ret

    def _send_cmd(self, cmd):
        if not self.fp: return
        try:
            self.fp.write(cmd)
            self.fp.flush()
        except (IOError, OSError):
            self.close()
    def set_icon(self, icon):
        self._send_cmd('icon: %s\n' % icon)
    def set_tooltip(self, tooltip):
        self._send_cmd('tooltip: %s\n' % tooltip)
    def set_visible(self, visible):
        if visible:
            visible = 'true'
        else:
            visible = 'false'
        self._send_cmd('visible: %s\n' % visible)
