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
import imp
import time
from StringIO import StringIO

import cmds

def get_installed_pkgconfigs(config):
    """Returns a dictionary mapping pkg-config names to their current versions on the system."""
    pkgversions = {}
    try:
        proc = subprocess.Popen(['pkg-config', '--list-all'], stdout=subprocess.PIPE, close_fds=True)
        stdout = proc.communicate()[0]
        proc.wait()
        pkgs = []
        for line in StringIO(stdout):
            pkg, rest = line.split(None, 1)
            pkgs.append(pkg)

        # see if we can get the versions "the easy way"
        try:
            stdout = subprocess.check_output(['pkg-config', '--modversion'] + pkgs)
            versions = stdout.splitlines()
            if len(versions) == len(pkgs):
                return dict(zip(pkgs, versions))
        except OSError:
            pass

        # We have to rather inefficiently repeatedly fork to work around
        # broken pkg-config installations - if any package has a missing
        # dependency pkg-config will fail entirely.
        for pkg in pkgs:
            args = ['pkg-config', '--modversion']
            args.append(pkg)
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            stdout = proc.communicate()[0]
            proc.wait()
            pkgversions[pkg] = stdout.strip()
    except OSError: # pkg-config not installed
        pass
    return pkgversions

def get_uninstalled_pkgconfigs_and_filenames(uninstalled):
    uninstalled_pkgconfigs = []
    uninstalled_filenames = []

    for module_name, dep_type, value in uninstalled:
        if dep_type == 'pkgconfig':
            uninstalled_pkgconfigs.append((module_name, value))
        elif dep_type.lower() == 'path':
            uninstalled_filenames.append((module_name, os.path.join('/usr/bin', value)))
        elif dep_type.lower() == 'c_include':
            uninstalled_filenames.append((module_name, os.path.join('/usr/include', value)))

    return uninstalled_pkgconfigs, uninstalled_filenames

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
                    if arg.strip() in ['-I', '-isystem']:
                        # extract paths handling quotes and multiple paths
                        paths += shell_split(itr.next())[0].split(os.pathsep)
                    elif arg.startswith('-I'):
                        paths += shell_split(arg[2:])[0].split(os.pathsep)
            except StopIteration:
                pass
            return paths
        try:
            multiarch = subprocess.check_output(['gcc', '-print-multiarch']).strip()
        except:
            multiarch = None
        # search /usr/include and its multiarch subdir (if any) by default
        paths = [ os.path.join(os.sep, 'usr', 'include')]
        if multiarch:
            paths += [ os.path.join(paths[0], multiarch) ]
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
        paths += os.environ.get('C_INCLUDE_PATH', '').split(':')
        paths += os.environ.get('CPLUS_INCLUDE_PATH', '').split(':')
        paths = list(set(paths)) # remove duplicates
        return paths

    c_include_search_paths = None
    for dep_type, value, altdeps in sysdeps:
        dep_met = True
        if dep_type.lower() == 'path':
            if os.path.split(value)[0]:
                if not os.path.isfile(value) and not os.access(value, os.X_OK):
                    dep_met = False
            else:
                pathdirs = set(os.environ.get('PATH', '').split(os.pathsep))
                pathdirs.update(['/sbin', '/usr/sbin'])
                for path in pathdirs:
                    filename = os.path.join(path, value)
                    if os.path.isfile(filename) and os.access(filename, os.X_OK):
                        break
                else:
                    dep_met = False
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
                dep_met = False

        elif dep_type == 'python2':
            try:
                imp.find_module(value)
            except:
                dep_met = False

        elif dep_type == 'xml':
            xml_catalog = '/etc/xml/catalog'

            if not os.path.exists(xml_catalog):
                for d in os.environ['XDG_DATA_DIRS'].split(':'):
                    xml_catalog = os.path.join(d, 'xml', 'catalog')
                    if os.path.exists(xml_catalog):
                        break

            try:
                # no xmlcatalog installed will (correctly) fail the check
                subprocess.check_output(['xmlcatalog', xml_catalog, value])

            except:
                dep_met = False

        # check alternative dependencies
        if not dep_met and altdeps:
            for altdep in altdeps:
                if systemdependencies_met(module_name, [ altdep ], config):
                    dep_met = True
                    break

        if not dep_met:
            return False

    return True

class SystemInstall(object):
    def __init__(self):
        if cmds.has_command('pkexec'):
            self._root_command_prefix_args = ['pkexec']
        elif cmds.has_command('sudo'):
            self._root_command_prefix_args = ['sudo']
        else:
            raise SystemExit(_('No suitable root privilege command found; you should install "pkexec"'))

    def install(self, uninstalled):
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
PK_TRANSACTION_FLAG_ENUM_ONLY_TRUSTED = 1 << 1

# NOTE: This class is unfinished
class PKSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)
        self._loop = None
        self._sysbus = None
        self._pkdbus = None

    def _on_pk_message(self, msgtype, msg):
        logging.info(_('PackageKit: %s' % (msg,)))

    def _on_pk_error(self, msgtype, msg):
        logging.error(_('PackageKit: %s' % (msg,)))

    def _get_new_transaction(self):
        if self._loop is None:
            import glib
            self._loop = glib.MainLoop()
        if self._sysbus is None:
            import dbus.glib
            import dbus
            self._dbus = dbus
            self._sysbus = dbus.SystemBus()
        if self._pkdbus is None:
            self._pkdbus = dbus.Interface(self._sysbus.get_object('org.freedesktop.PackageKit',
                                              '/org/freedesktop/PackageKit'),
                            'org.freedesktop.PackageKit')
            properties = dbus.Interface(self._pkdbus, 'org.freedesktop.DBus.Properties')
            self._pk_major = properties.Get('org.freedesktop.PackageKit', 'VersionMajor')
            self._pk_minor = properties.Get('org.freedesktop.PackageKit', 'VersionMinor')
        if self._pk_major == 1 or (self._pk_major == 0 and self._pk_minor >= 8):
            txn_path = self._pkdbus.CreateTransaction()
            txn = self._sysbus.get_object('org.freedesktop.PackageKit', txn_path)
        else:
            tid = self._pkdbus.GetTid()
            txn = self._sysbus.get_object('org.freedesktop.PackageKit', tid)
        txn_tx = self._dbus.Interface(txn, 'org.freedesktop.PackageKit.Transaction')
        txn.connect_to_signal('Message', self._on_pk_message)
        txn.connect_to_signal('ErrorCode', self._on_pk_error)
        txn.connect_to_signal('Destroy', lambda *args: self._loop.quit())
        return txn_tx, txn

    def install(self, uninstalled):
        uninstalled_pkgconfigs, uninstalled_filenames = get_uninstalled_pkgconfigs_and_filenames(uninstalled)
        pk_package_ids = set()

        if uninstalled_pkgconfigs:
            txn_tx, txn = self._get_new_transaction()
            txn.connect_to_signal('Package', lambda info, pkid, summary: pk_package_ids.add(pkid))
            if self._pk_major == 1 or (self._pk_major == 0 and self._pk_minor >= 9):
                # PackageKit 1.0.x or 0.9.x
                txn_tx.WhatProvides(PK_FILTER_ENUM_ARCH | PK_FILTER_ENUM_NEWEST |
                                    PK_FILTER_ENUM_NOT_INSTALLED,
                                    ['pkgconfig(%s)' % pkg for modname, pkg in
                                     uninstalled_pkgconfigs])
            elif self._pk_major == 0 and self._pk_minor == 8:
                # PackageKit 0.8.x
                txn_tx.WhatProvides(PK_FILTER_ENUM_ARCH | PK_FILTER_ENUM_NEWEST |
                                    PK_FILTER_ENUM_NOT_INSTALLED,
                                    PK_PROVIDES_ANY,
                                    ['pkgconfig(%s)' % pkg for modname, pkg in
                                     uninstalled_pkgconfigs])
            else:
                # PackageKit 0.7.x and older
                txn_tx.WhatProvides('arch;newest;~installed', 'any',
                                    ['pkgconfig(%s)' % pkg for modname, pkg in
                                     uninstalled_pkgconfigs])
            self._loop.run()
            del txn, txn_tx

        if uninstalled_filenames:
            txn_tx, txn = self._get_new_transaction()
            txn.connect_to_signal('Package', lambda info, pkid, summary: pk_package_ids.add(pkid))
            if self._pk_major == 1 or (self._pk_major == 0 and self._pk_minor >= 8):
                txn_tx.SearchFiles(PK_FILTER_ENUM_ARCH | PK_FILTER_ENUM_NEWEST |
                                   PK_FILTER_ENUM_NOT_INSTALLED,
                                   [pkg for modname, pkg in
                                    uninstalled_filenames])
            else:
                txn_tx.SearchFiles('arch;newest;~installed',
                                   [pkg for modname, pkg in
                                    uninstalled_filenames])
            self._loop.run()
            del txn, txn_tx

        # On Fedora 17 a file can be in two packages: the normal package and
        # an older compat- package. Don't install compat- packages.
        pk_package_ids = [pkg for pkg in pk_package_ids
                          if not pkg.startswith('compat-')]

        if len(pk_package_ids) == 0:
            logging.info(_('Nothing available to install'))
            return

        logging.info(_('Installing:\n  %s' % ('\n  '.join(pk_package_ids, ))))

        txn_tx, txn = self._get_new_transaction()
        if self._pk_major == 1 or (self._pk_major == 0 and self._pk_minor >= 8):
            # Using OnlyTrusted might break package installation on rawhide,
            # where packages are unsigned, but this prevents users of normal
            # distros with signed packages from seeing security warnings. It
            # would be better to simulate the transaction first to decide
            # whether OnlyTrusted will work before using it. See
            # http://www.freedesktop.org/software/PackageKit/gtk-doc/introduction-ideas-transactions.html
            txn_tx.InstallPackages(PK_TRANSACTION_FLAG_ENUM_ONLY_TRUSTED, pk_package_ids)
        else:
            # PackageKit 0.7.x and older
            txn_tx.InstallPackages(True, pk_package_ids)
        self._loop.run()

        logging.info(_('Complete!'))

    @classmethod
    def detect(cls):
        return cmds.has_command('pkcon')

class PacmanSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)
        self._pacman_install_args = ['pacman', '-S', '--asdeps', '--needed', '--quiet', '--noconfirm']

    def _maybe_update_pkgfile(self):
        if not cmds.has_command('pkgfile'):
            logging.info(_('pkgfile not found, automatically installing'))
            if subprocess.call(self._root_command_prefix_args + self._pacman_install_args + ['pkgfile',]):
                logging.error(_('Failed to install pkgfile'))
                raise SystemExit

        # Update the pkgfile cache if it is older than 1 day.
        cacheexists = bool(os.listdir('/var/cache/pkgfile'))
        if not cacheexists or os.stat('/var/cache/pkgfile').st_mtime < time.time() - 86400:
            logging.info(_('pkgfile cache is old or doesn\'t exist, automatically updating'))
            result = subprocess.call(self._root_command_prefix_args + ['pkgfile', '--update'])
            if result and not cacheexists:
                logging.error(_('Failed to create pkgfile cache'))
                raise SystemExit
            elif result:
                logging.warning(_('Failed to update pkgfile cache'))
            else:
                logging.info(_('Successfully updated pkgfile cache'))

    def install(self, uninstalled):
        uninstalled_pkgconfigs, uninstalled_filenames = get_uninstalled_pkgconfigs_and_filenames(uninstalled)
        logging.info(_('Using pacman to install packages.  Please wait.'))
        package_names = set()

        if not uninstalled_filenames and not uninstalled_pkgconfigs:
            logging.info(_('Nothing to install'))
            return

        self._maybe_update_pkgfile()

        for name, pkgconfig in uninstalled_pkgconfigs:
            # Just throw the pkgconfigs in the normal file list
            uninstalled_filenames.append((None, '/usr/lib/pkgconfig/%s.pc' %pkgconfig))

        for name, filename in uninstalled_filenames:
            try:
                result = subprocess.check_output(['pkgfile', '--raw', filename])
                if result:
                    package_names.add(result.split('\n')[0])
            except subprocess.CalledProcessError:
                logging.warning(_('Provider for "%s" was not found, ignoring' %(name if name else filename)))

        if not package_names:
            logging.info(_('Nothing to install'))
            return

        logging.info('Installing:\n  %s' %('\n  '.join(package_names)))
        if subprocess.call(self._root_command_prefix_args + self._pacman_install_args + list(package_names)):
            logging.error(_('Install failed'))
        else:
            logging.info(_('Completed!'))

    @classmethod
    def detect(cls):
        if cmds.has_command('pacman'):
            return True
        return False

class YumSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)

    def install(self, uninstalled):
        uninstalled_pkgconfigs, uninstalled_filenames = get_uninstalled_pkgconfigs_and_filenames(uninstalled)
        logging.info(_('Using yum to install packages.  Please wait.'))

        if len(uninstalled_pkgconfigs) + len(uninstalled_filenames) > 0:
            logging.info(_('Installing:\n  %(pkgs)s') %
                         {'pkgs': '\n  '.join([modname for modname, pkg in
                                               uninstalled_pkgconfigs +
                                               uninstalled_filenames])})
            args = self._root_command_prefix_args + ['yum', '-y', 'install']
            args.extend(['pkgconfig(%s)' % pkg for modname, pkg in
                         uninstalled_pkgconfigs])
            args.extend([pkg for modname, pkg in uninstalled_filenames])
            subprocess.check_call(args)
        else:
            logging.info(_('Nothing to install'))

    @classmethod
    def detect(cls):
        return cmds.has_command('yum')


class AptSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)

    def _get_package_for(self, filename):
        proc = subprocess.Popen(['apt-file', 'search', filename],
                                stdout=subprocess.PIPE, close_fds=True)
        stdout = proc.communicate()[0]
        if proc.returncode != 0:
            return None
        for line in StringIO(stdout):
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            name = parts[0]
            path = parts[1]
            # Ignore copies of the pkg-config files that are not from the
            # libraries.
            if '/lsb3' in path:
                continue
            if '/emscripten' in path:
                continue

            # otherwise for now, just take the first match
            return name

    def install(self, uninstalled):
        uninstalled_pkgconfigs, uninstalled_filenames = get_uninstalled_pkgconfigs_and_filenames(uninstalled)
        logging.info(_('Using apt-file to search for providers; this may be slow.  Please wait.'))
        native_packages = []
        pkgconfigs = [(modname, '/%s.pc' % pkg) for modname, pkg in
                      uninstalled_pkgconfigs]
        for modname, filename in pkgconfigs + uninstalled_filenames:
            native_pkg = self._get_package_for(filename)
            if native_pkg:
                native_packages.append(native_pkg)
            else:
                logging.info(_('No native package found for %(id)s '
                               '(%(filename)s)') % {'id'       : modname,
                                                   'filename' : filename})

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
_classes = [AptSystemInstall, PacmanSystemInstall, PKSystemInstall, YumSystemInstall]

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    installer = SystemInstall.find_best()
    print "Using %r" % (installer, )
    installer.install(sys.argv[1:])
