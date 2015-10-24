#!/usr/bin/python

import sys
import os
import stat
import re
import md5
import getopt
import urlparse
import ConfigParser
import xml.dom.minidom

usage = 'mk-tarball-moduleset -d DEPS -u URI -s DIR'
help = \
'''Build a module set from a list of dependencies, a directory of tarballs
and a URI base.

Options:
  -d, --dependencies=FILE   The list of dependencies
  -u, --uri=URI             The base URI for the tarballs
  -s, --source=DIR          Location of tarballs
  -x, --exceptions=FILE     A file including exceptions for sources'''

def read_deps(filename):
    deps = []
    deps_dict = {}
    fp = open(filename)
    line = fp.readline()
    while line:
        pkg, dep_pkgs = line.split(':', 1)
        assert not deps_dict.has_key(pkg), '%s repeated' % pkg
        dep_pkgs = [ dep.strip() for dep in dep_pkgs.split() ]
        deps.append((pkg, dep_pkgs))
        deps_dict[pkg] = dep_pkgs
        line = fp.readline()
    # verify that all dependencies are listed
    for pkg in deps_dict.keys():
        for dep in deps_dict[pkg]:
            assert deps_dict.has_key(dep), 'dependency %s not found' % dep
    return deps

class SourceRepo:
    def __init__(self, sourcedir, uribase, exceptions):
        self.sourcedir = sourcedir
        self.uribase = uribase
        self.exceptions = exceptions

    def _find_tarball(self, pkg):
        '''Find the first file in sourcedir that looks like a tarball for
        the given package.  Bzip2 compressed tarballs are preferred.'''
        files = os.listdir(self.sourcedir)
        pat = re.compile(r'%s-([0-9].*)\.tar\.bz2' % pkg.replace('+', '\\+'))
        for filename in files:
            match = pat.match(filename)
            if match:
                return filename, match.group(1)
        pat = re.compile(r'%s-([0-9].*)\.tar\.gz' % pkg.replace('+', '\\+'))
        for filename in files:
            match = pat.match(filename)
            if match:
                return filename, match.group(1)
        raise RuntimeError('no file found for package %s' % pkg)

    def create_tarball_node(self, document, pkg):
        tarball = document.createElement('tarball')
        tarball.setAttribute('id', pkg)
        tarball.appendChild(document.createTextNode('\n'))
        source_node = document.createElement('source')
        tarball.appendChild(source_node)
        tarball.appendChild(document.createTextNode('\n'))

        if self.exceptions.has_section(pkg):
            tarball.setAttribute('version',
                                 self.exceptions.get(pkg, 'version'))

            source_node.setAttribute('href',
                                     self.exceptions.get(pkg, 'href'))
            source_node.setAttribute('size',
                                     self.exceptions.get(pkg, 'size'))
            source_node.setAttribute('md5sum',
                                     self.exceptions.get(pkg, 'md5sum'))
        else:
            filename, version = self._find_tarball(pkg)
            tarball.setAttribute('version', version)

            source_node.setAttribute('href',
                                     urlparse.urljoin(self.uribase, filename))
            info = os.stat(os.path.join(self.sourcedir, filename))
            size = info[stat.ST_SIZE]
            source_node.setAttribute('size', str(info[stat.ST_SIZE]))

            sum = md5.new()
            fp = open(os.path.join(self.sourcedir, filename), 'rb')
            data = fp.read(4096)
            while data:
                sum.update(data)
                data = fp.read(4096)
            fp.close()
            source_node.setAttribute('md5sum', sum.hexdigest())
        return tarball

def main(args):
    try:
        opts, args = getopt.getopt(args, 'd:u:s:x:h',
                                   ['dependencies=', 'uri=', 'source=',
                                    'exceptions=', 'help'])
    except getopt.error as exc:
        sys.stderr.write('mk-tarball-moduleset: %s\n' % str(exc))
        sys.stderr.write(usage + '\n')
        sys.exit(1)

    dependencies = None
    uri = None
    source = None
    exceptions = ConfigParser.ConfigParser()
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print usage
            print help
            sys.exit(0)
        elif opt in ('-d', '--dependencies'):
            dependencies = arg
        elif opt in ('-u', '--uri'):
            uri = arg
        elif opt in ('-s', '--source'):
            source = arg
        elif opt in ('-x', '--exceptions'):
            exceptions.read(arg)
    if not dependencies or not uri or not source:
        sys.stderr.write(usage + '\n')
        sys.exit(1)

    repo = SourceRepo(source, uri, exceptions)
    deps = read_deps(dependencies)

    document = xml.dom.minidom.Document()
    document.appendChild(document.createElement('moduleset'))
    document.documentElement.appendChild(document.createTextNode('\n'))
    for (pkg, dep_pkgs) in deps:
        if pkg.startswith('meta-'):
            pkg_node = document.createElement('metamodule')
            pkg_node.setAttribute('id', pkg)
            pkg_node.appendChild(document.createTextNode('\n'))
        else:
            pkg_node = repo.create_tarball_node(document, pkg)
        if dep_pkgs:
            deps = document.createElement('dependencies')
            deps.appendChild(document.createTextNode('\n'))
            for dep_pkg in dep_pkgs:
                node = document.createElement('dep')
                node.setAttribute('package', dep_pkg)
                deps.appendChild(node)
                deps.appendChild(document.createTextNode('\n'))
            pkg_node.appendChild(deps)
            pkg_node.appendChild(document.createTextNode('\n'))

        document.documentElement.appendChild(pkg_node)
        document.documentElement.appendChild(document.createTextNode('\n'))

    document.writexml(sys.stdout)
    document.unlink()

if __name__ == '__main__':
    main(sys.argv[1:])
