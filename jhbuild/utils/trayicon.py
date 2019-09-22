# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
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

import sys
import os
import subprocess
import signal
try:
    import dbus
except ImportError:
    dbus = None

class TrayIcon:
    proc = None

    def __init__(self, config):
        if dbus is None:
            return
        if config and config.notrayicon:
            return
        if not os.environ.get('DISPLAY'):
            return

        try:
            bus = dbus.SessionBus()
            proxy = bus.get_object('org.freedesktop.Notifications',
                                   '/org/freedesktop/Notifications')
            notify_iface = dbus.Interface(proxy, dbus_interface='org.freedesktop.Notifications')
            caps = notify_iface.GetCapabilities()
            for item in caps:
                if item == "persistence":
                    return
        except Exception:
            pass

        try:
            self._run_zenity()
        except AttributeError:
            # 'cStringIO.StringO' object has no attribute 'fileno'
            pass

    def __del__(self):
        if self.proc:
            self.close()

    def _run_zenity(self):
        # run zenity with stdout and stderr directed to /dev/null
        def preexec():
            null = open('/dev/null', 'w')
            try:
                os.dup2(null.fileno(), sys.stdout.fileno())
                os.dup2(null.fileno(), sys.stderr.fileno())
            finally:
                null.close()
            os.setsid()
        try:
            self.proc = subprocess.Popen(['zenity', '--notification',
                                          '--listen'],
                                         close_fds=True,
                                         preexec_fn=preexec,
                                         stdin=subprocess.PIPE)
        except (OSError, IOError):
            self.proc = None

    def close(self):
        status = None
        if self.proc:
            self.proc.stdin.close()
            try:
                os.kill(self.proc.pid, signal.SIGTERM)
            except OSError:
                pass
            status = self.proc.wait()
            self.proc = None
        return status

    def _send_cmd(self, cmd):
        if not self.proc:
            return
        try:
            self.proc.stdin.write(cmd)
            self.proc.stdin.flush()
        except (IOError, OSError):
            self.close()
    def set_icon(self, icon):
        self._send_cmd(b'icon: %s\n' % icon.encode('utf-8'))
    def set_tooltip(self, tooltip):
        self._send_cmd(b'tooltip: %s\n' % tooltip.encode('utf-8'))
    def set_visible(self, visible):
        if visible:
            visible = b'true'
        else:
            visible = b'false'
        self._send_cmd(b'visible: %s\n' % visible)
