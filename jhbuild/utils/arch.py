# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   arch.py: some code to handle various arch operations
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

def is_registered(archive):
    location = os.path.join(os.environ['HOME'], '.arch-params',
                            '=locations', archive)
    return os.path.exists(location)

def register(archive, uri):
    if not is_registered(archive):
        res = os.system('tla register-archive %s %s' % (archive, uri))
        if res != 0:
            raise jhbuild.errors.FatalError('could not register archive %s'
                                            % archive)

def get_revision(directory):
    data = jhbuild.utils.cmds.get_output('tla tree-version %s' % directory)
    archive, revision = data.strip().split('/')
    return archive, revision

class ArchArchive:
    '''A class to wrap up various Arch operations.'''

    def __init__(self, archive, checkoutroot):
        self.archive = archive
        self.localroot = checkoutroot

    def getcheckoutdir(self, revision, checkoutdir=None):
        if checkoutdir:
            return os.path.join(self.localroot, checkoutdir)
        else:
            return os.path.join(self.localroot, revision)

    def checkout(self, buildscript, revision, date=None, checkoutdir=None):
        os.chdir(self.localroot)
        cmd = 'tla get -A %s %s ' % (self.archive, revision)

        if checkoutdir:
            cmd += '%s ' % checkoutdir

        if date:
            sys.stderr.write('date based checkout not yet supported\n')
            return -1

        return buildscript.execute(cmd, 'arch')

    def update(self, buildscript, revision, date=None, checkoutdir=None):
        '''Perform a "svn update" (or possibly a checkout)'''
        dir = self.getcheckoutdir(revision, checkoutdir)
        if not os.path.exists(dir):
            return self.checkout(buildscript, revision, date, checkoutdir)

        os.chdir(dir)

        # how do you move a working copy to another branch?
        wc_archive, wc_revision = get_revision('.')
        if (wc_archive, wc_revision) != (self.archive, revision):
            sys.stderr.write('working copy does not point at right branch\n')
            sys.stderr.write('%s/%s != %s/%s\n' % (wc_archive, wc_revision,
                                                   self.archive, revision))
            sys.stderr.write('XXXX - need code to switch the working copy\n')
            return -1

        if date:
            sys.stderr.write('date based checkout not yet supported\n')
            return -1

        cmd = 'tla update'

        return buildscript.execute(cmd, 'arch')
