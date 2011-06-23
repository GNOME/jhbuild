# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2011  Colin Walters <walters@verbum.org>
#
#   systeminstall.py - Use system-specific means to acquire dependencies
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
import sys 
import logging
import subprocess
from StringIO import StringIO

import cmds

_classes = []

class SystemInstall(object):
    def __init__(self):
        pass

    def install(self, pkgconfig_ids):
        """Takes a list of pkg-config identifiers and uses a system-specific method to install them."""
        raise NotImplementedError()

    @classmethod
    def get_installed_pkgconfig(cls):
        """Returns a dictionary mapping pkg-config names to their current versions on the system."""
        env = dict(os.environ)
        if 'PKG_CONFIG_PATH' in env:
            del env['PKG_CONFIG_PATH']
        proc = subprocess.Popen(['pkg-config', '--list-all'], stdout=subprocess.PIPE, env=env, close_fds=True)
        stdout = proc.communicate()[0]
        proc.wait()
        pkgs = []
        for line in StringIO(stdout):
            pkg, rest = line.split(None, 1)
            pkgs.append(pkg + '.pc')
        args = ['pkg-config', '--modversion']
        args.extend(map(lambda x: x[:-3], pkgs))
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, close_fds=True)
        stdout = proc.communicate()[0]
        proc.wait()
        pkgversions = {}
        for pkg,verline in zip(pkgs, StringIO(stdout)):
            pkgversions[pkg] = verline.strip()
        return pkgversions

    @classmethod
    def find_best(cls):
        for possible_cls in _classes:
            if possible_cls.detect():
                return possible_cls()

class YumSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)

    def install(self, pkgconfig_ids):
        # Explicitly qualify so we don't get the one in jhbuild root
        args = ['/usr/bin/pkexec', 'yum', 'install']
        pkgconfig_provides = map(lambda x: 'pkgconfig(' + x[:-3] + ')', pkgconfig_ids)
        args.extend(pkgconfig_provides)
        subprocess.check_call(args, close_fds=True)

    @classmethod
    def detect(cls):
        return cmds.has_command('yum')

_classes.append(YumSystemInstall)

# NOTE: This class is unfinished
class PkconSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)

    def _get_package_for(self, pkg_config):
        assert pkg_config.endswith('.pc')
        pkg_config = pkg_config[:-3]
        proc = subprocess.Popen(['pkcon', '-p', 'what-provides', 'pkgconfig(%s)' % (pkg_config, ),
                                 '--filter=arch;newest'], stdout=subprocess.PIPE, close_fds=True)
        devnull.close()
        stdout = proc.communicate()[0]
        if proc.ecode != 0:
            return None
        pkg = None
        for line in StringIO(stdout):
            if line.startswith('Package:'):
                pkg = line[line.find(':') + 1:].strip()
                break
        return pkg

    def install(self, pkgconfig_ids):
        required_pkgs = []
        for pkg_config in pkgconfig_ids:
            if not pkg.endswith('.pc'):
                logging.warn("Invalid pkg-config id " + pkg)
                continue
            providing_pkg = self._get_package_for(pkg_config)
            if providing_pkg is not None:
                required_pkgs.append(providing_pkg)

    @classmethod
    def detect(cls):
        return cmds.has_command('pkcon')

_classes.append(PkconSystemInstall)

if __name__ == '__main__':
    installer = SystemInstall.find_best()
    print "Using %r" % (installer, )
    installer.install(sys.argv[1:])
