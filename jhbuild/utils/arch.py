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
        assert uri is not None, 'can not register archive without uri'
        res = os.system('baz register-archive %s' % uri)
        if res != 0:
            raise jhbuild.errors.FatalError('could not register archive %s'
                                            % archive)

def get_version(directory):
    '''Gets the tree version for a particular directory.'''
    data = jhbuild.utils.cmds.get_output('baz tree-version -d %s' % directory)
    archive, version = data.strip().split('/')
    return archive, version

def split_name(version):
    '''Returns an (archive, version) pair for the string passed in.  If
    no archive is mentioned, use the default archive name.'''
    if '/' in version:
        (archive, version) = version.split('/')
    else:
        # no archive specified -- use default.
        archive = open(os.path.join(os.environ['HOME'], '.arch-params',
                                    '=default-archive'), 'r').read().strip()
    return (archive, version)

class ArchArchive:
    '''A class to wrap up various Arch operations.'''

    def __init__(self, archive, checkoutroot):
        self.archive = archive
        self.localroot = checkoutroot

    def getcheckoutdir(self, version, checkoutdir=None):
        if checkoutdir:
            return os.path.join(self.localroot, checkoutdir)
        else:
            return os.path.join(self.localroot, version)

    def checkout(self, buildscript, version, date=None, checkoutdir=None):
        os.chdir(self.localroot)
        cmd = ['baz', 'get', '%s/%s' % (self.archive, version)]

        if checkoutdir:
            cmd.append(checkoutdir)

        if date:
            sys.stderr.write('date based checkout not yet supported\n')
            return -1

        return buildscript.execute(cmd, 'arch')

    def update(self, buildscript, version, date=None, checkoutdir=None):
        '''Perform a "baz update" (or possibly a checkout)'''
        dir = self.getcheckoutdir(version, checkoutdir)
        if not os.path.exists(dir):
            return self.checkout(buildscript, version, date, checkoutdir)

        os.chdir(dir)

        if date:
            sys.stderr.write('date based checkout not yet supported\n')
            return -1

        # how do you move a working copy to another branch?
        wc_archive, wc_version = get_version('.')
        if (wc_archive, wc_version) != (self.archive, version):
            cmd = ['baz', 'switch', '%s/%s' % (self.archive, version)]
        else:
            cmd = ['baz', 'update']

        return buildscript.execute(cmd, 'arch')
