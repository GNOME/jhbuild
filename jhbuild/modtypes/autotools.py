# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2007-2008  Frederic Peters
#
#   autotools.py: autotools module type definitions.
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

import os
import re
import stat

from jhbuild.errors import FatalError, BuildStateError, CommandError
from jhbuild.modtypes import \
     Package, get_dependencies, get_branch, register_module_type

__all__ = [ 'AutogenModule' ]

class AutogenModule(Package):
    '''Base type for modules that are distributed with a Gnome style
    "autogen.sh" script and the GNU build tools.  Subclasses are
    responsible for downloading/updating the working copy.'''
    type = 'autogen'

    STATE_CHECKOUT       = 'checkout'
    STATE_FORCE_CHECKOUT = 'force_checkout'
    STATE_CLEAN          = 'clean'
    STATE_FORCE_CLEAN    = 'force_clean'
    STATE_FORCE_DISTCLEAN= 'force_distclean'
    STATE_CONFIGURE      = 'configure'
    STATE_BUILD          = 'build'
    STATE_CHECK          = 'check'
    STATE_DIST           = 'dist'
    STATE_INSTALL        = 'install'

    def __init__(self, name, branch, autogenargs='', makeargs='',
                 makeinstallargs='',
                 dependencies=[], after=[], suggests=[],
                 supports_non_srcdir_builds=True,
                 skip_autogen=False,
                 autogen_sh='autogen.sh',
                 makefile='Makefile',
                 extra_env = None,
                 autogen_template=None,
                 check_target=True):
        Package.__init__(self, name, dependencies, after, suggests, extra_env)
        self.branch = branch
        self.autogenargs = autogenargs
        self.makeargs    = makeargs
        self.makeinstallargs = makeinstallargs
        self.supports_non_srcdir_builds = supports_non_srcdir_builds
        self.skip_autogen = skip_autogen
        self.autogen_sh = autogen_sh
        self.makefile = makefile
        self.autogen_template = autogen_template
        self.check_target = check_target

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            d = buildscript.config.builddir_pattern % (
                os.path.basename(self.get_srcdir(buildscript)))
            return os.path.join(buildscript.config.buildroot, d)
        else:
            return self.get_srcdir(buildscript)

    def get_revision(self):
        return self.branch.tree_id()

    def do_start(self, buildscript):
        pass
    do_start.next_state = STATE_CHECKOUT
    do_start.error_states = []

    def do_checkout(self, buildscript):
        self.checkout(buildscript)
    do_checkout.next_state = STATE_CONFIGURE
    do_checkout.error_states = [STATE_FORCE_CHECKOUT]

    def skip_force_checkout(self, buildscript, last_state):
        return False

    def do_force_checkout(self, buildscript):
        buildscript.set_action(_('Checking out'), self)
        self.branch.force_checkout(buildscript)
    do_force_checkout.next_state = STATE_CONFIGURE
    do_force_checkout.error_states = [STATE_FORCE_CHECKOUT]

    def skip_configure(self, buildscript, last_state):
        # skip if nobuild is set.
        if buildscript.config.nobuild:
            return True

        # skip if manually instructed to do so
        if self.skip_autogen:
            return True

        # don't skip this stage if we got here from one of the
        # following states:
        if last_state in [self.STATE_FORCE_CHECKOUT,
                          self.STATE_CLEAN,
                          self.STATE_BUILD,
                          self.STATE_INSTALL]:
            return False

        # skip if the makefile exists and we don't have the
        # alwaysautogen flag turned on:
        builddir = self.get_builddir(buildscript)
        return (os.path.exists(os.path.join(builddir, self.makefile)) and
                not buildscript.config.alwaysautogen)

    def do_configure(self, buildscript):
        builddir = self.get_builddir(buildscript)
        if buildscript.config.buildroot and not os.path.exists(builddir):
            os.makedirs(builddir)
        buildscript.set_action(_('Configuring'), self)

        srcdir = self.get_srcdir(buildscript)
        if self.autogen_sh == 'autogen.sh':
            # if there is no autogen.sh, automatically fallback to configure
            if not os.path.exists(os.path.join(srcdir, 'autogen.sh')) and \
                    os.path.exists(os.path.join(srcdir, 'configure')):
                self.autogen_sh = 'configure'

        try:
            if not (os.stat(os.path.join(srcdir, self.autogen_sh))[stat.ST_MODE] & 0111):
                os.chmod(os.path.join(srcdir, self.autogen_sh), 0755)
        except:
            pass

        if self.autogen_template:
            template = self.autogen_template
        else:
            template = ("%(srcdir)s/%(autogen-sh)s --prefix %(prefix)s"
                        " --libdir %(libdir)s %(autogenargs)s ")

        vars = {'prefix': buildscript.config.prefix,
                'autogen-sh': self.autogen_sh,
                'autogenargs': self.autogenargs}
                
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            vars['srcdir'] = self.get_srcdir(buildscript)
        else:
            vars['srcdir'] = '.'

        if buildscript.config.use_lib64:
            vars['libdir'] = "'${exec_prefix}/lib64'"
        else:
            vars['libdir'] = "'${exec_prefix}/lib'"

        cmd = template % vars

        if self.autogen_sh == 'autoreconf':
            buildscript.execute(['autoreconf', '-i'], cwd = builddir,
                    extra_env = self.extra_env)
            cmd = cmd.replace('autoreconf', 'configure')
            cmd = cmd.replace('--enable-maintainer-mode', '')

        # Fix up the arguments for special cases:
        #   tarballs: remove --enable-maintainer-mode to avoid breaking build
        #   tarballs: remove '-- ' to avoid breaking build (GStreamer weirdness)
        #   non-tarballs: place --prefix and --libdir after '-- ', if present
        if self.autogen_sh == 'configure':
            cmd = cmd.replace('--enable-maintainer-mode', '')
            
            # Also, don't pass '--', which gstreamer attempts to do, since
            # it is royally broken.
            cmd = cmd.replace('-- ', '')
        else:
            # place --prefix and --libdir arguments after '-- '
            # (GStreamer weirdness)
            if self.autogenargs.find('-- ') != -1:
                p = re.compile('(.*)(--prefix %s )((?:--libdir %s )?)(.*)-- ' %
                       (buildscript.config.prefix, "'\${exec_prefix}/lib64'"))
                cmd = p.sub(r'\1\4-- \2\3', cmd)

        buildscript.execute(cmd, cwd = builddir, extra_env = self.extra_env)
    do_configure.next_state = STATE_CLEAN
    do_configure.error_states = [STATE_FORCE_CHECKOUT,
            STATE_FORCE_CLEAN, STATE_FORCE_DISTCLEAN]

    def skip_clean(self, buildscript, last_state):
        return (not buildscript.config.makeclean or
                buildscript.config.nobuild)

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        cmd = '%s %s clean' % (os.environ.get('MAKE', 'make'), self.makeargs)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                extra_env = self.extra_env)
    do_clean.next_state = STATE_BUILD
    do_clean.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_build(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        cmd = '%s %s' % (os.environ.get('MAKE', 'make'), self.makeargs)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                extra_env = self.extra_env)
    do_build.next_state = STATE_CHECK
    do_build.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE,
            STATE_FORCE_CLEAN, STATE_FORCE_DISTCLEAN]

    def skip_check(self, buildscript, last_state):
        if not self.check_target:
            return True
        if not buildscript.config.module_makecheck.get(self.name, buildscript.config.makecheck):
            return True
        if buildscript.config.forcecheck:
            return False
        if buildscript.config.nobuild:
            return True
        return False

    def do_check(self, buildscript):
        buildscript.set_action(_('Checking'), self)
        cmd = '%s %s check' % (os.environ.get('MAKE', 'make'), self.makeargs)
        try:
            buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                    extra_env = self.extra_env)
        except CommandError:
            if not buildscript.config.makecheck_advisory:
                raise
    do_check.next_state = STATE_DIST
    do_check.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_dist(self, buildscript, last_state):
        return not (buildscript.config.makedist or buildscript.config.makedistcheck)

    def do_dist(self, buildscript):
        buildscript.set_action(_('Creating tarball for'), self)
        if buildscript.config.makedistcheck:
            cmd = '%s %s distcheck' % (os.environ.get('MAKE', 'make'), self.makeargs)
        else:
            cmd = '%s %s dist' % (os.environ.get('MAKE', 'make'), self.makeargs)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                    extra_env = self.extra_env)
    do_dist.next_state = STATE_INSTALL
    do_dist.error_states = [STATE_FORCE_CHECKOUT, STATE_CONFIGURE]

    def skip_install(self, buildscript, last_state):
        return buildscript.config.nobuild

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        if self.makeinstallargs:
            cmd = '%s %s' % (os.environ.get('MAKE', 'make'), self.makeinstallargs)
        else:
            cmd = '%s install' % os.environ.get('MAKE', 'make')

        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                    extra_env = self.extra_env)
        buildscript.packagedb.add(self.name, self.get_revision() or '')
    do_install.next_state = Package.STATE_DONE
    do_install.error_states = []

    def skip_force_clean(self, buildscript, last_state):
        return False

    def do_force_clean(self, buildscript):
        self.do_clean(buildscript)
    do_force_clean.next_state = STATE_CONFIGURE
    do_force_clean.error_states = []

    def skip_force_distclean(self, buildscript, last_state):
        return False

    def do_force_distclean(self, buildscript):
        buildscript.set_action(_('Distcleaning'), self)
        cmd = '%s %s distclean' % (os.environ.get('MAKE', 'make'), self.makeargs)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                    extra_env = self.extra_env)
    do_force_distclean.next_state = STATE_CONFIGURE
    do_force_distclean.error_states = []

    def xml_tag_and_attrs(self):
        return ('autotools',
                [('autogenargs', 'autogenargs', ''),
                 ('id', 'name', None),
                 ('makeargs', 'makeargs', ''),
                 ('makeinstallargs', 'makeinstallargs', ''),
                 ('supports-non-srcdir-builds',
                  'supports_non_srcdir_builds', True),
                 ('skip-autogen', 'skip_autogen', False),
                 ('autogen-sh', 'autogen_sh', 'autogen.sh'),
                 ('makefile', 'makefile', 'Makefile'),
                 ('autogen-template', 'autogen_template', None)])


def parse_autotools(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')
    autogenargs = ''
    makeargs = ''
    makeinstallargs = ''
    supports_non_srcdir_builds = True
    autogen_sh = 'autogen.sh'
    skip_autogen = False
    check_target = True
    makefile = 'Makefile'
    autogen_template = None
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
    if node.hasAttribute('makeinstallargs'):
        makeinstallargs = node.getAttribute('makeinstallargs')
    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')
    if node.hasAttribute('skip-autogen'):
        skip_autogen = (node.getAttribute('skip-autogen') == 'true')
    if node.hasAttribute('check-target'):
        check_target = (node.getAttribute('check-target') == 'true')
    if node.hasAttribute('autogen-sh'):
        autogen_sh = node.getAttribute('autogen-sh')
    if node.hasAttribute('makefile'):
        makefile = node.getAttribute('makefile')
    if node.hasAttribute('autogen-template'):
        autogen_template = node.getAttribute('autogen-template')

    # Make some substitutions; do special handling of '${prefix}' and '${libdir}'
    p = re.compile('(\${prefix})')
    autogenargs     = p.sub(config.prefix, autogenargs)
    makeargs        = p.sub(config.prefix, makeargs)
    makeinstallargs = p.sub(config.prefix, makeinstallargs)
    # I'm not sure the replacement of ${libdir} is necessary for firefox...
    p = re.compile('(\${libdir})')
    libsubdir = '/lib'
    if config.use_lib64:
        libsubdir = '/lib64'
    autogenargs     = p.sub(config.prefix + libsubdir, autogenargs)
    makeargs        = p.sub(config.prefix + libsubdir, makeargs)
    makeinstallargs = p.sub(config.prefix + libsubdir, makeinstallargs)

    autogenargs += ' ' + config.module_autogenargs.get(id, config.autogenargs)
    makeargs += ' ' + config.module_makeargs.get(id, config.makeargs)
    extra_env = config.module_extra_env.get(id)

    dependencies, after, suggests = get_dependencies(node)
    branch = get_branch(node, repositories, default_repo, config)
    if config.module_checkout_mode.get(id):
        branch.checkout_mode = config.module_checkout_mode[id]

    return AutogenModule(id, branch, autogenargs, makeargs,
                         makeinstallargs=makeinstallargs,
                         dependencies=dependencies,
                         after=after,
                         suggests=suggests,
                         supports_non_srcdir_builds=supports_non_srcdir_builds,
                         skip_autogen=skip_autogen,
                         autogen_sh=autogen_sh,
                         makefile=makefile,
                         extra_env=extra_env,
                         autogen_template=autogen_template,
                         check_target=check_target)
register_module_type('autotools', parse_autotools)


# deprecated module types below:
def parse_cvsmodule(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')
    module = None
    revision = None
    checkoutdir = None
    autogenargs = ''
    makeargs = ''
    supports_non_srcdir_builds = True
    if node.hasAttribute('module'):
        module = node.getAttribute('module')
    if node.hasAttribute('revision'):
        revision = node.getAttribute('revision')
    if node.hasAttribute('checkoutdir'):
        checkoutdir = node.getAttribute('checkoutdir')
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')

    if not id:
        id = checkoutdir or module

    autogenargs += ' ' + config.module_autogenargs.get(id, config.autogenargs)
    makeargs += ' ' + config.module_makeargs.get(id, config.makeargs)
    extra_env = config.module_extra_env.get(id)

    dependencies, after, suggests = get_dependencies(node)

    for attrname in ['cvsroot', 'root']:
        if node.hasAttribute(attrname):
            try:
                repo = repositories[node.getAttribute(attrname)]
                break
            except KeyError:
                raise FatalError(_('Repository=%s not found for module id=%s. '
                                   'Possible repositories are %s')
                                 % (node.getAttribute(attrname),
                                    node.getAttribute('id'), repositories))
    else:
        repo = repositories.get(default_repo, None)
    branch = repo.branch(id, module=module, checkoutdir=checkoutdir,
                         revision=revision)

    return AutogenModule(id, branch, autogenargs, makeargs,
                         dependencies=dependencies,
                         after=after, suggests=suggests,
                         supports_non_srcdir_builds=supports_non_srcdir_builds,
                         extra_env=extra_env)
register_module_type('cvsmodule', parse_cvsmodule)

def parse_svnmodule(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')
    module = None
    checkoutdir = None
    autogenargs = ''
    makeargs = ''
    supports_non_srcdir_builds = True
    if node.hasAttribute('module'):
        module = node.getAttribute('module')
    if node.hasAttribute('checkoutdir'):
        checkoutdir = node.getAttribute('checkoutdir')
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')

    if not id:
        id = checkoutdir or os.path.basename(module)

    autogenargs += ' ' + config.module_autogenargs.get(id, config.autogenargs)
    makeargs += ' ' + config.module_makeargs.get(id, config.makeargs)
    extra_env = config.module_extra_env.get(id)

    dependencies, after, suggests = get_dependencies(node)

    if node.hasAttribute('root'):
        repo = repositories[node.getAttribute('root')]
    else:
        repo = repositories.get(default_repo, None)
    branch = repo.branch(id, module=module, checkoutdir=checkoutdir)

    return AutogenModule(id, branch, autogenargs, makeargs,
                         dependencies=dependencies,
                         after=after, suggests=suggests,
                         supports_non_srcdir_builds=supports_non_srcdir_builds,
                         extra_env=extra_env)
register_module_type('svnmodule', parse_svnmodule)

def parse_archmodule(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')
    version = None
    checkoutdir = None
    autogenargs = ''
    makeargs = ''
    supports_non_srcdir_builds = True
    if node.hasAttribute('version'):
        version = node.getAttribute('version')
    if node.hasAttribute('checkoutdir'):
        checkoutdir = node.getAttribute('checkoutdir')
    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = \
            (node.getAttribute('supports-non-srcdir-builds') != 'no')

    if not id:
        id = checkoutdir or version

    autogenargs += ' ' + config.module_autogenargs.get(id, config.autogenargs)
    makeargs += ' ' + config.module_makeargs.get(id, makeargs)
    extra_env = config.module_extra_env.get(id)

    dependencies, after, suggests = get_dependencies(node)

    if node.hasAttribute('root'):
        repo = repositories[node.getAttribute('root')]
    else:
        repo = repositories.get(default_repo, None)
    branch = repo.branch(id, module=version, checkoutdir=checkoutdir)

    return AutogenModule(id, branch, autogenargs, makeargs,
                         dependencies=dependencies,
                         after=after, suggests=suggests,
                         supports_non_srcdir_builds=supports_non_srcdir_builds,
                         extra_env=extra_env)
register_module_type('archmodule', parse_archmodule)
