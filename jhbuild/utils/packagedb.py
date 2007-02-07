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

import time
try:
    import xml.dom.minidom
except ImportError:
    raise SystemExit, 'Python xml packages are required but could not be found'

def _parse_isotime(string):
    if string[-1] != 'Z':
        return time.mktime(time.strptime(string, '%Y-%m-%dT%H:%M:%S'))
    tm = time.strptime(string, '%Y-%m-%dT%H:%M:%SZ')
    return time.mktime(tm[:8] + (0,)) - time.timezone    

def _format_isotime(tm):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(tm))

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
            package = node.getAttribute('package')
            version = node.getAttribute('version')
            installed = _parse_isotime(node.getAttribute('installed'))
            self.entries[package] = (version, installed)
        document.unlink()

    def _write_cache(self):
        document = xml.dom.minidom.Document()
        document.appendChild(document.createElement('packagedb'))
        node = document.createTextNode('\n')
        document.documentElement.appendChild(node)
        for package in self.entries:
            version, installed = self.entries[package]
            node = document.createElement('entry')
            node.setAttribute('package', package)
            node.setAttribute('version', version)
            node.setAttribute('installed', _format_isotime(installed))
            document.documentElement.appendChild(node)

            node = document.createTextNode('\n')
            document.documentElement.appendChild(node)

        document.writexml(open(self.dbfile, 'w'))
        document.unlink()

    def add(self, package, version):
        '''Add a module to the install cache.'''
        now = time.time()
        self.entries[package] = (version, now)
        self._write_cache()

    def check(self, package, version=None):
        '''Check whether a particular module is installed.'''
        if not self.entries.has_key(package): return False
        p_version, p_installed = self.entries[package]
        if version:
            if version != p_version: return False
        return True

    def installdate(self, package, version=None):
        '''Get the install date for a particular module.'''
        if not self.entries.has_key(package): return None
        p_version, p_installed = self.entries[package]
        if version:
            if version != p_version: return None
        return p_installed
