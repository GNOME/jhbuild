# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2003  James Henstridge
#
#   cvs.py: some code to handle various cvs operations
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

import os, string

class CVSRoot:
    '''A class to wrap up various CVS opperations.'''
    
    def __init__(self, buildscript, cvsroot, checkoutroot):
        self.cvsroot = cvsroot
        self.localroot = checkoutroot

        self._login(buildscript)
        
    def _login(self, buildscript):
        '''Maybe log in (if there are no entries in ~/.cvspass)'''
        loggedin = 0
        try:
            home = os.environ['HOME']
            fp = open(os.path.join(home, '.cvspass'), 'r')
            for line in fp.readlines():
                parts = string.split(line)
                if parts[0] == '/1':
                    root = parts[1]
                else:
                    root = parts[0]
                if string.replace(self.cvsroot, ':2401', ':') == \
                       string.replace(root, ':2401', ':'):
                    loggedin = 1
                    break
        except IOError:
            pass
        if not loggedin:
            return buildscript.execute('runsocks cvs -d %s login' % self.cvsroot)

    def getcheckoutdir(self, module, checkoutdir=None):
        if checkoutdir:
            return os.path.join(self.localroot, checkoutdir)
        else:
            return os.path.join(self.localroot, module)

    def checkout(self, buildscript, module, revision=None, checkoutdir=None):
        os.chdir(self.localroot)
        cmd = 'runsocks cvs -z3 -q -d %s checkout ' % self.cvsroot

        if checkoutdir:
            cmd = cmd + '-d %s ' % checkoutdir

        if revision:
            cmd = cmd + '-r %s ' % revision
        else:
            cmd = cmd + '-A '

        cmd = cmd + module

        return buildscript.execute(cmd)

    def update(self, buildscript, module, revision=None, checkoutdir=None):
        '''Perform a "cvs update" (or possibly a checkout)'''
        dir = self.getcheckoutdir(module, checkoutdir)
        if not os.path.exists(dir):
            return self.checkout(buildscript, module, revision, checkoutdir)
        
        os.chdir(dir)
        cmd = 'runsocks cvs -z3 -q -d %s update -dP ' % self.cvsroot

        if revision:
            cmd = cmd + '-r %s ' % revision
        else:
            cmd = cmd + '-A '

        cmd = cmd + '.'

        return buildscript.execute(cmd)
