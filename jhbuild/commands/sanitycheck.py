# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   sanitycheck.py: check whether build environment is sane
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
import re

from jhbuild.commands.base import register_command

def get_output(cmd):
    fp = os.popen('{ %s; } 2>&1' % cmd, 'r')
    data = fp.read()
    status = fp.close()
    if status and (not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0):
        raise RuntimeError('program exited abnormally')
    return data

def check_version(cmd, regexp, minver):
    try:
        data = get_output(cmd)
    except:
        return False
    match = re.match(regexp, data, re.MULTILINE)
    if not match: return False
    version = match.group(1)

    version = version.split('.')
    for i in range(len(version)):
        part = re.sub(r'^[^\d]*(\d+).*$', r'\1', version[i])
        if not part:
            version[i] = None
        else:
            version[i] = int(part)
    minver = minver.split('.')
    for i in range(len(minver)):
        part = re.sub(r'^[^\d]*(\d+).*$', r'\1', minver[i])
        if not part:
            minver[i] = None
        else:
            minver[i] = int(part)
    return version >= minver

def get_aclocal_path(version):
    data = get_output('aclocal-%s --print-ac-dir' % version)
    path = [data[:-1]]
    env = os.environ.get('ACLOCAL_FLAGS', '').split()
    i = 0
    while i < len(env):
        if env[i] == '-I':
            path.append(env[i+1])
            i = i + 2
        else:
            i = i + 1
    return path

def inpath(filename, path):
    for dir in path:
        if os.path.isfile(os.path.join(dir, filename)):
            return True
    return False

def do_sanitycheck(config, args):
    # check whether various tools are installed
    if not check_version('libtoolize --version',
                         r'libtoolize \([^)]*\) ([\d.]+)', '1.5'):
        print 'libtool >= 1.5 not found'
    if not check_version('gettext --version',
                         r'gettext \([^)]*\) ([\d.]+)', '0.10.40'):
        print 'gettext >= 0.10.40 not found'
    if not check_version('pkg-config --version',
                         r'^([\d.]+)', '0.14.0'):
        print 'pkg-config >= 0.14.0 not found'
    if not check_version('autoconf --version',
                         r'autoconf \([^)]*\) ([\d.]+)', '2.53'):
        print 'autoconf >= 2.53 not found'
    if not check_version('automake-1.4 --version',
                         r'automake \([^)]*\) ([\d.]+)', '1.4'):
        print 'automake-1.4 not found'
    if not check_version('automake-1.6 --version',
                         r'automake \([^)]*\) ([\d.]+)', '1.6'):
        print 'automake-1.6 not found'
    if not check_version('automake-1.7 --version',
                         r'automake \([^)]*\) ([\d.]+)', '1.7'):
        print 'automake-1.7 not found'
    if not check_version('automake-1.8 --version',
                         r'automake \([^)]*\) ([\d.]+)', '1.8'):
        print 'automake-1.8 not found'

    for amver in ('1.4', '1.6', '1.7', '1.8'):
        try:
            path = get_aclocal_path(amver)
        except:
            continue # exception raised if aclocal-ver not runnable

        if not inpath('libtool.m4', path):
            print "aclocal-%s can't see libtool macros" % amver
        if not inpath('gettext.m4', path):
            print "aclocal-%s can't see gettext macros" % amver
        if not inpath('pkg.m4', path):
            print "aclocal-%s can't see pkg-config macros" % amver

register_command('sanitycheck', do_sanitycheck)
