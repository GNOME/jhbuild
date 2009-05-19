# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2009  Codethink Ltd.
#
#   xvfb.py: Helper methods for running under Xvfb
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
#
#  Authors:
#    John Carr <john.carr@unrouted.co.uk>

# Heavily based on testmodule.py (FIXME: Proper attribution of GSOC student)

import os, sys, subprocess, random, md5, tempfile

class XvfbWrapper(object):

    def __init__(self, config=None):
        self.config = config or []

    def _get_display(self):
        servernum = 99
        while True:
            if not os.path.exists('/tmp/.X%d-lock' % servernum):
                break
            servernum += 1
        return str(servernum)

    def _set_xauth(self, servernum):
        paths = os.environ.get('PATH').split(':')
        for path in paths:
            if os.path.exists(os.path.join(path, xauth)):
                break
        else:
            raise Fail

        jhfolder = os.path.join(tempfile.gettempdir(), 'jhbuild.%d' % os.getpid())
        if os.path.exists(jhfolder):
            raise Fail

        try:
            os.mkdir(jhfolder)
            new_xauth = os.path.join(jhfolder, 'Xauthority')
            open(new_xauth, 'w').close()
            hexdigest = md5.md5(str(random.random())).hexdigest()
            os.system('xauth -f "%s" add ":%s" "." "%s"' % (
                new_xauth, servernum, hexdigest))
        except OSError:
            raise Fail

        return new_xauth

    def _start(self):
        new_display = self._get_display()
        new_xauth = self._set_xauth(new_display)

        os.environ['DISPLAY'] = ':' + new_display
        os.environ['XAUTHORITY'] = new_xauth

        self.xvfb = subprocess.Popen(['Xvfb',':'+new_display] + self.config, shell=False)
        self.new_display = new_display
        self.new_xauth = new_xauth

        #FIXME: Is there a better way??
        time.sleep(2)

        if self.xvfb.poll() != None:
            raise Fail

    def _stop(self):
        os.kill(self.xvfb.pid, signal.SIGINT)
        os.system('xauth remove ":%s"' % self.new_display)
        os.system('rm -r %s' % os.path.split(self.new_xauth)[0])
        del os.environ['DISPLAY']
        del os.environ['XAUTHORITY']

    def execute(self, method, *args, **kwargs):
        old_display = os.environ.get('DISPLAY')
        old_xauth = os.environ.get('XAUTHORITY')

        try:
            method(*args, **kwargs)
            self._start()
        finally:
            self._stop()
            if old_xauth:
                os.environ['XAUTHORITY'] = old_xauth
            if old_display:
                os.environ['DISPLAY'] = old_display


