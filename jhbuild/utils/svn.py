# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   svn.py: some code to handle various Subversion operations
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

import os, sys

def _make_uri(repo, path):
    if repo[-1] != '/':
        return '%s/%s' % (repo, path)
    else:
        return repo + path

class SVNRoot:
    '''A class to wrap up various Subversion opperations.'''

    def __init__(self, svnroot, checkoutroot):
        self.svnroot = svnroot
        self.localroot = checkoutroot

    def getcheckoutdir(self, module, checkoutdir=None):
        if checkoutdir:
            return os.path.join(self.localroot, checkoutdir)
        else:
            return os.path.join(self.localroot, os.path.basename(module))

    def checkout(self, buildscript, module, date=None, checkoutdir=None):
        os.chdir(self.localroot)
        cmd = 'svn checkout %s ' % _make_uri(self.svnroot, module)

        if checkoutdir:
            cmd += '%s ' % checkoutdir

        if date:
            cmd += '-r "{%s}" ' % date

        if checkoutdir is not None:
            cmd += checkoutdir

        return buildscript.execute(cmd, 'svn')

    def update(self, buildscript, module, date=None, checkoutdir=None):
        '''Perform a "svn update" (or possibly a checkout)'''
        dir = self.getcheckoutdir(module, checkoutdir)
        if not os.path.exists(dir):
            return self.checkout(buildscript, module, date, checkoutdir)

        os.chdir(dir)
        cmd = 'svn update '

        if date:
            cmd += '-r "{%s}" ' % date

        return buildscript.execute(cmd, 'svn')
