#!/usr/bin/env python

import os

def changecvsroot(newroot, *dirs):
    def handle(newroot, dirname, fnames):
        if os.path.basename(dirname) == 'CVS' and 'Root' in fnames:
            fp = open(os.path.join(dirname, 'Root'), 'w')
            fp.write('%s\n' % newroot)
    for dir in dirs:
        os.path.walk(dir, handle, newroot)

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        sys.stderr.write('usage: changecvsroot.py newroot dirs ...\n')
        sys.exit(1)
    changecvsroot(sys.argv[1], *sys.argv[2:])
