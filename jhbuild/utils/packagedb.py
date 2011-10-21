# jhbuild - a build script for GNOME 1.x and 2.x
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
import sys 
import stat
import time
import logging
import xml.dom.minidom as DOM

from jhbuild.utils import lockfile

try:
    import xml.etree.ElementTree as ET
except ImportError:
    import elementtree.ElementTree as ET

from StringIO import StringIO

from jhbuild.utils import fileutils

def _parse_isotime(string):
    if string[-1] != 'Z':
        return time.mktime(time.strptime(string, '%Y-%m-%dT%H:%M:%S'))
    tm = time.strptime(string, '%Y-%m-%dT%H:%M:%SZ')
    return time.mktime(tm[:8] + (0,)) - time.timezone    

def _format_isotime(tm):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(tm))

class PackageEntry:
    def __init__(self, package, version, metadata, manifests_dir):
        self.package = package # string
        self.version = version # string
        self.metadata = metadata # hash of string to value
        self.manifests_dir = manifests_dir

    _manifest = None
    def get_manifest(self):
        if self._manifest:
            return self._manifest
        if not os.path.exists(os.path.join(self.manifests_dir, self.package)):
            return None
        self._manifest = []
        for line in file(os.path.join(self.manifests_dir, self.package)):
            self._manifest.append(line.strip())
        return self._manifest

    def set_manifest(self, value):
        if value is None:
            self._manifest = value
            return
        self._manifest = [x.strip() for x in value if not '\n' in value]
        if len(self._manifest) != len(value):
            logging.error(_('package %s has files with embedded new lines') % self.package)

    manifest = property(get_manifest, set_manifest)

    @classmethod
    def from_xml(cls, node, manifests_dir):
        package = node.attrib['package']
        version = node.attrib['version']
        metadata = {}

        installed_string = node.attrib['installed']
        if installed_string:
            metadata['installed-date'] = _parse_isotime(installed_string)

        dbentry = cls(package, version, metadata, manifests_dir)

        # Transition code for the time when the list of files were stored
        # in list of xml nodes
        manifestNode = node.find('manifest')
        if manifestNode is not None:
            manifest = []
            for manifest_child in manifestNode:
                if manifest_child.tag != 'file':
                    continue
                # The strip here is important since presently we
                # "pretty print" which adds whitespace around <file>.
                # Since we don't handle files with whitespace in their
                # names anyways, it's a fine hack.
                manifest.append(manifest_child.text.strip())
            dbentry.manifest = manifest

        return dbentry


    def to_xml(self, doc):
        entry_node = ET.Element('entry', {'package': self.package,
                                          'version': self.version})
        if 'installed-date' in self.metadata:
            entry_node.attrib['installed'] = _format_isotime(self.metadata['installed-date'])
        if self.manifest is not None:
            fd = file(os.path.join(self.manifests_dir, self.package + '.tmp'), 'w')
            fd.write('\n'.join(self.manifest))
            if hasattr(os, 'fdatasync'):
                os.fdatasync(fd.fileno())
            else:
                os.fsync(fd.fileno())
            fd.close()
            os.rename(os.path.join(self.manifests_dir, self.package + '.tmp'),
                      os.path.join(self.manifests_dir, self.package))
        return entry_node

class PackageDB:
    def __init__(self, dbfile, config):
        self.dbfile = dbfile
        dirname = os.path.dirname(dbfile)
        self.manifests_dir = os.path.join(dirname, 'manifests')
        if not os.path.exists(self.manifests_dir):
            os.makedirs(self.manifests_dir)
        self.config = config
        self._lock = lockfile.LockFile.get(os.path.join(dirname, 'packagedb.xml.lock'))
        self._entries = None # hash
        self._entries_stat = None # os.stat structure

    def _ensure_cache(function):
        def decorate(self, *args, **kwargs):
            if self._entries is None:
                self._read_cache()
            elif self._entries_stat is None:
                # It didn't exist before, see if it does now
                self._read_cache()
            else:
                try:
                    stbuf = os.stat(self.dbfile)
                except OSError, e:
                    pass
                if not (self._entries_stat[stat.ST_INO] == stbuf[stat.ST_INO]
                        and self._entries_stat[stat.ST_MTIME] == stbuf[stat.ST_MTIME]):
                    logging.info(_('Package DB modified externally, rereading'))
                    self._read_cache()
            return function(self, *args, **kwargs)
        return decorate

    def _read_cache(self):
        self._entries = {}
        self._entries_stat = None
        try:
            f = open(self.dbfile)
        except OSError, e:
            return # treat as empty cache
        except IOError, e:
            return
        doc = ET.parse(f)
        root = doc.getroot()
        if root.tag != 'packagedb':
            return # doesn't look like a cache
        for node in root:
            if node.tag != 'entry':
                continue
            entry = PackageEntry.from_xml(node, self.manifests_dir)
            self._entries[entry.package] = entry
        self._entries_stat = os.fstat(f.fileno())

    def _write_cache(self):
        pkgdb_node = ET.Element('packagedb')
        doc = ET.ElementTree(pkgdb_node)
        for package,entry in self._entries.iteritems():
            node = entry.to_xml(doc)
            pkgdb_node.append(node)

        tmp_dbfile_path = self.dbfile + '.tmp'
        tmp_dbfile = open(tmp_dbfile_path, 'w')
        
        # Because ElementTree can't pretty-print, we convert it to a string
        # and then read it back with DOM, then write it out again.  Yes, this
        # is lame.
        # http://renesd.blogspot.com/2007/05/pretty-print-xml-with-python.html
        buf = StringIO()
        doc.write(buf, encoding='UTF-8')
        dom_doc = DOM.parseString(buf.getvalue())
        try:
            dom_doc.writexml(tmp_dbfile, addindent='  ', newl='\n', encoding='UTF-8')
        except:
            tmp_dbfile.close()
            os.unlink(tmp_dbfile_path)
            raise
        tmp_dbfile.flush()
        os.fsync(tmp_dbfile.fileno())
        tmp_dbfile.close()
        os.rename(tmp_dbfile_path, self.dbfile)
        # Ensure we don't reread what we already have cached
        self._entries_stat = os.stat(self.dbfile)

    def _locked(function):
        def decorate(self, *args, **kwargs):
            self._lock.lock()
            try:
                function(self, *args, **kwargs)
            finally:
                self._lock.unlock()
        return decorate

    @_ensure_cache
    def get(self, package):
        '''Return entry if package is installed, otherwise return None.'''
        return self._entries.get(package)

    @_ensure_cache
    @_locked
    def add(self, package, version, contents):
        '''Add a module to the install cache.'''
        now = time.time()
        metadata = {'installed-date': now}
        self._entries[package] = PackageEntry(package, version, metadata, self.manifests_dir)
        self._entries[package].manifest = contents
        self._write_cache()

    def check(self, package, version=None):
        '''Check whether a particular module is installed.'''
        entry = self.get(package)
        if entry is None:
            return False
        if version is not None:
            if entry.version != version: return False
        return True

    def installdate(self, package, version=None):
        '''Get the install date for a particular module.'''
        entry = self.get(package)
        if entry is None:
            return None
        if version and (entry.version != version):
            return None
        return entry.metadata['installed-date']

    @_ensure_cache
    @_locked
    def uninstall(self, package_name):
        '''Remove a module from the install cache.'''
        entry = self._entries[package_name]

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

        del self._entries[package_name]
        self._write_cache()

if __name__ == '__main__':
    db = PackageDB(sys.argv[1])
    print "%r" % (db._entries, )
