# jhbuild - a tool to ease building collections of source packages
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
import shlex
import subprocess
import pipes
from StringIO import StringIO

import cmds

def get_installed_pkgconfigs(config):
    """Returns a dictionary mapping pkg-config names to their current versions on the system."""
    pkgversions = {}
    try:
        proc = subprocess.Popen(['pkg-config', '--list-all'], stdout=subprocess.PIPE, env=config.get_original_environment(), close_fds=True)
        stdout = proc.communicate()[0]
        proc.wait()
        pkgs = []
        for line in StringIO(stdout):
            pkg, rest = line.split(None, 1)
            pkgs.append(pkg)
        # We have to rather inefficiently repeatedly fork to work around
        # broken pkg-config installations - if any package has a missing
        # dependency pkg-config will fail entirely.
        for pkg in pkgs:
            args = ['pkg-config', '--modversion']
            args.append(pkg)
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    close_fds=True, env=config.get_original_environment())
            stdout = proc.communicate()[0]
            proc.wait()
            pkgversions[pkg] = stdout.strip()
    except OSError: # pkg-config not installed
        pass
    return pkgversions

def systemdependencies_met(module_name, sysdeps, config):
    '''Returns True of the system dependencies are met for module_name'''
    def get_c_include_search_paths(config):
        '''returns a list of C include paths (-I) from the environment and the
        user's config'''
        def extract_path_from_cflags(args):
            '''extract the C include paths (-I) from a list of arguments (args)
            Returns a list of paths'''
            itr = iter(args.split())
            paths = []
            if os.name == 'nt':
                # shlex.split doesn't handle sep '\' on Windows
                import string
                shell_split = string.split
            else:
                shell_split = shlex.split
            try:
                while True:
                    arg = itr.next()
                    if arg.strip() == '-I':
                        # extract paths handling quotes and multiple paths
                        paths += shell_split(itr.next())[0].split(os.pathsep)
                    elif arg.startswith('-I'):
                        paths += shell_split(arg[2:])[0].split(os.pathsep)
            except StopIteration:
                pass
            return paths
        # search /usr/include by default
        paths = [ os.path.join(os.sep, 'usr', 'include')]
        paths += extract_path_from_cflags(os.environ.get('CPPFLAGS', ''))
        # check include paths incorrectly configured in CFLAGS, CXXFLAGS
        paths += extract_path_from_cflags(os.environ.get('CFLAGS', ''))
        paths += extract_path_from_cflags(os.environ.get('CXXFLAGS', ''))
        # check include paths incorrectly configured in makeargs
        paths += extract_path_from_cflags(config.makeargs)
        paths += extract_path_from_cflags(config.module_autogenargs.get
                                             (module_name, ''))
        paths += extract_path_from_cflags(config.module_makeargs.get
                                             (module_name, ''))
        paths = list(set(paths)) # remove duplicates
        return paths

    c_include_search_paths = None
    for dep_type, value in sysdeps:
        if dep_type.lower() == 'path':
            if os.path.split(value)[0]:
                if not os.path.isfile(value) and not os.access(value, os.X_OK):
                    return False
            else:
                found = False
                for path in os.environ.get('PATH', '').split(os.pathsep):
                    filename = os.path.join(path, value)
                    if (os.path.isfile(filename) and
                        os.access(filename, os.X_OK)):
                        found = True
                        break
                if not found:
                    return False
        elif dep_type.lower() == 'c_include':
            if c_include_search_paths is None:
                c_include_search_paths = get_c_include_search_paths(config)
            found = False
            for path in c_include_search_paths:
                filename = os.path.join(path, value)
                if os.path.isfile(filename):
                    found = True
                    break
            if not found:
                return False
    return True

class SystemInstall(object):
    def __init__(self):
        if cmds.has_command('pkexec'):
            self._root_command_prefix_args = ['pkexec']
        elif cmds.has_command('sudo'):
            self._root_command_prefix_args = ['sudo']
        else:
            raise SystemExit, _('No suitable root privilege command found; you should install "pkexec"')

    def install(self, pkgconfig_ids):
        """Takes a list of pkg-config identifiers and uses a system-specific method to install them."""
        raise NotImplementedError()

    @classmethod
    def find_best(cls):
        global _classes
        for possible_cls in _classes:
            if possible_cls.detect():
                return possible_cls()

# PackageKit dbus interface contains bitfield constants which
# aren't introspectable
PK_PROVIDES_ANY = 1
PK_FILTER_ENUM_NOT_INSTALLED = 1 << 3
PK_FILTER_ENUM_NEWEST = 1 << 16
PK_FILTER_ENUM_ARCH = 1 << 18

# NOTE: This class is unfinished
class PKSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)

    def _on_pk_message(self, msgtype, msg):
        logging.info(_('PackageKit: %s' % (msg,)))

    def _on_pk_error(self, msgtype, msg):
        logging.error(_('PackageKit: %s' % (msg,)))

    def install(self, pkgconfig_ids):
        import dbus
        import dbus.glib
        import glib

        # PackageKit 0.8.1 has API breaks in the D-BUS interface, for now
        # we try to support both it and older PackageKit
        using_pk_0_8_1 = False

        loop = glib.MainLoop()
        
        sysbus = dbus.SystemBus()
        pk = dbus.Interface(sysbus.get_object('org.freedesktop.PackageKit',
                                              '/org/freedesktop/PackageKit'),
                            'org.freedesktop.PackageKit')
        try:
            txn_path = pk.CreateTransaction()
            txn = sysbus.get_object('org.freedesktop.PackageKit', txn_path)
            using_pk_0_8_1 = True
        except dbus.exceptions.DBusException:
            tid = pk.GetTid()
            txn = sysbus.get_object('org.freedesktop.PackageKit', tid)

        txn_tx = dbus.Interface(txn, 'org.freedesktop.PackageKit.Transaction')
        txn.connect_to_signal('Message', self._on_pk_message)
        txn.connect_to_signal('ErrorCode', self._on_pk_error)
        txn.connect_to_signal('Destroy', lambda *args: loop.quit())

        pk_package_ids = set()
        txn.connect_to_signal('Package', lambda info, pkid, summary: pk_package_ids.add(pkid))
        if using_pk_0_8_1:
            txn_tx.WhatProvides(PK_FILTER_ENUM_ARCH | PK_FILTER_ENUM_NEWEST | PK_FILTER_ENUM_NOT_INSTALLED,
                                PK_PROVIDES_ANY,
                                ['pkgconfig(%s)' % pkg for pkg in pkgconfig_ids])
        else:
            txn_tx.WhatProvides("arch;newest;~installed", "any",
                                ['pkgconfig(%s)' % pkg for pkg in pkgconfig_ids])
        loop.run()

        del txn

        if len(pk_package_ids) == 0:
            logging.info(_('Nothing available to install'))
            return

        logging.info(_('Installing: %s' % (' '.join(pk_package_ids, ))))

        if using_pk_0_8_1:
            txn_path = pk.CreateTransaction()
            txn = sysbus.get_object('org.freedesktop.PackageKit', txn_path)
        else:
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

class YumSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)

    def install(self, pkgconfig_ids):
        logging.info(_('Using yum to install packages.  Please wait.'))

        native_packages = []
        for pkgconfig in pkgconfig_ids:
            native_packages.append('pkgconfig(' + pkgconfig + ')')

        if native_packages:
            logging.info(_('Installing: %(pkgs)s') % {'pkgs': ' '.join(native_packages)})
            args = self._root_command_prefix_args + ['yum', '-y', 'install']
            args.extend(native_packages)
            subprocess.check_call(args)
        else:
            logging.info(_('Nothing to install'))

    @classmethod
    def detect(cls):
        return cmds.has_command('yum')


class AptSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)

    def _get_package_for(self, pkg_config):
        pattern = '/%s.pc' % (pkg_config, )
        proc = subprocess.Popen(['apt-file', 'search', pattern],
                                stdout=subprocess.PIPE, close_fds=True)
        stdout = proc.communicate()[0]
        if proc.returncode != 0:
            return None
        pkg = None
        for line in StringIO(stdout):
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            name = parts[0]
            path = parts[1]
            # No idea why the LSB has forks of the pkg-config files
            if path.find('/lsb3') != -1:
                continue
            
            # otherwise for now, just take the first match
            return name

    def install(self, pkgconfig_ids):
        logging.info(_('Using apt-file to search for providers; this may be slow.  Please wait.'))
        native_packages = []
        for pkgconfig in pkgconfig_ids:
            native_pkg = self._get_package_for(pkgconfig)
            if native_pkg:
                native_packages.append(native_pkg)
            else:
                logging.info(_('No native package found for %(id)s') % {'id': pkgconfig})
            
        if native_packages:
            logging.info(_('Installing: %(pkgs)s') % {'pkgs': ' '.join(native_packages)})
            args = self._root_command_prefix_args + ['apt-get', 'install']
            args.extend(native_packages)
            subprocess.check_call(args)
        else:
            logging.info(_('Nothing to install'))

    @classmethod
    def detect(cls):
        return cmds.has_command('apt-file')

# Ordered from best to worst
_classes = [AptSystemInstall, PKSystemInstall, YumSystemInstall]

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    installer = SystemInstall.find_best()
    print "Using %r" % (installer, )
    installer.install(sys.argv[1:])
