# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2009  Codethink Ltd.
#
#   systempackage.py:  Infrastructure for interacting with installed packages
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
#
# Authors:
#   John Carr <john.carr@unrouted.co.uk>

import os

class SystemPackages(object):

    def __init__(self):
        self.aliases = {}

        af = os.path.join(".", "aliases", self.aliasesfile)
        tmp = {}
        if os.path.exists(af+'.generated'):
            execfile(af+'.generated', tmp)
            self.aliases.update(tmp['aliases'])
        if os.path.exists(af):
            execfile(af, tmp)
            self.aliases.update(tmp['aliases'])

    def get_pkgname(self, name):
        if name in self.aliases:
            return self.aliases[name]
        return name

    def satisfiable(self, name, module):
        """ Returns true if a module is satisfiable by installing a system package """
        return self.is_available(self.get_pkgname(name))

    def satisfied(self, name, module):
        """ Returns true if module is satisfied by an already installed system package """
        return self.is_installed(self.get_pkgname(name))

    def is_installed(self, name, version=None):
        return False

    def is_available(self, name, version=None):
        return False

    def install(self, names):
        raise UnimplementedError

    def remove(self, names):
        raise UnimplementedError

    def supported(cls):
        return False
    supported = classmethod(supported)


class PackageKitPackages(SystemPackages):
    pass


class DebianPackages(SystemPackages):

    aliasesfile = "debian.aliases"

    def __init__(self):
        super(DebianPackages, self).__init__()
        import apt
        self.apt_cache = apt.Cache()

    def is_installed(self, name, version=None):
        if name not in self.apt_cache.keys():
            return False
        pkg = self.apt_cache[name]
        if not pkg.isInstalled:
            return False
        if version and apt.VersionCompare(version, pkg.installed.version) > 0:
            return False
        return True

    def is_available(self, name, version=None):
        if name not in self.apt_cache.keys():
            return False
        if version:
            pkg = self.apt_cache[name]
            if apt.candidate and apt.VersionCompare(version, apt.candidate.version) > 0:
                return False
        return True

    def install(self, names):
        fetchprogress = apt.progress.TextFetchProgress()
        installprogress = apt.progress.InstallProgress()
        cache = apt.Cache()
        for name in names:
            cache[name].markInstall()
        cache.commit(fetchprogress, installprogress)
        cache.open(apt.progress.OpProgress())

    def remove(self, names):
        cache = apt.Cache()
        for name in names:
            cache[name].markDelete()
        cache.commit()
        cache.open()

    def supported(cls):
        try:
            import apt
            return True
        except ImportError:
            return False
    supported = classmethod(supported)


system_packages = None

def get_system_packages():
    global system_packages
    if not system_packages:
        for c in SystemPackages.__subclasses__():
            if c.supported():
                system_packages = c()
                break
        else:
            system_packages = SystemPackages()
    return system_packages

