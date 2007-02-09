# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
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

from jhbuild.commands import Command, register_command
from jhbuild.utils.cmds import get_output
from jhbuild.errors import UsageError, FatalError

def check_version(cmd, regexp, minver):
    try:
        data = get_output(cmd)
    except:
        return False
    match = re.match(regexp, data, re.MULTILINE)
    if not match: return False
    version = match.group(1)

    version = version.split('.')
    for i, ver in enumerate(version):
        part = re.sub(r'^[^\d]*(\d+).*$', r'\1', ver)
        if not part:
            version[i] = None
        else:
            version[i] = int(part)
    minver = minver.split('.')
    for i, ver in enumerate(minver):
        part = re.sub(r'^[^\d]*(\d+).*$', r'\1', ver)
        if not part:
            minver[i] = None
        else:
            minver[i] = int(part)
    return version >= minver

def get_aclocal_path(version):
    data = get_output(['aclocal-%s' % version, '--print-ac-dir'])
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


class cmd_sanitycheck(Command):
    """Check that required support tools are available"""

    name = 'sanitycheck'
    usage_args = ''

    def run(self, config, options, args):
        if args:
            raise UsageError('no extra arguments expected')
    
        # check whether the checkout root and install prefix are writable
        if not (os.path.isdir(config.checkoutroot) and
                os.access(config.checkoutroot, os.R_OK|os.W_OK|os.X_OK)):
            print 'checkout root is not writable'
        if not (os.path.isdir(config.prefix) and
                os.access(config.prefix, os.R_OK|os.W_OK|os.X_OK)):
            print 'install prefix is not writable'

        # check whether various tools are installed
        if not check_version(['libtoolize', '--version'],
                             r'libtoolize \([^)]*\) ([\d.]+)', '1.5'):
            print 'libtool >= 1.5 not found'
        if not check_version(['gettext', '--version'],
                             r'gettext \([^)]*\) ([\d.]+)', '0.10.40'):
            print 'gettext >= 0.10.40 not found'
        if not check_version(['pkg-config', '--version'],
                             r'^([\d.]+)', '0.14.0'):
            print 'pkg-config >= 0.14.0 not found'
        if not check_version(['db2html', '--version'],
                             r'.* ([\d.]+)', '0.0'):
            print 'db2html not found'
        if not check_version(['autoconf', '--version'],
                             r'autoconf \([^)]*\) ([\d.]+)', '2.53'):
            print 'autoconf >= 2.53 not found'
        if not check_version(['automake-1.4', '--version'],
                             r'automake \([^)]*\) ([\d.]+)', '1.4'):
            print 'automake-1.4 not found'
        if not check_version(['automake-1.7', '--version'],
                             r'automake \([^)]*\) ([\d.]+)', '1.7'):
            print 'automake-1.7 not found'
        if not check_version(['automake-1.8', '--version'],
                             r'automake \([^)]*\) ([\d.]+)', '1.8'):
            print 'automake-1.8 not found'
        if not check_version(['automake-1.9', '--version'],
                             r'automake \([^)]*\) ([\d.]+)', '1.9'):
            print 'automake-1.9 not found'

        for amver in ('1.4', '1.7', '1.8', '1.9'):
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

        # XML catalog sanity checks
        if not os.access('/etc/xml/catalog', os.R_OK):
            print 'Could not find XML catalog'
        else:
            for (item, name) in [('-//OASIS//DTD DocBook XML V4.1.2//EN',
                                  'DocBook XML DTD V4.1.2'),
                                 ('http://docbook.sourceforge.net/release/xsl/current/html/chunk.xsl',
                                  'DocBook XSL Stylesheets')]:
                try:
                    data = get_output(['xmlcatalog', '/etc/xml/catalog', item])
                except:
                    print 'Could not find %s in XML catalog' % name            

        # Perl modules used by tools such as intltool:
        for perlmod in [ 'XML::Parser' ]:
            try:
                get_output(['perl', '-M%s' % perlmod, '-e', 'exit'])
            except:
                print 'Could not find the perl module %s' % perlmod
                
        # check for cvs:
        if not inpath('cvs', os.environ['PATH'].split(os.pathsep)):
            print 'cvs not found'

        # check for svn:
        if not inpath('svn', os.environ['PATH'].split(os.pathsep)):
            print 'svn not found'

        # check for git:
        if not inpath('git', os.environ['PATH'].split(os.pathsep)):
            print 'git not found'
        else:
            try:
                git_help = os.popen('git --help', 'r').read()
                if not 'clone' in git_help:
                    print 'Installed git program is not the right git'
            except:
                print 'Could not check git program'

        # check for svn:
        if not inpath('svn', os.environ['PATH'].split(os.pathsep)):
            print 'svn not found'

register_command(cmd_sanitycheck)
