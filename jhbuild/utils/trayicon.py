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

import sys
import os
import fcntl

class TrayIcon:
    def __init__(self):
        self._run_zenity()
    def _run_zenity(self):
        pipe_r, pipe_w = os.pipe()
        self.pid = os.fork()
        if self.pid == 0:
            # close stdout/stderr
            null = open('/dev/null', 'w')
            try:
                os.dup2(null.fileno(), sys.stdout.fileno())
                os.dup2(null.fileno(), sys.stderr.fileno())
            finally:
                null.close()
            # hook pipe to stdin
            os.close(pipe_w)
            os.dup2(pipe_r, sys.stdin.fileno())
            # disassociate from controlling terminal
            os.setsid()
            # run program
            os.execvp('zenity', ['zenity', '--notification', '--listen'])
        elif self.pid > 0:
            os.close(pipe_r)
            # don't pass file descriptor on to children
            fcntl.fcntl(pipe_w, fcntl.F_SETFD,
                        fcntl.fcntl(pipe_w, fcntl.F_GETFD) | fcntl.FD_CLOEXEC)
            self.fp = os.fdopen(pipe_w, 'w')
        else:
            # ignore error.  This just means that we have no tray icon.
            self.fp = None
    def close(self):
        status = None
        if self.fp:
            self.fp.close()
            self.fp = None
        if self.pid > 0:
            (pid, status) = os.waitpid(self.pid, 0)
            self.pid = 0
        return status

    def _send_cmd(self, cmd):
        if not self.fp: return
        try:
            self.fp.write(cmd)
            self.fp.flush()
        except (IOError, OSError), err:
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
