# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   darcs.py: some code to handle various darcs operations
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
import jhbuild.errors
import jhbuild.utils.cmds

class DarcsArchive:
    '''A class to wrap up various Darcs operations.'''

    def __init__(self, archive, checkoutroot):
        self.archive = archive
        self.localroot = checkoutroot

    def getcheckoutdir(self, checkoutdir):
        if checkoutdir:
            return os.path.join(self.localroot, checkoutdir)
        else:
            return self.localroot

    def checkout(self, buildscript, date=None, checkoutdir=None):
        os.chdir(self.localroot)
        cmd = ['darcs', 'get', self.archive]

        if checkoutdir:
            cmd.append(checkoutdir)

        if date:
            raise jhbuild.errors.FatalError(
                'date based checkout not yet supported\n')

        buildscript.execute(cmd, 'darcs')

        autogen_file = os.path.join(checkoutdir, "autogen.sh")
        if os.path.exists(autogen_file):
            os.chmod(autogen_file, 0755)

    def update(self, buildscript, date=None, checkoutdir=None):
        '''Perform a "darcs pull" (or possibly a checkout)'''
        dir = self.getcheckoutdir(checkoutdir)
        if not os.path.exists(dir):
            self.checkout(buildscript, date, checkoutdir)

        os.chdir(dir)

        if date:
            raise jhbuild.errors.FatalError(
                'date based checkout not yet supported\n')

        buildscript.execute(['darcs', 'pull', '-a'], 'darcs')
        
        autogen_file = os.path.join(checkoutdir, "autogen.sh")
        if os.path.exists(autogen_file):
            os.chmod(autogen_file, 0755)
