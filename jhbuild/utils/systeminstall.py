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
        except (subprocess.CalledProcessError, OSError):
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
    except (subprocess.CalledProcessError, OSError): # pkg-config not installed
        pass
    return pkgversions

def get_uninstalled_pkgconfigs(uninstalled):
    uninstalled_pkgconfigs = []
    for module_name, dep_type, value in uninstalled:
        if dep_type == 'pkgconfig':
            uninstalled_pkgconfigs.append((module_name, value))
    return uninstalled_pkgconfigs

def get_uninstalled_binaries(uninstalled):
    uninstalled_binaries = []
    for module_name, dep_type, value in uninstalled:
        if dep_type.lower() == 'path':
            uninstalled_binaries.append((module_name, value))
    return uninstalled_binaries

def get_uninstalled_c_includes(uninstalled):
    uninstalled_c_includes = []
    for module_name, dep_type, value in uninstalled:
        if dep_type.lower() == 'c_include':
            uninstalled_c_includes.append((module_name, value))
    return uninstalled_c_includes

# This function returns uninstalled binaries and C includes as filenames.
# Backends should use either this OR the functions above.
def get_uninstalled_filenames(uninstalled):
    uninstalled_filenames = []
    for module_name, dep_type, value in uninstalled:
        if dep_type.lower() == 'path':
            uninstalled_filenames.append((module_name, os.path.join('/usr/bin', value)))
        elif dep_type.lower() == 'c_include':
            uninstalled_filenames.append((module_name, os.path.join('/usr/include', value)))
    return uninstalled_filenames

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

    def install(self, uninstalled, install_options):
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
            try:
                import glib
            except:
                try:
                    from gi.repository import GLib as glib
                except:
                    raise SystemExit(_('Error: python-gobject package not found.'))
            self._loop = glib.MainLoop()
        if self._sysbus is None:
            try:
                import dbus.glib
            except:
                raise SystemExit(_('Error: dbus-python package not found.'))
            import dbus
            self._dbus = dbus
            self._sysbus = dbus.SystemBus()
        if self._pkdbus is None:
            self._pkdbus = dbus.Interface(self._sysbus.get_object('org.freedesktop.PackageKit',
                                                                  '/org/freedesktop/PackageKit'),
                                          'org.freedesktop.PackageKit')
            properties = dbus.Interface(self._pkdbus, 'org.freedesktop.DBus.Properties')
        txn_path = self._pkdbus.CreateTransaction()
        txn = self._sysbus.get_object('org.freedesktop.PackageKit', txn_path)
        txn_tx = self._dbus.Interface(txn, 'org.freedesktop.PackageKit.Transaction')
        txn.connect_to_signal('Message', self._on_pk_message)
        txn.connect_to_signal('ErrorCode', self._on_pk_error)
        txn.connect_to_signal('Destroy', lambda *args: self._loop.quit())
        return txn_tx, txn

    def install(self, uninstalled, install_options):
        """Computes packages and installs them.
        @param install_options ignored
        """
        logging.info(_('Computing packages to install. This might be slow. Please wait.'))
        pk_package_ids = set()
        uninstalled_pkgconfigs = get_uninstalled_pkgconfigs(uninstalled)
        if uninstalled_pkgconfigs:
            txn_tx, txn = self._get_new_transaction()
            txn.connect_to_signal('Package', lambda info, pkid, summary: pk_package_ids.add(pkid))
            txn_tx.WhatProvides(PK_FILTER_ENUM_ARCH | PK_FILTER_ENUM_NEWEST |
                                PK_FILTER_ENUM_NOT_INSTALLED,
                                ['pkgconfig(%s)' % pkg for modname, pkg in
                                 uninstalled_pkgconfigs])
            self._loop.run()
            del txn, txn_tx

        uninstalled_filenames = get_uninstalled_filenames(uninstalled)
        if uninstalled_filenames:
            txn_tx, txn = self._get_new_transaction()
            txn.connect_to_signal('Package', lambda info, pkid, summary: pk_package_ids.add(pkid))
            txn_tx.SearchFiles(PK_FILTER_ENUM_ARCH | PK_FILTER_ENUM_NEWEST |
                               PK_FILTER_ENUM_NOT_INSTALLED,
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
        logging.info(_('This might take a very long time. Do not turn off your computer. You can run `pkmon\' to monitor progress.'))

        txn_tx, txn = self._get_new_transaction()
        txn_tx.InstallPackages(PK_TRANSACTION_FLAG_ENUM_ONLY_TRUSTED, pk_package_ids)
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

    def install(self, uninstalled, install_options):
        """Computes packages and installs them.
        @param install_options ignored
        """
        uninstalled_pkgconfigs = get_uninstalled_pkgconfigs(uninstalled)
        uninstalled_filenames = get_uninstalled_filenames(uninstalled)
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

class AptSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)

    def _get_package_for(self, filename, exact_match):
        if exact_match:
            proc = subprocess.Popen(['apt-file', '--fixed-string', 'search', filename],
                                    stdout=subprocess.PIPE, close_fds=True)
        else:
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

    def _try_append_native_package(self, modname, filename, native_packages, exact_match):
        native_pkg = self._get_package_for(filename, exact_match)
        if native_pkg:
            native_packages.append(native_pkg)
            return True
        return False

    def _append_native_package_or_warn(self, modname, filename, native_packages, exact_match):
        if not self._try_append_native_package(modname, filename, native_packages, exact_match):
            logging.info(_('No native package found for %(id)s '
                           '(%(filename)s)') % {'id'       : modname,
                                                'filename' : filename})

    def _install_packages(self, native_packages, install_options):
        """Computes packages and installs them.
        @param install_options options passed to `apt-get` before the `install`
        subcommand (see `man apt-get` for details)
        """
        logging.info(_('Installing: %(pkgs)s') % {'pkgs': ' '.join(native_packages)})
        apt_cmd_line = ['apt-get']
        if install_options != None:
            apt_cmd_line += str.split(install_options)
        apt_cmd_line += ['install']
        args = self._root_command_prefix_args + apt_cmd_line
        args.extend(native_packages)
        subprocess.check_call(args)

    def install(self, uninstalled, install_options):
        logging.info(_('Using apt-file to search for providers; this may be extremely slow. Please wait. Patience!'))
        native_packages = []

        pkgconfigs = [(modname, '/%s.pc' % pkg) for modname, pkg in
                      get_uninstalled_pkgconfigs(uninstalled)]
        for modname, filename in pkgconfigs:
            self._append_native_package_or_warn(modname, filename, native_packages, False)

        binaries = [(modname, '/usr/bin/%s' % pkg) for modname, pkg in
                    get_uninstalled_binaries(uninstalled)]
        for modname, filename in binaries:
            self._append_native_package_or_warn(modname, filename, native_packages, True)

        # Get multiarch include directory, e.g. /usr/include/x86_64-linux-gnu
        multiarch = None
        try:
            multiarch = subprocess.check_output(['gcc', '-print-multiarch']).strip()
        except:
            # Really need GCC to continue. Yes, this is fragile.
            self._install_packages(['gcc'])
            multiarch = subprocess.check_output(['gcc', '-print-multiarch']).strip()

        c_includes = get_uninstalled_c_includes(uninstalled)
        for modname, filename in c_includes:
            # Try multiarch first, so we print the non-multiarch location on failure.
            if (multiarch == None or
                not self._try_append_native_package(modname, '/usr/include/%s/%s' % (multiarch, filename), native_packages, True)):
                self._append_native_package_or_warn(modname, '/usr/include/%s' % filename, native_packages, True)

        if native_packages:
            self._install_packages(native_packages, install_options=install_options)
        else:
            logging.info(_('Nothing to install'))

    @classmethod
    def detect(cls):
        return cmds.has_command('apt-file')

# Ordered from best to worst
_classes = [AptSystemInstall, PacmanSystemInstall, PKSystemInstall]

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    installer = SystemInstall.find_best()
    print "Using %r" % (installer, )
    installer.install(sys.argv[1:])
