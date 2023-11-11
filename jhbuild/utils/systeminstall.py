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

from io import StringIO
import os
import sys
import logging
import shlex
import subprocess
import textwrap
import time
import re

from . import cmds
from . import _, udecode

def get_installed_pkgconfigs(config):
    """Returns a dictionary mapping pkg-config names to their current versions on the system."""
    pkgversions = {}
    cmd = ['pkg-config', '--list-all']
    try:
        stdout = subprocess.check_output(cmd, universal_newlines=True)
    except (subprocess.CalledProcessError, OSError): # pkg-config not installed
        logging.error("{} failed".format(cmd))
        return pkgversions

    pkgs = []
    for line in stdout.splitlines():
        pkg, rest = line.split(None, 1)
        pkgs.append(pkg)

    # see if we can get the versions "the easy way"
    try:
        stdout = subprocess.check_output(['pkg-config', '--modversion'] + pkgs, universal_newlines=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError):
        pass
    else:
        versions = stdout.splitlines()
        if len(versions) == len(pkgs):
            return dict(zip(pkgs, versions))

    # We have to rather inefficiently repeatedly fork to work around
    # broken pkg-config installations - if any package has a missing
    # dependency pkg-config will fail entirely.
    for pkg in pkgs:
        cmd = ['pkg-config', '--modversion', pkg]
        try:
            stdout = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, OSError):
            logging.error("{} failed".format(cmd))
            continue
        pkgversions[pkg] = stdout.strip()

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
                    arg = next(itr)
                    if arg.strip() in ['-I', '-isystem']:
                        # extract paths handling quotes and multiple paths
                        paths += shell_split(next(itr))[0].split(os.pathsep)
                    elif arg.startswith('-I'):
                        paths += shell_split(arg[2:])[0].split(os.pathsep)
            except StopIteration:
                pass
            return paths
        try:
            multiarch = udecode(subprocess.check_output(['gcc', '-print-multiarch'])).strip()
        except (EnvironmentError, subprocess.CalledProcessError):
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
        paths += extract_path_from_cflags(config.module_autogenargs.get(
            module_name, ''))
        paths += extract_path_from_cflags(config.module_makeargs.get(
            module_name, ''))
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

        elif dep_type in ('python2', 'python3'):
            command = dep_type
            python_script = textwrap.dedent('''
                import imp
                import sys
                try:
                    imp.find_module(sys.argv[1])
                except:
                    exit(1)
                ''').strip('\n')
            try:
                subprocess.check_call([command, '-c', python_script, value])
            except (subprocess.CalledProcessError, OSError):
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
            except (EnvironmentError, subprocess.CalledProcessError):
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
        # pkexec is broken in toolbox, avoid it if we're running in a toolbox
        if cmds.has_command('pkexec') and not os.path.isfile('/run/.toolboxenv'):
            self._root_command_prefix_args = ['pkexec']
        elif cmds.has_command('sudo'):
            self._root_command_prefix_args = ['sudo']
        else:
            raise SystemExit(_('No suitable root privilege command found; you should install "sudo" or "pkexec" (or the system package that provides it)'))

    def install(self, uninstalled, assume_yes):
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
                from gi.repository import GLib
            except ImportError:
                raise SystemExit(_('Error: python-gobject package not found.'))
            self._loop = GLib.MainLoop()
        if self._sysbus is None:
            try:
                import dbus.glib
            except ImportError:
                raise SystemExit(_('Error: dbus-python package not found.'))
            import dbus
            self._dbus = dbus
            self._sysbus = dbus.SystemBus()
        if self._pkdbus is None:
            self._pkdbus = dbus.Interface(self._sysbus.get_object('org.freedesktop.PackageKit',
                                                                  '/org/freedesktop/PackageKit'),
                                          'org.freedesktop.PackageKit')
        txn_path = self._pkdbus.CreateTransaction()
        txn = self._sysbus.get_object('org.freedesktop.PackageKit', txn_path)
        txn_tx = self._dbus.Interface(txn, 'org.freedesktop.PackageKit.Transaction')
        txn.connect_to_signal('Message', self._on_pk_message)
        txn.connect_to_signal('ErrorCode', self._on_pk_error)
        txn.connect_to_signal('Destroy', lambda *args: self._loop.quit())
        return txn_tx, txn

    def install(self, uninstalled, assume_yes):
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
        logging.info(_("This might take a very long time. Do not turn off your computer. You can run 'pkmon' to monitor progress."))

        txn_tx, txn = self._get_new_transaction()
        txn_tx.InstallPackages(PK_TRANSACTION_FLAG_ENUM_ONLY_TRUSTED, pk_package_ids)
        self._loop.run()

        logging.info(_('Complete!'))

    @classmethod
    def detect(cls):
        return cmds.has_command('pkcon')

class DNFSystemInstall(SystemInstall):
    def __init__(self):
        SystemInstall.__init__(self)

    def install(self, uninstalled, assume_yes):
        uninstalled_pkgconfigs = get_uninstalled_pkgconfigs(uninstalled)
        uninstalled_filenames = get_uninstalled_filenames(uninstalled)
        logging.info(_('Using dnf to install packages.  Please wait.'))
        package_names = set()

        if not uninstalled_filenames and not uninstalled_pkgconfigs:
            logging.info(_('Nothing to install'))
            return

        for name, pkgconfig in uninstalled_pkgconfigs:
            package_names.add('pkgconfig({})'.format(pkgconfig))

        for name, filename in uninstalled_filenames:
            package_names.add(filename)

        if not package_names:
            logging.info(_('Nothing to install'))
            return

        logging.info('Installing:\n  %s' %('\n  '.join(package_names)))
        dnf_command = ['dnf', 'install']
        if assume_yes:
            dnf_command.append('--assumeyes')
        if subprocess.call(self._root_command_prefix_args + dnf_command + list(package_names)):
            logging.error(_('Install failed'))
        else:
            logging.info(_('Completed!'))

    @classmethod
    def detect(cls):
        return cmds.has_command('dnf')

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

    def install(self, uninstalled, assume_yes):
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
                result = udecode(subprocess.check_output(['pkgfile', '--raw', filename]))
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

    def _apt_file_result(self, regexp):
        if regexp is None or regexp == "":
            raise RuntimeError("regexp mustn't be None or empty")
        apt_file_result = subprocess.check_output(["apt-file", "search", "--regexp", regexp])
        apt_file_result = udecode(apt_file_result)
        ret_value = []
        for line in StringIO(apt_file_result):
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            name = parts[0]
            path = parts[1].strip()
            ret_value.append((name, path))
        return ret_value

    def _build_apt_file_path_regexp_exact(self, paths):
        if len(paths) == 0:
            return None
        first_path = paths[0][1]
        if first_path.startswith("/"):
            first_path = first_path[1:]
        ret_value = re.escape(first_path)
        for modname, path in paths[1:]:
            if path.startswith("/"):
                path = path[1:]
            ret_value += "|" + re.escape(path)
        return ret_value

    def _build_apt_file_path_regexp_pc_or_c_includes(self, paths):
        if len(paths) == 0:
            return None
        first_path = paths[0][1]
        if first_path.startswith("/"):
            first_path = first_path[1:]
        ret_value = re.escape(first_path)
        for modname, path in paths[1:]:
            if path.startswith("/"):
                path = path[1:]
            ret_value += "|.*/" + re.escape(path)
        return ret_value

    def _name_match_exact(self, exact_path_to_match, apt_file_result, native_packages):
        for name, path in apt_file_result:
            if path == exact_path_to_match:
                native_packages.append(name)
                return True
        return False

    def _append_native_packages_or_warn_pkgconfig(self, pkgconfigs, native_packages):
        if len(pkgconfigs) == 0:
            return

        def get_pkg_config_search_paths():
            output = subprocess.check_output(
                ["pkg-config", "--variable", "pc_path", "pkg-config"])
            output = udecode(output)
            return output.strip().split(os.pathsep)

        # Various packages include zlib.pc (emscripten, mingw) so look only in
        # the default pkg-config search paths
        search_paths = get_pkg_config_search_paths()
        search_paths = tuple(os.path.join(p, "") for p in search_paths)

        apt_file_result = self._apt_file_result(regexp="\\.pc$")
        for modname, pkg in pkgconfigs:
            for name, path in apt_file_result:
                if path.endswith("/" + pkg) and path.startswith(search_paths):
                    native_packages.append(name)
                    break
            else:
                logging.info(_('No native package found for %(id)s '
                               '(%(filename)s)') % {'id'       : modname,
                                                    'filename' : pkg})

    def _append_native_packages_or_warn_exact(self, paths, native_packages):
        if len(paths) == 0:
            return
        exact_regexp = self._build_apt_file_path_regexp_exact(paths)
        apt_file_result = self._apt_file_result(exact_regexp)
        for modname, path in paths:
            if not self._name_match_exact(path, apt_file_result, native_packages):
                logging.info(_('No native package found for %(id)s '
                               '(%(filename)s)') % {'id'       : modname,
                                                    'filename' : path})

    def _append_native_packages_or_warn_c_includes(self, c_includes, native_packages, multiarch):
        if len(c_includes) == 0:
            return
        c_includes_regexp = self._build_apt_file_path_regexp_pc_or_c_includes(c_includes)
        apt_file_result = self._apt_file_result(c_includes_regexp)
        for modname, filename in c_includes:
            # Try multiarch first, so we print the non-multiarch location on failure.
            if (multiarch is None or
                    not self._name_match_exact('/usr/include/%s/%s' % (multiarch, filename), apt_file_result, native_packages)):
                if not self._name_match_exact('/usr/include/%s' % filename, apt_file_result, native_packages):
                    logging.info(_('No native package found for %(id)s '
                                   '(%(filename)s)') % {'id'       : modname,
                                                        'filename' : filename})

    def _install_packages(self, native_packages, assume_yes):
        logging.info(_('Installing: %(pkgs)s') % {'pkgs': ' '.join(native_packages)})
        apt_cmd_line = ['apt-get']
        if assume_yes is True:
            apt_cmd_line += ['--assume-yes']
        apt_cmd_line += ['install']
        args = self._root_command_prefix_args + apt_cmd_line
        args.extend(native_packages)
        subprocess.check_call(args)

    def install(self, uninstalled, assume_yes):
        if not cmds.has_command('apt-file'):
            logging.info(_('Please install apt-file first.'))
            return

        logging.info(_('Using apt-file to search for providers; this may be extremely slow. Please wait. Patience!'))
        native_packages = []

        pkgconfigs = [(modname, '%s.pc' % pkg) for modname, pkg in
                      get_uninstalled_pkgconfigs(uninstalled)]
        self._append_native_packages_or_warn_pkgconfig(pkgconfigs, native_packages)

        binaries = [(modname, '/usr/bin/%s' % pkg) for modname, pkg in
                    get_uninstalled_binaries(uninstalled)]
        self._append_native_packages_or_warn_exact(binaries, native_packages)

        # Get multiarch include directory, e.g. /usr/include/x86_64-linux-gnu
        multiarch = None
        try:
            multiarch = udecode(subprocess.check_output(['gcc', '-print-multiarch'])).strip()
        except (EnvironmentError, subprocess.CalledProcessError):
            # Really need GCC to continue. Yes, this is fragile.
            self._install_packages(['gcc'])
            multiarch = udecode(subprocess.check_output(['gcc', '-print-multiarch'])).strip()

        c_includes = get_uninstalled_c_includes(uninstalled)
        self._append_native_packages_or_warn_c_includes(c_includes, native_packages, multiarch)

        if native_packages:
            self._install_packages(native_packages, assume_yes=assume_yes)
        else:
            logging.info(_('Nothing to install'))

    @classmethod
    def detect(cls):
        return cmds.has_command('apt')

_classes = [AptSystemInstall, PacmanSystemInstall, DNFSystemInstall, PKSystemInstall]

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    installer = SystemInstall.find_best()
    print("Using %r" % (installer, ))
    installer.install(sys.argv[1:])
