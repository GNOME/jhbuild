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


class SystemPackages(object):

    def satisfiable(self, name, module):
        """ Returns true if a module is satisfiable by installing a system package """
        return self.is_available(name)

    def satisfied(self, name, module):
        """ Returns true if module is satisfied by an already installed system package """
        return self.is_installed(name)

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

    def __init__(self):
        import apt_pkg
        apt_pkg.InitSystem()
        self.apt_cache = apt_pkg.GetCache()

    def is_installed(self, name, version=None):
        for pkg in self.apt_cache.Packages:
            if pkg.Name == name:
                if not pkg.CurrentVer:
                    return False
                if version and apt_pkg.VersionCompare(version, pkg.CurrentVer.VerStr) > 0:
                    return False
                return True
        return False

    def is_available(self, name, version=None):
        for pkg in self.apt_cache.Packages:
            if pkg.Name == name:
                if version:
                    versions = list(pkg.VersionList)
                    versions.sort(lambda x,y: apt_pkg.VersionCompare(x.VersionStr, y.VersionStr))
                    newest = versions[-1].VerStr
                    if apt_pkg.VersionCompare(version, newest) > 0:
                        return False
                return True
        return False

    def install(self, names):
        buildscript.execute(['apt-get', 'install', ' '.join(name)])

    def remove(self, names):
        buildscript.execute(['apt-get', 'remove', ' '.join(name)])

    def supported(cls):
        try:
            import apt_pkg
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

