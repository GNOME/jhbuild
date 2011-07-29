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
import pipes
from StringIO import StringIO

import cmds

def get_installed_pkgconfigs(config):
    """Returns a dictionary mapping pkg-config names to their current versions on the system."""
    proc = subprocess.Popen(['pkg-config', '--list-all'], stdout=subprocess.PIPE, env=config.get_original_environment(), close_fds=True)
    stdout = proc.communicate()[0]
    proc.wait()
    pkgs = []
    for line in StringIO(stdout):
        pkg, rest = line.split(None, 1)
        pkgs.append(pkg)
    args = ['pkg-config', '--modversion']
    args.extend(pkgs)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, close_fds=True)
    stdout = proc.communicate()[0]
    proc.wait()
    pkgversions = {}
    for pkg,verline in zip(pkgs, StringIO(stdout)):
        pkgversions[pkg] = verline.strip()
    return pkgversions

class SystemInstall(object):
    def __init__(self):
        pass

    def install(self, pkgconfig_ids):
        """Takes a list of pkg-config identifiers and uses a system-specific method to install them."""
        raise NotImplementedError()

    @classmethod
    def find_best(cls):
        global _classes
        for possible_cls in _classes:
            if possible_cls.detect():
                return possible_cls()

# NOTE: This class is unfinished
class PKSystemInstall(SystemInstall):
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

    def _on_pk_message(self, msgtype, msg):
        logging.info(_('PackageKit: %s' % (msg,)))

    def _on_pk_error(self, msgtype, msg):
        logging.error(_('PackageKit: %s' % (msg,)))

    def install(self, pkgconfig_ids):
        import dbus
        import dbus.glib
        import glib

        loop = glib.MainLoop()
        
        sysbus = dbus.SystemBus()
        pk = dbus.Interface(sysbus.get_object('org.freedesktop.PackageKit',
                                              '/org/freedesktop/PackageKit'),
                            'org.freedesktop.PackageKit')
        tid = pk.GetTid()
        txn = sysbus.get_object('org.freedesktop.PackageKit', tid)
        txn_tx = dbus.Interface(txn, 'org.freedesktop.PackageKit.Transaction')
        txn.connect_to_signal('Message', self._on_pk_message)
        txn.connect_to_signal('ErrorCode', self._on_pk_error)
        txn.connect_to_signal('Destroy', lambda *args: loop.quit())

        pk_package_ids = set()
        txn.connect_to_signal('Package', lambda info, pkid, summary: pk_package_ids.add(pkid))
        txn_tx.WhatProvides("arch;newest;~installed", "any", map(lambda x: 'pkgconfig(%s)' % (x, ), pkgconfig_ids))
        loop.run()

        del txn

        if len(pk_package_ids) == 0:
            logging.info(_('Nothing available to install'))
            return

        logging.info(_('Installing: %s' % (' '.join(pk_package_ids, ))))

        tid = pk.GetTid()
        txn = sysbus.get_object('org.freedesktop.PackageKit', tid)
        txn_tx = dbus.Interface(txn, 'org.freedesktop.PackageKit.Transaction')
        txn.connect_to_signal('Message', self._on_pk_message)
        txn.connect_to_signal('ErrorCode', self._on_pk_error)
        txn.connect_to_signal('Destroy', lambda *args: loop.quit())

        txn_tx.InstallPackages(True, pk_package_ids)
        loop.run()

        logging.info(_('Complete!'))

    @classmethod
    def detect(cls):
        return cmds.has_command('pkcon')

# Ordered from best to worst
_classes = [PKSystemInstall]

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    installer = SystemInstall.find_best()
    print "Using %r" % (installer, )
    installer.install(sys.argv[1:])
