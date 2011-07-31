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
import time
import logging
import xml.dom.minidom as DOM

try:
    import xml.etree.ElementTree as ET
except ImportError:
    import elementtree.ElementTree as ET

from StringIO import StringIO

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
            os.fdatasync(fd.fileno())
            fd.close()
            os.rename(os.path.join(self.manifests_dir, self.package + '.tmp'),
                      os.path.join(self.manifests_dir, self.package))
        return entry_node

class PackageDB:
    def __init__(self, dbfile, config):
        self.dbfile = dbfile
        self.manifests_dir = os.path.join(os.path.dirname(dbfile), 'manifests')
        if not os.path.exists(self.manifests_dir):
            os.makedirs(self.manifests_dir)
        self.config = config
        self._entries = None

    def _ensure_cache(function):
        def decorate(self, *args, **kwargs):
            if self._entries is None:
                self._read_cache()
            function(self, *args, **kwargs)
        return decorate

    def _read_cache(self):
        self._entries = {}
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

    def _accumulate_dirtree_contents_recurse(self, path, contents):
        assert os.path.isdir(path)
        names = os.listdir(path)
        for name in names:
            subpath = os.path.join(path, name)
            if os.path.isdir(subpath):
                contents.append(subpath + '/')
                self._accumulate_dirtree_contents_recurse(subpath, contents)
            else:
                contents.append(subpath)

    def _accumulate_dirtree_contents(self, path):
        contents = []
        self._accumulate_dirtree_contents_recurse(path, contents)
        if not path.endswith('/'):
            path = path + '/'
        pathlen = len(path)
        for i,subpath in enumerate(contents):
            assert subpath.startswith(path)
            # Strip the temporary prefix, then make it absolute again for our target
            contents[i] = '/' + subpath[pathlen:]
        return contents

    @_ensure_cache
    def get(self, package):
        '''Return entry if package is installed, otherwise return None.'''
        return self._entries.get(package)

    @_ensure_cache
    def add(self, package, version, destdir):
        '''Add a module to the install cache.'''
        now = time.time()
        metadata = {'installed-date': now}
        self._entries[package] = PackageEntry(package, version, metadata, self.manifests_dir)
        self._entries[package].manifest = self._accumulate_dirtree_contents(destdir)
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
    def uninstall(self, package_name):
        '''Remove a module from the install cache.'''
        entry = self._entries[package_name]

        if entry.manifest is None:
            logging.error(_("no manifest for '%s', can't uninstall.  Try building again, then uninstalling.") % (package_name,))
            return

        directories = []
        for path in entry.manifest:
            assert os.path.isabs(path)
            if os.path.isdir(path):
                directories.append(path)
            else:
                try:
                    os.unlink(path)
                    logging.info(_("Deleted: %s" % (path, )))
                except OSError, e:
                    logging.warn(_("Failed to delete %(file)r: %(msg)s") % { 'file': path,
                                                                             'msg': e.strerror})
                        
        for directory in directories:
            if not directory.startswith(self.config.prefix):
                # Skip non-prefix directories; otherwise we
                # may try to remove the user's ~ or something
                # (presumably we'd fail, but better not to try)
                continue
            try:
                os.rmdir(directory)
                logging.info(_("Deleted: %s" % (directory, )))
            except OSError, e:
                # Allow multiple components to use directories
                pass
        del self._entries[package_name]
        self._write_cache()

if __name__ == '__main__':
    db = PackageDB(sys.argv[1])
    print "%r" % (db._entries, )
