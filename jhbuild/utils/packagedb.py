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
import time
try:
    import xml.dom.minidom
except ImportError:
    raise SystemExit, _('Python xml packages are required but could not be found')

def _parse_isotime(string):
    if string[-1] != 'Z':
        return time.mktime(time.strptime(string, '%Y-%m-%dT%H:%M:%S'))
    tm = time.strptime(string, '%Y-%m-%dT%H:%M:%SZ')
    return time.mktime(tm[:8] + (0,)) - time.timezone    

def _format_isotime(tm):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(tm))

def _get_text_content(node):
    content = ''
    for child in node.childNodes:
        if (child.nodeType == child.TEXT_NODE):
            content += child.nodeValue
    return content

def _list_from_xml(node, child_name):
    """Parse XML like:
        <foolist>
            <item>content</item>
            <item>more content</item>
            ...
        </foolist>."""
    result = []
    for child in node.childNodes:
        if not (child.nodeType == child.ELEMENT_NODE and child.nodeName == child_name):
            continue
        result.append(_get_text_content(child))
    return result

def _find_node(node, child_name):
    """Get the first child node named @child_name"""
    for child in node.childNodes:
        if not (child.nodeType == child.ELEMENT_NODE and child.nodeName == child_name):
            continue
        return child
    return None

class PackageEntry:
    def __init__(self, package, version, manifest,
                 metadata):
        self.package = package # string
        self.version = version # string
        self.manifest = manifest # list of strings
        self.metadata = metadata # hash of string to value

    @classmethod
    def from_xml(cls, node):
        package = node.getAttribute('package')
        version = node.getAttribute('version')
        metadata = {}

        installed_string = node.getAttribute('installed')
        if installed_string:
            metadata['installed-date'] = _parse_isotime(installed_string)

        manifestNode = _find_node(node, 'manifest')
        if manifestNode:
            manifest = _list_from_xml(manifestNode, 'file')
        else:
            manifest = None
        return cls(package, version, manifest, metadata)

    def to_xml(self, document):
        entryNode = document.createElement('entry')
        entryNode.setAttribute('package', self.package)
        entryNode.setAttribute('version', self.version)
        if 'installed-date' in self.metadata:
            entryNode.setAttribute('installed', _format_isotime(self.metadata['installed-date']))
        entryNode.appendChild(document.createTextNode('\n'))
        if self.manifest is not None:
            manifestNode = document.createElement('manifest')
            entryNode.appendChild(manifestNode)
            manifestNode.appendChild(document.createTextNode('\n'))
            for filename in self.manifest:
                node = document.createElement('file')
                node.appendChild(document.createTextNode(filename))
                manifestNode.appendChild(document.createTextNode('  '))
                manifestNode.appendChild(node)
                manifestNode.appendChild(document.createTextNode('\n'))
            entryNode.appendChild(document.createTextNode('\n'))
        return entryNode

class PackageDB:
    def __init__(self, dbfile):
        self.dbfile = dbfile
        self._read_cache()

    def _read_cache(self):
        self.entries = {}
        try:
            document = xml.dom.minidom.parse(self.dbfile)
        except:
            return # treat as empty cache
        if document.documentElement.nodeName != 'packagedb':
            document.unlink()
            return # doesn't look like a cache
        for node in document.documentElement.childNodes:
            if node.nodeType != node.ELEMENT_NODE: continue
            if node.nodeName != 'entry': continue
            
            entry = PackageEntry.from_xml(node)
            self.entries[entry.package] = entry
        document.unlink()

    def _write_cache(self):
        document = xml.dom.minidom.Document()
        document.appendChild(document.createElement('packagedb'))
        node = document.createTextNode('\n')
        document.documentElement.appendChild(node)
        for package,entry in self.entries.iteritems():
            node = entry.to_xml(document)
            document.documentElement.appendChild(node)
            node = document.createTextNode('\n')
            document.documentElement.appendChild(node)

        tmp_dbfile_path = self.dbfile + '.tmp'
        tmp_dbfile = open(tmp_dbfile_path, 'w')
        try:
            document.writexml(tmp_dbfile)
        except:
            tmp_dbfile.close()
            os.unlink(tmp_dbfile_path)
            raise
        tmp_dbfile.close()
        os.rename(tmp_dbfile_path, self.dbfile)
        document.unlink()

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
                    print "Deleting %r" % (path, )
                    if os.path.isdir(path):
                        directories.append(path)
                    else:
                        os.unlink(path)
                for directory in directories:
                    if not directory.startswith(buildscript.prefix):
                        # Skip non-prefix directories; otherwise we
                        # may try to remove the user's ~ or something
                        # (presumably we'd fail, but better not to try)
                        continue
                    try:
                        os.rmdir(directory)
                    except OSError, e:
                        # Allow multiple components to use directories
                        pass
            del self.entries[package_name]
            self._write_cache()
        else:
            buildscript.message("warning: no package known for '%s'")
