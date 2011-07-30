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
     Package, DownloadableModule, register_module_type

__all__ = [ 'AutogenModule' ]

class AutogenModule(Package, DownloadableModule):
    '''Base type for modules that are distributed with a Gnome style
    "autogen.sh" script and the GNU build tools.  Subclasses are
    responsible for downloading/updating the working copy.'''
    type = 'autogen'

    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_CLEAN          = 'clean'
    PHASE_DISTCLEAN      = 'distclean'
    PHASE_CONFIGURE      = 'configure'
    PHASE_BUILD          = 'build'
    PHASE_CHECK          = 'check'
    PHASE_DIST           = 'dist'
    PHASE_INSTALL        = 'install'

    def __init__(self, name, branch=None,
                 autogenargs='', makeargs='',
                 makeinstallargs='',
                 supports_non_srcdir_builds=True,
                 skip_autogen=False,
                 autogen_sh='autogen.sh',
                 makefile='Makefile',
                 autogen_template=None,
                 check_target=True,
                 supports_static_analyzer=True):
        Package.__init__(self, name, branch=branch)
        self.autogenargs = autogenargs
        self.makeargs    = makeargs
        self.makeinstallargs = makeinstallargs
        self.supports_non_srcdir_builds = supports_non_srcdir_builds
        self.skip_autogen = skip_autogen
        self.autogen_sh = autogen_sh
        self.makefile = makefile
        self.autogen_template = autogen_template
        self.check_target = check_target
        self.supports_install_destdir = True
        self.supports_static_analyzer = supports_static_analyzer

    def _get_makeargs(self, buildscript):
        makeargs = self.makeargs + ' ' + self.config.module_makeargs.get(
            self.name, self.config.makeargs)
        if self.supports_parallel_build:
            # Propagate job count into makeargs, unless -j is already set
            if ' -j' not in makeargs:
                arg = '-j %s' % (buildscript.config.jobs, )
                makeargs = makeargs + ' ' + arg
        return makeargs.strip()

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            d = buildscript.config.builddir_pattern % (
                self.branch.checkoutdir or self.branch.get_module_basename())
            return os.path.join(buildscript.config.buildroot, d)
        else:
            return self.get_srcdir(buildscript)

    def skip_configure(self, buildscript, last_phase):
        # skip if manually instructed to do so
        if self.skip_autogen is True:
            return True

        # don't skip this stage if we got here from one of the
        # following phases:
        if last_phase in [self.PHASE_FORCE_CHECKOUT,
                          self.PHASE_CLEAN,
                          self.PHASE_BUILD,
                          self.PHASE_INSTALL]:
            return False

        if self.skip_autogen == 'never':
            return False

        if buildscript.config._internal_noautogen:
            return True

        return False

    def do_configure(self, buildscript):
        builddir = self.get_builddir(buildscript)
        if buildscript.config.buildroot and not os.path.exists(builddir):
            os.makedirs(builddir)
        buildscript.set_action(_('Configuring'), self)

        srcdir = self.get_srcdir(buildscript)
        if not os.path.exists(os.path.join(srcdir, self.autogen_sh)):
            # if there is no autogen.sh, automatically fallback to configure
            if os.path.exists(os.path.join(srcdir, 'configure')):
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

        autogenargs = self.autogenargs + ' ' + self.config.module_autogenargs.get(
                self.name, self.config.autogenargs)

        vars = {'prefix': buildscript.config.prefix,
                'autogen-sh': self.autogen_sh,
                'autogenargs': autogenargs}
                
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            vars['srcdir'] = self.get_srcdir(buildscript)
        else:
            vars['srcdir'] = '.'

        if buildscript.config.use_lib64:
            vars['libdir'] = "'${exec_prefix}/lib64'"
        else:
            vars['libdir'] = "'${exec_prefix}/lib'"

        cmd = self.static_analyzer_pre_cmd(buildscript) + template % vars

        if self.autogen_sh == 'autoreconf':
            # autoreconf doesn't honour ACLOCAL_FLAGS, therefore we pass
            # a crafted ACLOCAL variable.  (GNOME bug 590064)
            extra_env = {}
            if self.extra_env:
                extra_env = self.extra_env.copy()
            extra_env['ACLOCAL'] = ' '.join((
                extra_env.get('ACLOCAL', os.environ.get('ACLOCAL', 'aclocal')),
                extra_env.get('ACLOCAL_FLAGS', os.environ.get('ACLOCAL_FLAGS', ''))))
            buildscript.execute(['autoreconf', '-i'], cwd=srcdir,
                    extra_env=extra_env)
            os.chmod(os.path.join(srcdir, 'configure'), 0755)
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
            if autogenargs.find('-- ') != -1:
                p = re.compile('(.*)(--prefix %s )((?:--libdir %s )?)(.*)-- ' %
                       (buildscript.config.prefix, "'\${exec_prefix}/lib64'"))
                cmd = p.sub(r'\1\4-- \2\3', cmd)

        # If there is no --exec-prefix in the constructed autogen command, we
        # can safely assume it will be the same as {prefix} and substitute it
        # right now, so the printed command can be copy/pasted afterwards.
        # (GNOME #580272)
        if not '--exec-prefix' in template:
            cmd = cmd.replace('${exec_prefix}', buildscript.config.prefix)

        buildscript.execute(cmd, cwd = builddir, extra_env = self.extra_env)
    do_configure.depends = [PHASE_CHECKOUT]
    do_configure.error_phases = [PHASE_FORCE_CHECKOUT,
            PHASE_CLEAN, PHASE_DISTCLEAN]

    def skip_clean(self, buildscript, last_phase):
        builddir = self.get_builddir(buildscript)
        if not os.path.exists(builddir):
            return True
        if not os.path.exists(os.path.join(builddir, self.makefile)):
            return True
        return False

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        makeargs = self._get_makeargs(buildscript)
        cmd = '%s %s clean' % (os.environ.get('MAKE', 'make'), makeargs)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                extra_env = self.extra_env)
    do_clean.depends = [PHASE_CONFIGURE]
    do_clean.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        makeargs = self._get_makeargs(buildscript)
        cmd = '%s%s %s' % (self.static_analyzer_pre_cmd(buildscript), os.environ.get('MAKE', 'make'), makeargs)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                extra_env = self.extra_env)
    do_build.depends = [PHASE_CONFIGURE]
    do_build.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE,
            PHASE_CLEAN, PHASE_DISTCLEAN]

    def static_analyzer_pre_cmd(self, buildscript):
        if self.supports_static_analyzer and buildscript.config.module_static_analyzer.get(self.name, buildscript.config.static_analyzer):
            template = buildscript.config.static_analyzer_template + ' '
            outputdir = buildscript.config.static_analyzer_outputdir

            if not os.path.exists(outputdir):
                os.makedirs(outputdir)

            vars = {'outputdir': outputdir,
                    'module': self.name
                   }

            return template % vars
        return ''

    def skip_check(self, buildscript, last_phase):
        if not self.check_target:
            return True
        if self.name in buildscript.config.module_makecheck:
            return not buildscript.config.module_makecheck[self.name]
        if 'check' not in buildscript.config.build_targets:
            return True
        return False

    def do_check(self, buildscript):
        buildscript.set_action(_('Checking'), self)
        makeargs = self._get_makeargs(buildscript)
        cmd = '%s%s %s check' % (self.static_analyzer_pre_cmd(buildscript), os.environ.get('MAKE', 'make'), makeargs)
        try:
            buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                    extra_env = self.extra_env)
        except CommandError:
            if not buildscript.config.makecheck_advisory:
                raise
    do_check.depends = [PHASE_BUILD]
    do_check.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_dist(self, buildscript):
        buildscript.set_action(_('Creating tarball for'), self)
        makeargs = self._get_makeargs(buildscript)
        cmd = '%s %s dist' % (os.environ.get('MAKE', 'make'), makeargs)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                    extra_env = self.extra_env)
    do_dist.depends = [PHASE_CONFIGURE]
    do_dist.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_distcheck(self, buildscript):
        buildscript.set_action(_('Dist checking'), self)
        makeargs = self._get_makeargs(buildscript)
        cmd = '%s %s distcheck' % (os.environ.get('MAKE', 'make'), makeargs)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                    extra_env = self.extra_env)
    do_distcheck.depends = [PHASE_DIST]
    do_distcheck.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        destdir = self.prepare_installroot(buildscript)
        if self.makeinstallargs:
            cmd = '%s %s DESTDIR=%s' % (os.environ.get('MAKE', 'make'),
                                        self.makeinstallargs,
                                        destdir)
        else:
            cmd = '%s install DESTDIR=%s' % (os.environ.get('MAKE', 'make'),
                                             destdir)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                    extra_env = self.extra_env)
        self.process_install(buildscript, self.get_revision())

    do_install.depends = [PHASE_BUILD]

    def do_distclean(self, buildscript):
        buildscript.set_action(_('Distcleaning'), self)
        makeargs = self._get_makeargs(buildscript)
        cmd = '%s %s distclean' % (os.environ.get('MAKE', 'make'), makeargs)
        buildscript.execute(cmd, cwd = self.get_builddir(buildscript),
                    extra_env = self.extra_env)
    do_distclean.depends = [PHASE_CONFIGURE]

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
                 ('supports-static-analyzer', 'supports_static_analyzer', True),
                 ('autogen-template', 'autogen_template', None)])


def parse_autotools(node, config, uri, repositories, default_repo):
    instance = AutogenModule.parse_from_xml(node, config, uri, repositories, default_repo)

    # Make some substitutions; do special handling of '${prefix}' and '${libdir}'
    prefix_re = re.compile('(\${prefix})')
    # I'm not sure the replacement of ${libdir} is necessary for firefox...
    libdir_re = re.compile('(\${libdir})')
    libsubdir = '/lib'
    if config.use_lib64:
        libsubdir = '/lib64'

    if node.hasAttribute('autogenargs'):
        autogenargs = node.getAttribute('autogenargs')
        autogenargs = prefix_re.sub(config.prefix, autogenargs)
        autogenargs = libdir_re.sub(config.prefix + libsubdir, autogenargs)        
        instance.autogenargs = autogenargs
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')
        makeargs = prefix_re.sub(config.prefix, makeargs)
        makeargs = libdir_re.sub(config.prefix + libsubdir, makeargs)
        instance.makeargs = makeargs
    if node.hasAttribute('makeinstallargs'):
        makeinstallargs = node.getAttribute('makeinstallargs')
        makeinstallargs = prefix_re.sub(config.prefix, makeinstallargs)
        makeinstallargs = libdir_re.sub(config.prefix + libsubdir, makeinstallargs)
        instance.makeinstallargs = makeinstallargs

    if node.hasAttribute('supports-non-srcdir-builds'):
        supports_non_srcdir_builds = (node.getAttribute('supports-non-srcdir-builds') != 'no')
    if node.hasAttribute('skip-autogen'):
        skip_autogen = node.getAttribute('skip-autogen')
        if skip_autogen == 'true':
            instance.skip_autogen = True
        elif skip_autogen == 'never':
            instance.skip_autogen = 'never'

    if node.hasAttribute('check-target'):
        instance.check_target = (node.getAttribute('check-target') == 'true')
    if node.hasAttribute('static-analyzer'):
        instance.supports_static_analyzer = (node.getAttribute('static-analyzer') == 'true')

    from jhbuild.versioncontrol.tarball import TarballBranch
    if node.hasAttribute('autogen-sh'):
        autogen_sh = node.getAttribute('autogen-sh')
        if autogen_sh is not None:
            instance.autogen_sh = autogen_sh
        elif isinstance(instance.branch, TarballBranch):
            # in tarballs, force autogen-sh to be configure, unless autogen-sh is
            # already set
            instance.autogen_sh = 'configure'

    if node.hasAttribute('makefile'):
        instance.makefile = node.getAttribute('makefile')
    if node.hasAttribute('autogen-template'):
        instance.autogen_template = node.getAttribute('autogen-template')

    return instance
register_module_type('autotools', parse_autotools)

