#!/usr/bin/env python2

# Run this script like so:
#
#  jhbuild -m gnome-world sysdeps --dump-all `jhbuild -m gnome-world list -a` | ./update-debian-sysdeps.py ../data/debian-sysdeps.py

import urlgrabber.progress
import urlgrabber
import gzip
import sys
import os

# in general, we aim to support (roughly):
#
#  - Debian: oldstable, stable, testing, unstable
#
#  - Ubuntu: last LTS, last stable, current unstable
#
# note for Debian: sid seems to identify itself in os-release under the
#                  codename of the current testing release, so we probably
#                  won't see 'unstable' here separately
releases = {
  'debian-7':       'http://ftp.debian.org/debian/dists/wheezy/main',
  'debian-8':       'http://ftp.debian.org/debian/dists/jessie/main',
  'ubuntu-14.04':   'http://archive.ubuntu.com/ubuntu/dists/trusty',
  'ubuntu-14.10':   'http://archive.ubuntu.com/ubuntu/dists/utopic',
  'ubuntu-15.04':   'http://archive.ubuntu.com/ubuntu/dists/vivid'
}

# We always search using Contents-amd64 under the premise that the package
# names for the dependency won't change depending on the arch.  We can
# therefore freely hardcode 'x86_64-linue-gnu' below.
#
# python2 is currently a bit of a hack since we always assume 2.7, but
# that seems to be a valid assumption for now
c_include_paths = ['/usr/include', '/usr/include/x86_64-linux-gnu']
pkgconfig_paths = ['/usr/lib/x86_64-linux-gnu/pkgconfig', '/usr/lib/pkgconfig', '/usr/share/pkgconfig']
path_paths = ['/usr/bin', '/usr/sbin', '/bin', '/sbin']
python2_paths = ['/usr/lib/python2.7/dist-packages']

# things that we know we won't find, either because we're not clever
# enough (xml), because of alternatives (not listed in apt-file), or
# because they are not available and not required on Debian
hints = {
  'xml:http://docbook.sourceforge.net/release/xsl/current/':         ['docbook-xsl'],
  'path:cc':                                                         ['gcc', 'clang'],
  'path:c++':                                                        ['g++', 'clang'],
  'path:automake':                                                   ['automake'],
  'path:bogofilter':                                                 ['bogofilter'],
  'path:ruby':                                                       ['ruby'],  # needed for wheezy
  'pkgconfig:bdw-gc-threaded':                                       [], # FreeBSD-only
  '' : []
}

def add_paths(mapping, key, prefixes, name):
    for p in prefixes:
        filename = p[1:] + '/' + name
        mapping[filename] = key

def collect_depends(fp):
    filemap = {}

    for line in fp:
        line = line.strip()
        reqtype, _, name = line.partition(':')

        if reqtype == 'path':
            add_paths(filemap, line, path_paths, name)

        elif reqtype =='c_include':
            add_paths(filemap, line, c_include_paths, name)

        elif reqtype == 'pkgconfig':
            add_paths(filemap, line, pkgconfig_paths, name + '.pc')

        elif reqtype == 'python2':
            add_paths(filemap, line, python2_paths, name + '/__init__.py')
            add_paths(filemap, line, python2_paths, name + '.py')

        else:
            filemap[line] = line

    return filemap

def find_interesting_lines(fp, search_items):
    line = fp.next()
    while True:
        res = cmp(search_items[0], line)

        if res > 0:
            line = fp.next()

        else:
            # apt-file has a weird format -- it is whitespace-delimited
            # but the filenames can also contain spaces...
            # it is unlikely that we will find a filename that starts
            # with the name of a file that we are looking for followed
            # by a space...
            if line.startswith(search_items[0]) and line[len(search_items[0])].isspace():
                yield line.split()

            del search_items[0]
            if not search_items:
                return

def handle_distro(name, filemap, log = sys.stderr):
    contents = gzip.open(name + '-Contents-amd64.gz')
    keys = set(filemap.itervalues())
    result = {}

    while not contents.next().startswith('FILE'):
        pass

    for filename, pkgs in find_interesting_lines(contents, sorted(filemap)):
        key = filemap[filename]
        assert key not in result
        result[key] = [pkg.split('/')[-1] for pkg in pkgs.split(',')]

    for key in sorted(keys):
        if key not in result:
            if key in hints:
                if len(hints[key]):
                    result[key] = hints[key]
            else:
                log.write("# warning: {}: unable to locate dependency '{}'\n".format(name, key))

    return result

def print_sorted_dict(outfile, name, items):
    outfile.write('    {!r}: {{\n'.format(name))
    for key in sorted(items):
        outfile.write('        {!r}: {!r},\n'.format(key, items[key]))
    outfile.write("        '': []\n")
    outfile.write('    },\n\n')

def generate_debian_py(outfile, infile, log = sys.stderr):
    outfile.write('# this file was generated by scripts/update-debian-sysdeps.py\n\n')

    filemap = collect_depends(infile)
    package_lists = {}
    common = {}

    for name in sorted(releases):
        log.write("# scanning '{}'\n".format(name))
        package_lists[name] = handle_distro(name, filemap, log)

    for dep in set(filemap.itervalues()):
        pkgs = [dist.get(dep) for dist in package_lists.itervalues()]
        if all(pkg == pkgs[0] for pkg in pkgs):
            # maybe they all failed?
            if not pkgs[0]:
                continue

            common[dep] = pkgs[0]
            for dist in package_lists.itervalues():
                del dist[dep]

    outfile.write('\n')
    outfile.write('{\n')
    print_sorted_dict(outfile, 'common', common)
    for dist in sorted(package_lists):
        print_sorted_dict(outfile, dist, package_lists[dist])
    outfile.write("    '': {}\n}\n")

def download_files(urls, filename):
    for name, url in urls.iteritems():
        fullname = name + '-' + filename
        if not os.path.isfile(fullname):
            urlgrabber.urlgrab(url + '/' + filename, fullname + '.partial',
                               progress_obj=urlgrabber.progress.TextMeter(),
                               text='Contents-amd64.gz ({})'.format(name),
                               timeout=10)
            os.rename(fullname + '.partial', fullname)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.stderr.write("this script must be run with a single argument: the name of the output file\n")
        sys.exit(1)

    download_files(releases, 'Contents-amd64.gz')
    output = open(sys.argv[1], 'w')
    generate_debian_py(output, sys.stdin, log = output)
    output.close()
