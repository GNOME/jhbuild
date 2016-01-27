#!/usr/bin/env python2
# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   changecvsroot.py: script to alter the CVS root of a working copy
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

def changecvsroot(oldroot, newroot, *dirs):
    def handle(xxx_todo_changeme, dirname, fnames):
        (oldroot, newroot) = xxx_todo_changeme
        if os.path.basename(dirname) == 'CVS' and 'Root' in fnames:
            r = open(os.path.join(dirname, 'Root'), 'r').read().strip()
            if r == oldroot:
                fp = open(os.path.join(dirname, 'Root'), 'w')
                fp.write('%s\n' % newroot)
                fp.close()
    for dir in dirs:
        os.path.walk(dir, handle, (oldroot, newroot))

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 4:
        sys.stderr.write('usage: changecvsroot.py oldroot newroot dirs ...\n')
        sys.exit(1)
    changecvsroot(sys.argv[1], sys.argv[2], *sys.argv[2:])
