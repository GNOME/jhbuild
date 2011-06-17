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
import xml.dom.minidom as DOM
import xml.etree.ElementTree as ET
from StringIO import StringIO

def _parse_isotime(string):
    if string[-1] != 'Z':
        return time.mktime(time.strptime(string, '%Y-%m-%dT%H:%M:%S'))
    tm = time.strptime(string, '%Y-%m-%dT%H:%M:%SZ')
    return time.mktime(tm[:8] + (0,)) - time.timezone    

def _format_isotime(tm):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(tm))

class PackageEntry:
    def __init__(self, package, version, manifest,
                 metadata):
        self.package = package # string
        self.version = version # string
        self.manifest = manifest # list of strings
        self.metadata = metadata # hash of string to value

    @classmethod
    def from_xml(cls, node):
        package = node.attrib['package']
        version = node.attrib['version']
        metadata = {}

        installed_string = node.attrib['installed']
        if installed_string:
            metadata['installed-date'] = _parse_isotime(installed_string)
         
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
        else:
            manifest = None
        return cls(package, version, manifest, metadata)

    def to_xml(self, doc):
        entry_node = ET.Element('entry', {'package': self.package,
                                          'version': self.version})
        if 'installed-date' in self.metadata:
            entry_node.attrib['installed'] = _format_isotime(self.metadata['installed-date'])
        if self.manifest is not None:
            manifest_node = ET.SubElement(entry_node, 'manifest')
            for filename in self.manifest:
                file_node = ET.SubElement(manifest_node, 'file')
                file_node.text = filename
        return entry_node

class PackageDB:
    def __init__(self, dbfile):
        self.dbfile = dbfile
        self._read_cache()

    def _read_cache(self):
        self.entries = {}
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
            entry = PackageEntry.from_xml(node)
            self.entries[entry.package] = entry

    def _write_cache(self):
        pkgdb_node = ET.Element('packagedb')
        doc = ET.ElementTree(pkgdb_node)
        for package,entry in self.entries.iteritems():
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

    def add(self, package, version, destdir):
        '''Add a module to the install cache.'''
        now = time.time()
        contents = self._accumulate_dirtree_contents(destdir)
        metadata = {'installed-date': now}
        self.entries[package] = PackageEntry(package, version, contents, metadata)
        self._write_cache()

    def check(self, package, version=None):
        '''Check whether a particular module is installed.'''
        if not self.entries.has_key(package): return False
        entry = self.entries[package]
        if version is not None:
            if entry.version != version: return False
        return True

    def installdate(self, package, version=None):
        '''Get the install date for a particular module.'''
        if not self.entries.has_key(package): return None
        entry = self.entries[package]
        if version:
            if entry.version != version: return None
        return entry.metadata['installed-date']

    def uninstall(self, package_name, buildscript):
        '''Remove a module from the install cache.'''
        if package_name in self.entries:
            entry = self.entries[package_name]
            if entry.manifest is None:
                buildscript.message("warning: no manifest known for '%s', not deleting files")
            else:
                directories = []
                for path in entry.manifest:
                    assert os.path.isabs(path)
                    if os.path.isdir(path):
                        directories.append(path)
                    else:
                        os.unlink(path)
                        print "Deleted %r" % (path, )
                for directory in directories:
                    if not directory.startswith(buildscript.config.prefix):
                        # Skip non-prefix directories; otherwise we
                        # may try to remove the user's ~ or something
                        # (presumably we'd fail, but better not to try)
                        continue
                    try:
                        os.rmdir(directory)
                        print "Deleted %r" % (path, )
                    except OSError, e:
                        # Allow multiple components to use directories
                        pass
            del self.entries[package_name]
            self._write_cache()
        else:
            buildscript.message("warning: no package known for '%s'")

if __name__ == '__main__':
    db = PackageDB(sys.argv[1])
    print "%r" % (db.entries, )
