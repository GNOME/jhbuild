import os
import rfc822
import re
import apt_pkg
import gzip


REPREPRO_DIR = os.path.expanduser('~/.jhdebuild/reprepro')

ARCH = os.popen('dpkg-architecture -qDEB_HOST_ARCH').read().strip()

def install_changes(buildscript, filename):
    moduleset = buildscript.config.moduleset
    if type(moduleset) is list:
        moduleset = moduleset[0]
    if not os.path.exists(REPREPRO_DIR):
        os.makedirs(REPREPRO_DIR)
        os.mkdir(os.path.join(REPREPRO_DIR, 'conf'))
        open(os.path.join(REPREPRO_DIR, 'conf', 'distributions'), 'w').write("""\
Origin: jhdebuild
Label: JhDebuild Packages Repository
Codename: %s
Architectures: i386 source
Components: main
UDebComponents: main
Description: JhDebuild Packages
""" % moduleset)

    buildscript.execute(['reprepro', '--ignore=wrongdistribution', '--section=main',
            '-b', REPREPRO_DIR, 'include', moduleset, filename])


def check_build_depends(debian_control):
    '''check build dependencies'''
    current = None
    versions = {}
    providers = {}
    installed = False
    for line in open('/var/lib/dpkg/status'):
        if line.startswith('Package: '):
            installed = False
            name = line.split(':')[1].strip()
        elif line.startswith('Status: '):
            if line.strip().endswith(' ok installed'):
                installed = True
        elif line.startswith('Version: ') and installed:
            versions[name] = line.split(':', 1)[1].strip()
            providers[name] = [name]
        elif line.startswith('Provides: ') and installed:
            for p in line.split(':')[1].strip().split(', '):
                providers[p] = providers.get(p, [])
                providers[p].append(name)

    m = rfc822.Message(file(debian_control))
    build_deps = m.getheader('Build-Depends') or ''
    build_deps_indep = m.getheader('Build-Depends-Indep') or ''

    failures = []
    for depend in build_deps.split(',') + build_deps_indep.split(','):
        depend = depend.strip()

        ok = False
        names = []
        for dep in depend.split('|'):
            dep = dep.strip()

            if not dep:
                continue
            
            try:
                name, relation, version = re.findall('([A-Za-z0-9+.-]+) \(([<>=]+) (.+)\)', dep)[0]
            except IndexError:
                name = re.findall('([A-Za-z0-9+.-]+)', dep)[0]
                relation, version = None, None
            if '[' in dep:
                archs = dep[dep.index('[')+1:dep.rindex(']')].split(' ')
                if ARCH not in archs:
                    continue

            names.append(name)
            if relation and version:
                if not versions.has_key(name):
                    continue
                else:
                    r = apt_pkg.VersionCompare(versions[name], version)
                    if not ((relation == '<=' and r <= 0) or (relation == '<<' and r < 0) or (
                             relation == '>>' and r > 0) or (relation == '>=' and r >= 0) or (
                             relation == '>' and r > 0) or (relation == '<' and r < 0) or (
                             relation == '=' and r == 0)):
                        continue
                break
            else:
                if not providers.has_key(name):
                    continue
                break
        else:
            if names:
                failures.append(names)

    return failures

def get_version(buildscript, package):
    moduleset = buildscript.config.moduleset
    if type(moduleset) is list:
        moduleset = moduleset[0]
    sources_filename = os.path.join(REPREPRO_DIR, 'dists', moduleset, 'main/source/Sources.gz')
    if not os.path.exists(sources_filename):
        return None

    for line in gzip.open(sources_filename):
        if line.startswith('Package: '):
            name = line.split(':')[1].strip()
        elif line.startswith('Version:' ):
            version = line.split(':', 1)[1].strip()
            if name == package:
                return version
    return None

