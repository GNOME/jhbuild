# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   packagedb.py - a registry of installed packages
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
import time
import logging
import errno
import hashlib

import xml.etree.ElementTree as ET

from jhbuild.utils import fileutils, _, open_text

def _parse_isotime(string):
    if string[-1] != 'Z':
        return time.mktime(time.strptime(string, '%Y-%m-%dT%H:%M:%S'))
    tm = time.strptime(string, '%Y-%m-%dT%H:%M:%SZ')
    return time.mktime(tm[:8] + (0,)) - time.timezone    

def _format_isotime(tm):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(tm))

class PackageEntry:
    def __init__(self, package, version, metadata, dirname):
        self.package = package # string
        self.version = version # string
        self.metadata = metadata # hash of string to value
        self.dirname = dirname

    _manifest = None

    @property
    def manifest(self):
        if self._manifest:
            return self._manifest
        if not os.path.exists(os.path.join(self.dirname, 'manifests', self.package)):
            return None
        self._manifest = []
        for line in open_text(os.path.join(self.dirname, 'manifests', self.package)):
            self._manifest.append(line.strip())
        return self._manifest

    @manifest.setter
    def manifest(self, value):
        if value is None:
            self._manifest = value
            return
        self._manifest = [x.strip() for x in value if '\n' not in value]
        if len(self._manifest) != len(value):
            logging.error(_('package %s has files with embedded new lines') % self.package)

    def write(self):
        # write info file
        fileutils.mkdir_with_parents(os.path.join(self.dirname, 'info'))
        writer = fileutils.SafeWriter(os.path.join(self.dirname, 'info', self.package))
        ET.ElementTree(self.to_xml()).write(writer.fp)
        writer.fp.write(b'\n')
        writer.commit()

        # write manifest
        fileutils.mkdir_with_parents(os.path.join(self.dirname, 'manifests'))
        writer = fileutils.SafeWriter(os.path.join(self.dirname, 'manifests', self.package))
        writer.fp.write('\n'.join(self.manifest).encode('utf-8', 'backslashreplace') + b'\n')
        writer.commit()

    def remove(self):
        # remove info file
        fileutils.ensure_unlinked(os.path.join(self.dirname, 'info', self.package))

        # remove manifest
        fileutils.ensure_unlinked(os.path.join(self.dirname, 'manifests', self.package))

    def to_xml(self):
        entry_node = ET.Element('entry', {'package': self.package,
                                          'version': self.version})
        if 'installed-date' in self.metadata:
            entry_node.attrib['installed'] = _format_isotime(self.metadata['installed-date'])
        if 'configure-hash' in self.metadata:
            entry_node.attrib['configure-hash'] = \
                self.metadata['configure-hash']

        return entry_node

    @classmethod
    def from_xml(cls, node, dirname):
        package = node.attrib['package']
        version = node.attrib['version']
        metadata = {}

        installed_string = node.attrib['installed']
        if installed_string:
            metadata['installed-date'] = _parse_isotime(installed_string)
        configure_hash = node.attrib.get('configure-hash')
        if configure_hash:
            metadata['configure-hash'] = configure_hash

        dbentry = cls(package, version, metadata, dirname)

        return dbentry

    @classmethod
    def open(cls, dirname, package):
        try:
            with open(os.path.join (dirname, 'info', package), "rb") as info:
                doc = ET.parse(info)
            node = doc.getroot()

            if node.tag == 'entry':
                return PackageEntry.from_xml(node, dirname)

        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise

        # That didn't work: try the old packagedb.xml file instead.  We
        # use the manifest file to check if the package 'really exists'
        # because otherwise we may see the old packagedb.xml entry for
        # an uninstalled package (since we no longer update that file)
        #
        # please delete this code in 2016
        try:
            if os.path.exists(os.path.join(dirname, 'manifests', package)):
                info = open (os.path.join (dirname, 'packagedb.xml'))
                doc = ET.parse(info)
                root = doc.getroot()

                if root.tag == 'packagedb':
                    for node in root:
                        if node.tag == 'entry' and node.attrib['package'] == package:
                            return PackageEntry.from_xml(node, dirname)

        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise

        # it seems not to exist...
        return None

class PackageDB:
    def __init__(self, dbfile, config):
        self.dirname = os.path.dirname(dbfile)
        self.config = config

    def get(self, package):
        '''Return entry if package is installed, otherwise return None.'''
        return PackageEntry.open(self.dirname, package)

    def add(self, package, version, contents, configure_cmd = None):
        '''Add a module to the install cache.'''
        entry = self.get(package)
        if entry:
            metadata = entry.metadata
        else:
            metadata = {}
        metadata['installed-date'] = time.time() # now
        if configure_cmd:
            metadata['configure-hash'] = hashlib.md5(configure_cmd.encode("utf-8")).hexdigest()
        pkg = PackageEntry(package, version, metadata, self.dirname)
        pkg.manifest = contents
        pkg.write()

    def check(self, package, version=None):
        '''Check whether a particular module is installed.'''
        entry = self.get(package)
        if entry is None:
            return False
        if version is not None:
            if entry.version != version:
                return False
        return True

    def installdate(self, package, version=None):
        '''Get the install date for a particular module.'''
        entry = self.get(package)
        if entry is None:
            return None
        if version and (entry.version != version):
            return None
        return entry.metadata['installed-date']

    def uninstall(self, package_name):
        '''Remove a module from the install cache.'''
        entry = self.get(package_name)

        if entry is None:
            raise KeyError

        if entry.manifest is None:
            logging.error(_("no manifest for '%s', can't uninstall.  Try building again, then uninstalling.") % (package_name,))
            return

        # Skip files that aren't in the prefix; otherwise we
        # may try to remove the user's ~ or something
        # (presumably we'd fail, but better not to try)
        to_delete = fileutils.filter_files_by_prefix(self.config, entry.manifest)

        # Don't warn on non-empty directories; we want to allow multiple
        # modules to share the same directory.  We could improve this by
        # reference-counting directories.
        for (path, was_deleted, error_string) in fileutils.remove_files_and_dirs(to_delete, allow_nonempty_dirs=True):
            if was_deleted:
                logging.info(_("Deleted: %(file)r") % {'file': path})
            elif error_string is None:
                pass
            else:
                logging.warn(_("Failed to delete %(file)r: %(msg)s") % { 'file': path,
                                                                         'msg': error_string})

        entry.remove()
