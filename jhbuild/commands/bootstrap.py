# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
#
#   bootstrap.py: code to check whether prerequisite modules are installed
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
import urllib
import getopt

from jhbuild.commands.base import register_command
from jhbuild.utils import cmds

term = os.environ.get('TERM', '')
is_xterm = term.find('xterm') >= 0 or term == 'rxvt'
del term
try: t_bold = cmds.get_output('tput bold')
except: t_bold = ''
try: t_reset = cmds.get_output('tput sgr0')
except: t_reset = ''

jhbuild_directory = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 '..', '..'))

class Bootstrap:
    def __init__(self, package, version, sourceurl, sourcesize, patches=[],
                 versioncheck=None):
        self.package = package
        self.version = version
        self.sourceurl = sourceurl
        self.sourcesize = sourcesize
        self.patches = patches
        self.versioncheck = versioncheck
        
    def _bold(self, msg):
        print '%s*** %s ***%s' % (t_bold, msg, t_reset)
        if is_xterm:
            print '\033]0;jhbuild: %s\007' % msg
            
    def _execute(self, command):
        print command
        ret = os.system(command)
        print
        return ret
    
    def wants_package(self):
        self._bold('checking for %s %s' % (self.package, self.version))
        if self.versioncheck:
            out = os.popen(self.versioncheck, 'r').read()
            if out == '':
                print 'package not found'
            elif out.find(self.version.replace('x', '')) >= 0:
                print 'package found'
                val = raw_input('do you want to install %s %s [y/N]? '
                                % (self.package, self.version))
                if val and val.lower()[0] == 'y':
                    return 1
                else:
                    return 0
            else:
                if out[-1] == '\n':
                    out = out[:-1]
                print 'might be okay:'
                print out
        val = raw_input('do you want to install %s %s [Y/n]? '
                        % (self.package, self.version))
        if val and val.lower()[0] == 'n':
            return 0
        return 1

    def build(self, config):
        if not self.wants_package():
            return

        # get the source package
        buildroot = config.checkoutroot
        localfile = os.path.join(buildroot, os.path.basename(self.sourceurl))
        if not os.path.exists(localfile) or \
           os.stat(localfile)[6] != self.sourcesize:
            while 1:
                self._bold('downloading %s' % self.sourceurl)
                try:
                    urllib.urlretrieve(self.sourceurl, localfile)
                    if os.stat(localfile)[6] == self.sourcesize:
                        break # we got the file
                    print 'downloaded file does not match expected size'
                except IOError, e:
                    print 'Could not download file. Exception was: '
                    print e
                val = raw_input('try downloading again? ')
                if val and val.lower()[0] == 'n':
                    return
        
        # untar the source package
        os.chdir(buildroot)
        localfile = os.path.basename(self.sourceurl)
        self._bold('untaring %s' % localfile)
        if localfile.endswith('.bz2'):
            ret = self._execute('bzip2 -dc %s | tar xf -' % localfile)
        else:
            ret = self._execute('gzip -dc %s | tar xf -' % localfile)
        if ret != 0:
            print 'failed to untar', self.package
            return

        # change to package directory
        if localfile.endswith('.tar.gz'):
            os.chdir(localfile[:-7])
        elif localfile.endswith('.tgz'):
            os.chdir(localfile[:-4])
        elif localfile.endswith('.tar.bz2'):
            os.chdir(localfile[:-8])
        else:
            print 'unknown package extension: ', self.package
            return

        # is there a patch to apply?
        for patch_filename, patch_options in self.patches:
            patchfile = os.path.join(jhbuild_directory,
                                     'patches', patch_filename)
            self._bold('applying patch %s' % patch_filename)
            ret = self._execute('patch -p%d < %s' % (patch_options, patchfile))
            if ret != 0:
                print 'failed to patch', self.package
                return

        # configure ...
        self._bold('configuring %s' % self.package)
        cmd = './configure --prefix %s' % config.prefix
        if config.use_lib64:
            cmd += " --libdir '${exec_prefix}/lib64'"
        ret = self._execute(cmd)
        if ret != 0:
            print 'failed to configure', self.package
            return

        # make
        self._bold('building %s' % self.package)
        ret = self._execute('make')
        if ret != 0:
            print 'failed to build', self.package
            return
        
        # install
        self._bold('installing %s' % self.package)
        ret = self._execute('make install')
        if ret != 0:
            print 'failed to install', self.package
            return

bootstraps = [
    Bootstrap('gettext', '0.11.5',
              'http://ftp.gnu.org/gnu/gettext/gettext-0.11.5.tar.gz',
              3724099,
              [('gettext-changelog.patch', 1)],  # patch to unbreak gettext ...
              'gettextize --version | head -1'),
    Bootstrap('autoconf', '2.59',
              'http://ftp.gnu.org/gnu/autoconf/autoconf-2.59.tar.bz2',
              925073,
              [],
	      'autoconf --version | head -1'),
    Bootstrap('libtool', '1.5.2',
              'http://ftp.gnu.org/gnu/libtool/libtool-1.5.2.tar.gz', 
              2653072,
              [('libtool-1.4.3-ltmain-SED.patch', 1),
               ('libtool-1.4.2-multilib.patch', 1),
               ('libtool-1.5-libtool.m4-x86_64.patch', 1)],
              'libtoolize --version | head -1'),
    Bootstrap('automake-1.4', '1.4-p6',
              'http://ftp.gnu.org/gnu/automake/automake-1.4-p6.tar.gz',
              375060,
              [],
              'automake-1.4 --version | head -1'),
    Bootstrap('automake-1.6', '1.6.3',
              'http://ftp.gnu.org/gnu/automake/automake-1.6.3.tar.gz',
              609618,
              [],
              'automake-1.6 --version | head -1'),
    Bootstrap('automake-1.7', '1.7.9',
              'http://ftp.gnu.org/gnu/automake/automake-1.7.9.tar.bz2',
              577705,
              [],
              'automake-1.7 --version | head -1'),
    Bootstrap('automake-1.8', '1.8.2',
              'http://ftp.gnu.org/gnu/automake/automake-1.8.2.tar.bz2', 
              638894,
              [],
              'automake-1.8 --version | head -1'),
    Bootstrap('pkg-config', '0.15.0',
              'http://www.freedesktop.org/software/pkgconfig/releases/pkgconfig-0.15.0.tar.gz',
              610697,
              [],
              'pkg-config --version'),
    Bootstrap('python', '2.x',
              'http://www.python.org/ftp/python/2.3.2/Python-2.3.2.tar.bz2',
              7161770,
              [],
              'echo "import sys; print sys.version.split()[0]" | python -'),
    Bootstrap('audiofile', '0.2.5',
              'http://www.68k.org/~michael/audiofile/audiofile-0.2.5.tar.gz',
              362370, 
              [],
              'audiofile-config --version'),
]

def do_bootstrap(config, args):
    if args:
        raise getopt.error, 'no extra arguments expected'

    for bootstrap in bootstraps:
        bootstrap.build(config)

register_command('bootstrap', do_bootstrap)
