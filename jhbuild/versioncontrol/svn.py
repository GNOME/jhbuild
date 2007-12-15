# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   svn.py: some code to handle various Subversion operations
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

__all__ = []
__metaclass__ = type

import os
import urlparse
import subprocess

from jhbuild.errors import CommandError, BuildStateError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type

import bzr, git

def _make_uri(repo, path):
    if repo[-1] != '/':
        return '%s/%s' % (repo, path)
    else:
        return repo + path

# Make sure that the urlparse module considers svn:// and svn+ssh://
# schemes to be netloc aware and set to allow relative URIs.
if 'svn' not in urlparse.uses_netloc:
    urlparse.uses_netloc.append('svn')
if 'svn' not in urlparse.uses_relative:
    urlparse.uses_relative.append('svn')
if 'svn+ssh' not in urlparse.uses_netloc:
    urlparse.uses_netloc.append('svn+ssh')
if 'svn+ssh' not in urlparse.uses_relative:
    urlparse.uses_relative.append('svn+ssh')

def get_info(filename):
    # we run Subversion in the C locale, because Subversion localises
    # the key names in the output.  See bug #334678 for more info.
    output = get_output(
        ['svn', 'info', filename],
        extra_env={
            'LANGUAGE': 'C',
            'LC_ALL': 'C',
            'LANG': 'C'})
    ret = {}
    for line in output.splitlines():
        if ':' not in line: continue
        key, value = line.split(':', 1)
        ret[key.lower().strip()] = value.strip()
    return ret

def get_subdirs(url):
    print "Getting SVN subdirs: this operation might be long..."
    output = get_output(
        ['svn', 'ls', '-R', url],
        extra_env={
            'LANGUAGE': 'C',
            'LC_ALL': 'C',
            'LANG': 'C'})
    ret = []
    for line in output.splitlines():
        if not line[-1] == '/': continue
        ret.append (line)
    return ret

def get_externals(url):
    output = get_output(
        ['svn', 'propget', 'svn:externals', url],
        extra_env={
            'LANGUAGE': 'C',
            'LC_ALL': 'C',
            'LANG': 'C'})
    ret = {}
    for line in output.splitlines():
        if ' ' not in line: continue
        key, value = line.split(' ')
        ret[key.strip()] = value
    return ret

def get_uri(filename):
    try:
        info = get_info(filename)
    except CommandError:
        raise BuildStateError('could not get Subversion URI for %s'
                              % filename)
    if 'url' not in info:
        raise BuildStateError('could not parse "svn info" output for %s'
                              % filename)
    return info['url']

class SubversionRepository(Repository):
    """A class used to work with a Subversion repository"""

    init_xml_attrs = ['href', 'trunk-path', 'branches-path']

    def __init__(self, config, name, href, trunk_path='trunk', branches_path='branches'):
        Repository.__init__(self, config, name)
        # allow user to adjust location of branch.
        self.href = config.repos.get(name, href)
        self.trunk_path = trunk_path
        self.branches_path = branches_path
        self.svn_program = config.svn_program

    branch_xml_attrs = ['module', 'checkoutdir', 'revision']

    def branch(self, name, module=None, checkoutdir=None, revision=None):
        module_href = None
        if name in self.config.branches:
            if self.config.branches[name]:
                module_href = self.config.branches[name]
            else:
                module = None
                revision = None

        if module is None or revision is not None:
            if module is None:
                module = name
            if not revision:
                if self.trunk_path:
                    module += '/' + self.trunk_path
                    if checkoutdir is None:
                        checkoutdir = name
            else:
                if self.branches_path:
                    module += '/' + self.branches_path + '/' + revision
                else:
                    module += '/' + revision
            
        if module_href is None:
            module_href = urlparse.urljoin(self.href, module)
        
        if checkoutdir is None:
            checkoutdir = name
        
        if self.svn_program == 'bzr' and not revision:
            return bzr.BzrBranch(self, module_href, checkoutdir)
        elif self.svn_program == 'git-svn':
            return git.GitSvnBranch(self, module_href, checkoutdir, revision)
        else:
            return SubversionBranch(self, module_href, name, checkoutdir, revision)


class SubversionBranch(Branch):
    """A class representing a Subversion branch"""

    def __init__(self, repository, module, module_name, checkoutdir, revision):
        Branch.__init__(self, repository, module, checkoutdir)
        self.module_name = module_name
        self.revision = revision

    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.checkoutroot,
                                os.path.basename(self.module))
    srcdir = property(srcdir)

    def branchname(self):
        return self.revision
    branchname = property(branchname)

    def _export(self, buildscript):
        cmd = ['svn', 'export', self.module]

        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.config.sticky_date:
            cmd.extend(['-r', '{%s}' % self.config.sticky_date])

        buildscript.execute(cmd, 'svn', cwd=self.checkoutroot)
    
    def _checkout(self, buildscript, copydir=None):
        cmd = ['svn', 'checkout', self.module]

        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.config.sticky_date:
            cmd.extend(['-r', '{%s}' % self.config.sticky_date])

        if copydir:
            buildscript.execute(cmd, 'svn', cwd=copydir)
        else:
            buildscript.execute(cmd, 'svn', cwd=self.config.checkoutroot)

    def _update(self, buildscript, copydir=None):
        opt = []
        if not copydir:
            outputdir = os.path.join(copydir, os.path.basename(self.srcdir))
        else:
            outputdir = self.srcdir

        opt = []
        if self.config.sticky_date:
            opt.extend(['-r', '{%s}' % self.config.sticky_date])

        # if the URI doesn't match, use "svn switch" instead of "svn update"
        if get_uri(outputdir) != self.module:
            cmd = ['svn', 'switch'] + opt + [self.module]
        else:
            cmd = ['svn', 'update'] + opt + ['.']

        buildscript.execute(cmd, 'svn', cwd=outputdir)

        try:
            self._check_for_conflicts()
        except CommandError:
            # execute svn status so conflicts are displayed
            buildscript.execute(['svn', 'status'], 'svn', cwd=self.srcdir)
            raise

    def _check_for_conflicts(self):
        kws = {}
        kws['cwd'] = self.srcdir
        kws['env'] = os.environ.copy()
        extra_env={
            'LANGUAGE': 'C',
            'LC_ALL': 'C',
            'LANG': 'C'}
        kws['env'].update(extra_env)
        try:
            output = subprocess.Popen(['svn', 'info', '-R'],
                    stdout = subprocess.PIPE, **kws).communicate()[0]
        except OSError, e:
            raise CommandError(str(e))
        if 'Conflict' in output:
            raise CommandError('Error checking for conflicts')

    def checkout(self, buildscript):
        if self.checkout_mode in ('clobber', 'export'):
            self._wipedir(buildscript)
            if self.checkout_mode == 'clobber':
                self._checkout(buildscript)
            else:
                self._export(buildscript)
        elif self.checkout_mode in ('update', 'copy'):
            copydir = None
            if self.checkout_mode == 'copy' and self.config.copy_dir:
                copydir = self.config.copy_dir
            else:
                copydir = self.config.checkoutroot

            if os.path.exists(os.path.join(copydir,
                              os.path.basename(self.srcdir), '.svn')):
                self._update(buildscript, copydir)
            else:
                self._wipedir(buildscript)
                self._checkout(buildscript, copydir)
            if self.checkout_mode == 'copy' and self.config.copy_dir:
                self._copy(buildscript, copydir)

    def force_checkout(self, buildscript):
        self._checkout(buildscript)

    def tree_id(self):
        if not os.path.exists(self.srcdir):
            return None
        info = get_info(self.srcdir)
        url = info['url']
        root = info['repository root']
        uuid = info['repository uuid']
        rev = info['last changed rev']

        # get the path within the repository
        assert url.startswith(root)
        path = url[len(root):]
        while path.startswith('/'):
            path = path[1:]

        return '%s,%s,%s' % (uuid.lower(), rev, path)


register_repo_type('svn', SubversionRepository)
