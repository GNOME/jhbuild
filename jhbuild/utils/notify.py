# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2007  Mariano Suarez-Alvarez
#
#   notify.py: using libnotify
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

class Notify:

    LOW = 'low'
    NORMAL = 'normal'
    CRITICAL = 'critical'

    def __init__(self, config = None):
        self.disabled = False
        if config and config.nonotify:
            self.disabled = True

    def notify(self, summary, body, urgency = NORMAL, icon = None, expire = 0):
        '''emit a notification'''
        if self.disabled:
            return
        cmd = ['notify-send', '--urgency=%s' % urgency]
        if icon:
            cmd.append('--icon=%s' % icon)
        if expire:
            cmd.append('--expire-time=%d' % (1000 * expire))
        cmd.extend([summary, body])
        try:
            retcode = subprocess.call(cmd)
            if retcode:
                self.disabled = True
        except OSError, e:
            self.disabled = True
