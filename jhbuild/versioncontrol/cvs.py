# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
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

__all__ = [
    'CVSRepository',
    'login',
    'get_sticky_tag',
    ]
__metaclass__ = type

import os, sys

from jhbuild.errors import BuildStateError
from jhbuild.versioncontrol import Repository, Branch, register_repo_type


# table used to scramble passwords in ~/.cvspass files
_shifts = [
    0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
   16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
  114,120, 53, 79, 96,109, 72,108, 70, 64, 76, 67,116, 74, 68, 87,
  111, 52, 75,119, 49, 34, 82, 81, 95, 65,112, 86,118,110,122,105,
   41, 57, 83, 43, 46,102, 40, 89, 38,103, 45, 50, 42,123, 91, 35,
  125, 55, 54, 66,124,126, 59, 47, 92, 71,115, 78, 88,107,106, 56,
   36,121,117,104,101,100, 69, 73, 99, 63, 94, 93, 39, 37, 61, 48,
   58,113, 32, 90, 44, 98, 60, 51, 33, 97, 62, 77, 84, 80, 85,223,
  225,216,187,166,229,189,222,188,141,249,148,200,184,136,248,190,
  199,170,181,204,138,232,218,183,255,234,220,247,213,203,226,193,
  174,172,228,252,217,201,131,230,197,211,145,238,161,179,160,212,
  207,221,254,173,202,146,224,151,140,196,205,130,135,133,143,246,
  192,159,244,239,185,168,215,144,139,165,180,157,147,186,214,176,
  227,231,219,169,175,156,206,198,129,164,150,210,154,177,134,127,
  182,128,158,208,162,132,167,209,149,241,153,251,237,236,171,195,
  243,233,253,240,194,250,191,155,142,137,245,235,163,242,178,152
]

def scramble(password):
    return 'A' + ''.join([chr(_shifts[ord(ch)]) for ch in password])
def descramble(password):
    assert password[0] == 'A', 'unknown password format'
    return ''.join([chr(_shifts[ord(ch)]) for ch in password[1:]])

def _canonicalise_cvsroot(cvsroot):
    if not cvsroot.startswith(':pserver:'): return cvsroot
    parts = cvsroot.split(':')
    if parts[3].startswith('/'):
        parts[3] = '2401' + parts[3]
    return ':'.join(parts)

def login(cvsroot, password=None):
    if not cvsroot.startswith(':pserver:'): return
    cvsroot = _canonicalise_cvsroot(cvsroot)
    cvspass = os.path.join(os.environ['HOME'], '.cvspass')

    # check if the password has already been entered:
    try:
        fp = open(cvspass, 'r')
        for line in fp.readlines():
            parts = line.split()
            if not parts:
                continue
            if parts[0] == '/1':
                root = parts[1]
            else:
                root = _canonicalise_cvsroot(parts[0])
            if root == cvsroot:
                return
                break
    except IOError:
        pass
     # if we have a password, just write it directly to the .cvspass file
    if password is not None:
        fp = open(cvspass, 'a')
        fp.write('/1 %s %s\n' % (cvsroot, scramble(password)))
        fp.close()
    else:
        # call cvs login ..
        if os.system('cvs -d %s login' % cvsroot) != 0:
            sys.stderr.write('could not log into %s\n' % cvsroot)
            sys.exit(1)

def check_sticky_tag(filename):
    dirname = os.path.dirname(filename)
    basename = os.path.basename(filename)
    entries_file = os.path.join(dirname, 'CVS', 'Entries')
    fp = open(entries_file, 'r')
    line = fp.readline()
    while line:
        parts = line.strip().split('/')
        if parts[1] == basename:
            # parts[5] is the tag for this file
            if parts[5] == '':
                return None
            else:
                return parts[5][1:]
        line = fp.readline()
    raise RuntimeError('%s is not managed by CVS' % filename)

def check_root(dirname):
    root_file = os.path.join(dirname, 'CVS', 'Root')
    return open(root_file, 'r').read().strip()


class CVSRepository(Repository):
    """A class used to work with a CVS repository"""

    init_xml_attrs = ['cvsroot', 'password']

    def __init__(self, config, name, cvsroot, password=None):
        Repository.__init__(self, config, name)
        # has the repository path been overridden?
        if self.name in config.repos:
            self.cvsroot = config.repos[name]
        else:
            self.cvsroot = cvsroot
            login(cvsroot, password)

    branch_xml_attrs = ['module', 'checkoutdir', 'revision']

    def branch(self, name, module=None, checkoutdir=None, revision=None):
        if module is None:
            module = name
        # allow remapping of branch for module:
        revision = self.config.branches.get(name, revision)
        return CVSBranch(self, module, checkoutdir, revision)


class CVSBranch(Branch):
    """A class representing a CVS branch inside a CVS repository"""

    def __init__(self, repository, module, checkoutdir, revision):
        self.repository = repository
        self.config = repository.config
        self.module = module
        self.checkoutdir = checkoutdir
        self.revision = revision

    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.config.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.config.checkoutroot, self.module)
    srcdir = property(srcdir)

    def branchname(self):
        return self.revision
    branchname = property(branchname)

    def _checkout(self, buildscript):
        os.chdir(self.config.checkoutroot)
        cmd = ['cvs', '-z3', '-q', '-d', self.repository.cvsroot,
               'checkout', '-P']
        if self.revision:
            cmd.extend(['-r', self.revision])
        if self.config.sticky_date:
            cmd.extend(['-D', self.config.sticky_date])
        if not (self.revision or self.config.sticky_date):
            cmd.append('-A')
        if self.checkoutdir:
            cmd.extend(['-d', self.checkoutdir])
        cmd.append(self.module)
        buildscript.execute(cmd, 'cvs')

    def _update(self, buildscript):
        # sanity check the existing working tree:
        try:
            wc_root = check_root(self.srcdir)
        except IOError:
            raise BuildStateError('"%s" does not appear to be a CVS working '
                                  'copy' % os.path.abspath(self.srcdir))
        if wc_root != self.repository.cvsroot:
            raise BuildStateError('working copy points at the wrong '
                                  'repository (expected %s but got %s). '
                                  'Consider using the changecvsroot.py '
                                  'script to fix this.'
                                  % (self.repository.cvsroot, wc_root))

        # update the working tree
        os.chdir(self.srcdir)
        cmd = ['cvs', '-z3', '-q', '-d', self.repository.cvsroot,
               'update', '-dP']
        if self.revision:
            cmd.extend(['-r', self.revision])
        if self.config.sticky_date:
            cmd.extend(['-D', self.config.sticky_date])
        if not (self.revision or self.config.sticky_date):
            cmd.append('-A')
        cmd.append('.')
        buildscript.execute(cmd, 'cvs')

    def checkout(self, buildscript):
        if os.path.exists(self.srcdir):
            self._update(buildscript)
        else:
            self._checkout(buildscript)

    def force_checkout(self, buildscript):
        self._checkout(buildscript)


register_repo_type('cvs', CVSRepository)
