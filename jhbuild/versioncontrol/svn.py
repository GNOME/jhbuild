# jhbuild - a tool to ease building collections of source packages
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
import subprocess
import urllib.parse

from jhbuild.errors import CommandError, BuildStateError
from jhbuild.utils.cmds import get_output, check_version
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.utils import inpath, _, udecode
from jhbuild.utils.sxml import sxml

svn_one_five = None # is this svn 1.5

def _make_uri(repo, path):
    if repo[-1] != '/':
        return '%s/%s' % (repo, path)
    else:
        return repo + path

# Make sure that the urlparse module considers svn:// and svn+ssh://
# schemes to be netloc aware and set to allow relative URIs.
if 'svn' not in urllib.parse.uses_netloc:
    urllib.parse.uses_netloc.append('svn')
if 'svn' not in urllib.parse.uses_relative:
    urllib.parse.uses_relative.append('svn')
if 'svn+ssh' not in urllib.parse.uses_netloc:
    urllib.parse.uses_netloc.append('svn+ssh')
if 'svn+ssh' not in urllib.parse.uses_relative:
    urllib.parse.uses_relative.append('svn+ssh')

def get_svn_extra_env():
    # we run Subversion in the C locale, because Subversion localises
    # the key names in the output.  See bug #334678 for more info.
    #
    # Also we run it without the JHBuild LD_LIBRARY_PATH, as it can lead to
    # errors if it picks up jhbuilded gnutls library.  See bug #561191.
    return { 'LANGUAGE': 'C', 'LC_ALL': 'C', 'LANG': 'C',
             'LD_LIBRARY_PATH': os.environ.get('UNMANGLED_LD_LIBRARY_PATH') }

def get_info(filename):
    output = get_output(
        ['svn', 'info', filename], extra_env=get_svn_extra_env())
    ret = {}
    for line in output.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        ret[key.lower().strip()] = value.strip()
    return ret

def get_subdirs(url):
    print(_("Getting SVN subdirs: this operation might be long..."))
    output = get_output(
        ['svn', 'ls', '-R', url], extra_env=get_svn_extra_env())
    ret = []
    for line in output.splitlines():
        if not line[-1] == '/':
            continue
        ret.append (line)
    return ret

def get_externals(url):
    output = get_output(['svn', 'propget', 'svn:externals', url],
            extra_env=get_svn_extra_env())
    ret = {}
    for line in output.splitlines():
        if ' ' not in line:
            continue
        key, value = line.split(' ')
        ret[key.strip()] = value
    return ret

def get_uri(filename):
    try:
        info = get_info(filename)
    except CommandError:
        raise BuildStateError(_('could not get Subversion URI for %s')
                              % filename)
    if 'url' not in info:
        raise BuildStateError(_('could not parse "svn info" output for %s')
                              % filename)
    return info['url']

def call_with_info(proc, filename, *keys):
    info = get_info(filename)
    try:
        return proc(*[info[k] for k in keys])
    except KeyError:
        return None

class SubversionRepository(Repository):
    """A class used to work with a Subversion repository"""

    init_xml_attrs = ['href', 'trunk-template', 'branches-template', 'tags-template']

    def __init__(self, config, name, href, trunk_template=None, branches_template=None, tags_template=None):
        Repository.__init__(self, config, name)
        # allow user to adjust location of branch.
        self.href = config.repos.get(name, href)
        self.trunk_template = trunk_template or "%(module)s/trunk"
        self.branches_template = branches_template or "%(module)s/branches/%(branch)s"
        self.tags_template = tags_template or "%(module)s/tags/%(tag)s"
        self.svn_program = config.svn_program

    branch_xml_attrs = ['module', 'checkoutdir', 'revision', 'tag']

    def branch(self, name, module=None, checkoutdir=None, revision=None, tag=None):
        from . import bzr, git

        module_href = None
        if name in self.config.branches:
            if self.config.branches[name]:
                module_href = self.config.branches[name]
            else:
                module = None
                revision = None

        if not module:
            module = name

        if revision and not revision.isdigit():
            template = self.branches_template
        elif tag:
            template = self.tags_template
        else:
            template = self.trunk_template

        # Workarounds for people with hacked modulesets
        if "/" in module or "trunk" == module:
            template = "%(module)s"

        if module_href is None:
            template = self.href + template
            module_href = template % {
                'module': module,
                'branch': revision,
                'tag': tag,
            }

        if checkoutdir is None:
            checkoutdir = name

        # workaround for svn client not handling '..' in URL (#560246, #678869)
        if os.name != 'nt':
            splitted_href = list(urllib.parse.urlsplit(module_href))
            splitted_href[2] = os.path.abspath(splitted_href[2])
            module_href = urllib.parse.urlunsplit(splitted_href)

        if self.svn_program == 'bzr' and not revision:
            return bzr.BzrBranch(self, module_href, checkoutdir)
        elif self.svn_program == 'git-svn':
            return git.GitSvnBranch(self, module_href, checkoutdir, revision)
        else:
            return SubversionBranch(self, module_href, name, checkoutdir, revision)

    def to_sxml(self):
        return [sxml.repository(type='svn', name=self.name, href=self.href)]

    def get_sysdeps(self):
        return ['svn']


class SubversionBranch(Branch):
    """A class representing a Subversion branch"""

    def __init__(self, repository, module, module_name, checkoutdir, revision):
        Branch.__init__(self, repository, module, checkoutdir)
        self.module_name = module_name
        self.revision = revision

    @property
    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.checkoutroot,
                                os.path.basename(self.module))

    @property
    def branchname(self):
        return self.revision

    def exists(self):
        try:
            get_output(['svn', 'ls', self.module], extra_env={
                'LD_LIBRARY_PATH': os.environ.get('UNMANGLED_LD_LIBRARY_PATH'),
                })
            return True
        except CommandError:
            return False

    def _export(self, buildscript):
        cmd = ['svn', 'export', self.module]

        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if self.revision and self.revision.isdigit():
            cmd.extend(['-r', '%s' % self.revision])
        elif self.config.sticky_date:
            cmd.extend(['-r', '{%s}' % self.config.sticky_date])

        buildscript.execute(cmd, 'svn', cwd=self.checkoutroot,
                extra_env = get_svn_extra_env())
    
    def _checkout(self, buildscript, copydir=None):
        cmd = ['svn', 'checkout', self.module]

        if self.checkoutdir:
            cmd.append(self.checkoutdir)

        if not self.config.interact:
            cmd.append('--non-interactive')

        if self.revision and self.revision.isdigit():
            cmd.extend(['-r', '%s' % self.revision])
        elif self.config.sticky_date:
            cmd.extend(['-r', '{%s}' % self.config.sticky_date])

        if copydir:
            buildscript.execute(cmd, 'svn', cwd=copydir,
                    extra_env=get_svn_extra_env())
        else:
            buildscript.execute(cmd, 'svn', cwd=self.config.checkoutroot,
                    extra_env=get_svn_extra_env())

    def _update(self, buildscript, copydir=None):
        opt = []
        if copydir:
            outputdir = os.path.join(copydir, os.path.basename(self.srcdir))
        else:
            outputdir = self.srcdir

        opt = []

        if not self.config.interact:
            opt.append('--non-interactive')

        if self.revision and self.revision.isdigit():
            opt.extend(['-r', '%s' % self.revision])
        elif self.config.sticky_date:
            opt.extend(['-r', '{%s}' % self.config.sticky_date])

        # Subversion 1.5 has interactive behaviour on conflicts; check version
        # and add appropriate flags to get back 1.4 behaviour.
        global svn_one_five
        if svn_one_five is None:
            svn_one_five = check_version(['svn', '--version'], r'svn, version ([\d.]+)', '1.5',
                    extra_env=get_svn_extra_env())

        if svn_one_five is True:
            opt.extend(['--accept', 'postpone'])

        uri = get_uri(outputdir)

        if urllib.parse.urlparse(uri)[:2] != urllib.parse.urlparse(self.module)[:2]:
            # server and protocol changed, probably because user changed
            # svnroots[] config variable.
            new_uri = urllib.parse.urlunparse(
                    urllib.parse.urlparse(self.module)[:2] + urllib.parse.urlparse(uri)[2:])
            cmd = ['svn', 'switch', '--relocate', uri, new_uri, '.']
            buildscript.execute(cmd, 'svn', cwd=outputdir,
                    extra_env=get_svn_extra_env())

        # if the URI doesn't match, use "svn switch" instead of "svn update"
        if get_uri(outputdir) != self.module:
            cmd = ['svn', 'switch'] + opt + [self.module]
        else:
            cmd = ['svn', 'update'] + opt + ['.']

        buildscript.execute(cmd, 'svn', cwd=outputdir,
                extra_env=get_svn_extra_env())

        try:
            self._check_for_conflicts()
        except CommandError:
            # execute svn status so conflicts are displayed
            buildscript.execute(['svn', 'status'], 'svn', cwd=self.srcdir,
                    extra_env=get_svn_extra_env())
            raise

    def _check_for_conflicts(self):
        kws = {}
        kws['cwd'] = self.srcdir
        kws['env'] = os.environ.copy()
        extra_env = get_svn_extra_env()
        kws['env'].update(extra_env)
        try:
            output = subprocess.Popen(['svn', 'info', '-R'],
                    stdout = subprocess.PIPE, **kws).communicate()[0]
        except OSError as e:
            raise CommandError(str(e))
        output = udecode(output)
        if '\nConflict' in output:
            raise CommandError(_('Error checking for conflicts'))

    def checkout(self, buildscript):
        if not inpath('svn', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'svn')
        Branch.checkout(self, buildscript)

    def tree_id(self):
        if not os.path.exists(self.srcdir):
            return None
        try:
            if self.config.checkout_mode == 'export':
                info = get_info(self.module)
            else:
                info = get_info(self.srcdir)
        except CommandError:
            return None
        try:
            url = info['url']
            root = info['repository root']
            uuid = info['repository uuid']
            rev = info['last changed rev']
        except KeyError:
            return None

        # get the path within the repository
        assert url.startswith(root)
        path = url[len(root):]
        while path.startswith('/'):
            path = path[1:]

        return '%s,%s,%s' % (uuid.lower(), rev, path)

    def to_sxml(self):
        return (call_with_info(lambda rev:
                    [sxml.branch(repo=self.repository.name,
                                 module=self.module,
                                 revision=rev)],
                               self.srcdir, 'last changed rev')
                or [sxml.branch(repo=self.repository.name,
                                module=self.module)])


register_repo_type('svn', SubversionRepository)
