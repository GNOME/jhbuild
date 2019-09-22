# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   tarball.py: rules for building tarballs
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

__metaclass__ = type

import logging

from jhbuild.utils import _
from jhbuild.modtypes import register_module_type, get_dependencies, find_first_child_node_content

def parse_tarball(node, config, uri, repositories, default_repo):
    name = node.getAttribute('id')
    version = node.getAttribute('version')
    source_url = None
    source_size = None
    source_hash = None
    patches = []
    checkoutdir = None
    autogenargs = ''
    makeargs = ''
    makeinstallargs = ''
    supports_non_srcdir_builds = True
    makefile = 'Makefile'
    if node.hasAttribute('checkoutdir'):
        checkoutdir = node.getAttribute('checkoutdir')
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
    if node.hasAttribute('makeinstallargs'):
        makeinstallargs = node.getAttribute('makeinstallargs')
    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')
    if node.hasAttribute('makefile'):
        makefile = node.getAttribute('makefile')

    for childnode in node.childNodes:
        if childnode.nodeType != childnode.ELEMENT_NODE:
            continue
        if childnode.nodeName == 'source':
            source_url = childnode.getAttribute('href')
            if childnode.hasAttribute('size'):
                try:
                    source_size = int(childnode.getAttribute('size'))
                except ValueError:
                    logging.warning(
                            _('module \'%(module)s\' has invalid size attribute (\'%(size)s\')') % {
                                'module': name, 'size': childnode.getAttribute('size')})
            if childnode.hasAttribute('md5sum'):
                source_hash = 'md5:' + childnode.getAttribute('md5sum')
            if childnode.hasAttribute('hash'):
                source_hash = childnode.getAttribute('hash')
        elif childnode.nodeName == 'patches':
            for patch in childnode.childNodes:
                if patch.nodeType != patch.ELEMENT_NODE:
                    continue
                if patch.nodeName != 'patch':
                    continue
                patchfile = patch.getAttribute('file')
                if patch.hasAttribute('strip'):
                    patchstrip = int(patch.getAttribute('strip'))
                else:
                    patchstrip = 0
                patches.append((patchfile, patchstrip))

    # for tarballs, don't ever pass --enable-maintainer-mode
    autogenargs = autogenargs.replace('--enable-maintainer-mode', '')

    dependencies, after, suggests, systemdependencies = get_dependencies(node)

    from .autotools import AutogenModule
    from jhbuild.versioncontrol.tarball import TarballBranch, TarballRepository

    # create a fake TarballRepository, and give it the moduleset uri
    repo = TarballRepository(config, None, None)
    repo.moduleset_uri = uri

    branch = TarballBranch(repo, source_url, version, checkoutdir,
            source_size, source_hash, None)
    branch.patches = patches

    instance = AutogenModule(name, branch,
                             autogenargs, makeargs, makeinstallargs,
                             supports_non_srcdir_builds = supports_non_srcdir_builds,
                             skip_autogen = False, autogen_sh = 'configure',
                             makefile = makefile)
    instance.dependencies = dependencies
    instance.after = after
    instance.suggests = suggests
    instance.systemdependencies = systemdependencies
    instance.pkg_config = find_first_child_node_content(node, 'pkg-config')
    instance.config = config

    return instance

register_module_type('tarball', parse_tarball)
