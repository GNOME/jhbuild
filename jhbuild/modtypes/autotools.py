# jhbuild - a tool to ease building collections of source packages
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
import stat
import hashlib

from jhbuild.errors import FatalError, CommandError
from jhbuild.modtypes import \
     DownloadableModule, register_module_type, MakeModule
from jhbuild.versioncontrol.tarball import TarballBranch
from jhbuild.utils import _

__all__ = [ 'AutogenModule' ]

class AutogenModule(MakeModule, DownloadableModule):
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
                 skip_install_phase=False,
                 uninstall_before_install=False,
                 autogen_sh='autogen.sh',
                 makefile='Makefile',
                 autogen_template=None,
                 check_target=True,
                 supports_static_analyzer=True,
                 needs_gmake=True,
                 supports_unknown_configure_options=True):
        MakeModule.__init__(self, name, branch=branch, makeargs=makeargs,
                            makeinstallargs=makeinstallargs, makefile=makefile, needs_gmake=needs_gmake)
        self.autogenargs = autogenargs
        self.supports_non_srcdir_builds = supports_non_srcdir_builds
        self.force_non_srcdir_builds = False
        self.skip_autogen = skip_autogen
        self.skip_install_phase = skip_install_phase
        self.uninstall_before_install = uninstall_before_install
        self.autogen_sh = autogen_sh
        self.autogen_template = autogen_template
        self.check_target = check_target
        self.supports_install_destdir = True
        self.supports_static_analyzer = supports_static_analyzer
        self.supports_unknown_configure_options = supports_unknown_configure_options

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        builddir = self.get_srcdir(buildscript)
        if buildscript.config.buildroot and self.supports_non_srcdir_builds:
            d = buildscript.config.builddir_pattern % (
                self.branch.checkoutdir or self.branch.get_module_basename())
            builddir = os.path.join(buildscript.config.buildroot, d)
        if self.force_non_srcdir_builds and builddir == self.get_srcdir(buildscript):
            builddir = os.path.join(builddir, 'build')
        return builddir

    def _file_exists_and_is_newer_than(self, potential, other):
        try:
            other_stbuf = os.stat(other)
            potential_stbuf = os.stat(potential)
        except OSError:
            return False
        return potential_stbuf.st_mtime > other_stbuf.st_mtime

    def _get_configure_cmd(self, buildscript):
        '''returns a string of the command-line to configure the module.
        This method may modify self.autogen_sh, if 'autogen.sh' doesn't exist.
        FIXME: bad idea to modify self.autogen_sh in a getter.
        '''
        srcdir = self.get_srcdir(buildscript)
        if self.autogen_sh == 'autogen.sh' and \
        not os.path.exists(os.path.join(srcdir, self.autogen_sh)):
            # if there is no autogen.sh, automatically fallback to configure
            if os.path.exists(os.path.join(srcdir, 'configure')):
                self.autogen_sh = 'configure'

        if self.autogen_template:
            template = self.autogen_template
        else:
            template = ("%(srcdir)s/%(autogen-sh)s --prefix %(prefix)s %(autogenargs)s ")

        default_autogenargs = (self.config.autogenargs
            if self.supports_unknown_configure_options else '')
        autogenargs = self.autogenargs + ' ' + self.config.module_autogenargs.get(
                self.name, default_autogenargs)

        if self.config.disable_Werror and self.supports_unknown_configure_options:
            autogenargs = '--disable-Werror' + ' ' + autogenargs

        vars = {'prefix': os.path.splitdrive(buildscript.config.prefix)[1],
                'autogen-sh': self.autogen_sh,
                'autogenargs': autogenargs}

        if buildscript.config.buildroot and self.supports_non_srcdir_builds or \
           self.force_non_srcdir_builds:
            vars['srcdir'] = self.get_srcdir(buildscript)
        else:
            vars['srcdir'] = '.'

        cmd = self.static_analyzer_pre_cmd(buildscript) + template % vars

        if self.autogen_sh == 'autoreconf':
            cmd = cmd.replace('autoreconf', 'configure')
            cmd = cmd.replace('--enable-maintainer-mode', '')

        # if we are using configure as the autogen command, make sure
        # we don't pass --enable-maintainer-mode, since it breaks many
        # tarball builds.
        if self.autogen_sh == 'configure':
            cmd = cmd.replace('--enable-maintainer-mode', '')

        # If there is no --exec-prefix in the constructed autogen command, we
        # can safely assume it will be the same as {prefix} and substitute it
        # right now, so the printed command can be copy/pasted afterwards.
        # (GNOME #580272)
        if '--exec-prefix' not in template:
            cmd = cmd.replace('${exec_prefix}', vars['prefix'])

        self.configure_cmd = cmd
        return cmd

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

        if buildscript.config.alwaysautogen:
            return False

        srcdir = self.get_srcdir(buildscript)
        configure_path = os.path.join(srcdir, 'configure')
        if not os.path.exists(configure_path):
            return False

        # if autogen.sh args has changed, re-run configure
        db_entry = buildscript.moduleset.packagedb.get(self.name)
        if db_entry:
            configure_hash = db_entry.metadata.get('configure-hash')
            if configure_hash:
                configure_cmd = self._get_configure_cmd(buildscript)
                if hashlib.md5(configure_cmd.encode("utf-8")).hexdigest() != configure_hash:
                    return False
            else:
                # force one-time reconfigure if no configure-hash
                return False
        else:
            # always configure for the first build
            return False

        # We can't rely on the autotools maintainer-mode stuff because many
        # modules' autogen.sh script includes e.g. gtk-doc and/or intltool,
        # which also need to be rerun.
        # https://bugzilla.gnome.org/show_bug.cgi?id=660844
        if not isinstance(self.branch, TarballBranch):
            configsrc = None
            for name in ['configure.ac', 'configure.in']:
                path = os.path.join(srcdir, name)
                if os.path.exists(path):
                    configsrc = path
                    break
            if configsrc is not None:
                config_status = os.path.join(self.get_builddir(buildscript),
                                             'config.status')
                if self._file_exists_and_is_newer_than(config_status,
                                                       configsrc):
                    return True

        return False

    def do_configure(self, buildscript):
        builddir = self.get_builddir(buildscript)
        if not os.path.exists(builddir):
            os.makedirs(builddir)
        buildscript.set_action(_('Configuring'), self)

        cmd = self._get_configure_cmd(buildscript)

        srcdir = self.get_srcdir(buildscript)
        try:
            if not (os.stat(os.path.join(srcdir, self.autogen_sh))[stat.ST_MODE] & 0o111):
                os.chmod(os.path.join(srcdir, self.autogen_sh), 0o755)
        except EnvironmentError:
            pass

        if self.autogen_sh == 'autoreconf':
            buildscript.execute(['autoreconf', '-fi'], cwd=srcdir)
            os.chmod(os.path.join(srcdir, 'configure'), 0o755)

        buildscript.execute(cmd, cwd = builddir, extra_env = self.extra_env)
    do_configure.depends = [PHASE_CHECKOUT]
    do_configure.error_phases = [PHASE_FORCE_CHECKOUT,
            PHASE_CLEAN, PHASE_DISTCLEAN]

    def skip_clean(self, buildscript, last_phase):
        if 'distclean' in self.config.build_targets:
            return True
        builddir = self.get_builddir(buildscript)
        if not os.path.exists(builddir):
            return True
        if not os.path.exists(os.path.join(builddir, self.makefile)):
            return True
        return False

    def do_clean(self, buildscript):
        buildscript.set_action(_('Cleaning'), self)
        self.make(buildscript, 'clean')
    do_clean.depends = [PHASE_CONFIGURE]
    do_clean.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        self.make(buildscript, pre=self.static_analyzer_pre_cmd(buildscript))
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
        try:
            self.make(buildscript, 'check', pre=self.static_analyzer_pre_cmd(buildscript))
        except CommandError:
            if not buildscript.config.makecheck_advisory:
                raise
    do_check.depends = [PHASE_BUILD]
    do_check.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_dist(self, buildscript):
        buildscript.set_action(_('Creating tarball for'), self)
        self.make(buildscript, 'dist')
    do_dist.depends = [PHASE_CONFIGURE]
    do_dist.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_distcheck(self, buildscript):
        buildscript.set_action(_('Dist checking'), self)
        self.make(buildscript, 'distcheck')
    do_distcheck.depends = [PHASE_DIST]
    do_distcheck.error_phases = [PHASE_FORCE_CHECKOUT, PHASE_CONFIGURE]

    def do_install(self, buildscript):
        if self.uninstall_before_install:
            packagedb = buildscript.moduleset.packagedb
            if packagedb.check(self.name):
                buildscript.set_action(_('Uninstalling old installed version'), self)
                packagedb.uninstall(self.name)

        buildscript.set_action(_('Installing'), self)
        destdir = self.prepare_installroot(buildscript)
        self.make(buildscript, self.makeinstallargs or 'install', makeargs='DESTDIR={}'.format(destdir))
        self.process_install(buildscript, self.get_revision())

    do_install.depends = [PHASE_BUILD]
    do_install.error_phases = [PHASE_CONFIGURE]

    def skip_install(self, buildscript, last_phase):
        return self.config.noinstall or self.skip_install_phase

    def skip_distclean(self, buildscript, last_phase):
        builddir = self.get_builddir(buildscript)
        if not os.path.exists(builddir):
            return True
        if not os.path.exists(os.path.join(builddir, self.makefile)) and \
           not hasattr(self.branch, 'delete_unknown_files'):
            return True

        return False

    def do_distclean(self, buildscript):
        buildscript.set_action(_('Distcleaning'), self)
        if hasattr(self.branch, 'delete_unknown_files'):
            self.branch.delete_unknown_files(buildscript)
        else:
            self.make(buildscript, 'distclean')
    do_distclean.depends = [PHASE_CHECKOUT]

    def xml_tag_and_attrs(self):
        return ('autotools',
                [('autogenargs', 'autogenargs', ''),
                 ('id', 'name', None),
                 ('makeargs', 'makeargs', ''),
                 ('makeinstallargs', 'makeinstallargs', ''),
                 ('supports-non-srcdir-builds',
                  'supports_non_srcdir_builds', True),
                 ('force-non-srcdir-builds',
                  'force_non_srcdir_builds', False),
                 ('supports-unknown-configure-options',
                  'supports_unknown_configure_options', True),
                 ('skip-autogen', 'skip_autogen', False),
                 ('skip-install', 'skip_install_phase', False),
                 ('uninstall-before-install', 'uninstall_before_install', False),
                 ('autogen-sh', 'autogen_sh', 'autogen.sh'),
                 ('makefile', 'makefile', 'Makefile'),
                 ('supports-static-analyzer', 'supports_static_analyzer', True),
                 ('autogen-template', 'autogen_template', None)])

def collect_args(instance, node, argtype):
    if node.hasAttribute(argtype):
        args = node.getAttribute(argtype)
    else:
        args = ''

    for child in node.childNodes:
        if child.nodeType == child.ELEMENT_NODE and child.nodeName == argtype:
            if not child.hasAttribute('value'):
                raise FatalError(_("<%s/> tag must contain value=''") % argtype)
            args += ' ' + child.getAttribute('value')

    return instance.eval_args(args)

def parse_autotools(node, config, uri, repositories, default_repo):
    instance = AutogenModule.parse_from_xml(node, config, uri, repositories, default_repo)

    # Allow base packages such as autoconf/automake/libtool/etc. to skip the
    # standard dependencies to prevent dependency cycles.
    if node.getAttribute('bootstrap') != 'true':
        instance.dependencies += ['automake', 'libtool', instance.get_makecmd(config)]

    instance.autogenargs = collect_args (instance, node, 'autogenargs')
    instance.makeargs = collect_args (instance, node, 'makeargs')
    instance.makeinstallargs = collect_args (instance, node, 'makeinstallargs')

    if node.hasAttribute('supports-non-srcdir-builds'):
        instance.supports_non_srcdir_builds = \
                (node.getAttribute('supports-non-srcdir-builds') != 'no')
    if node.hasAttribute('force-non-srcdir-builds'):
        instance.force_non_srcdir_builds = \
                (node.getAttribute('force-non-srcdir-builds') != 'no')
    if node.hasAttribute('supports-unknown-configure-options'):
        instance.supports_unknown_configure_options = \
                (node.getAttribute('supports-unknown-configure-options') != 'no')
    if node.hasAttribute('skip-autogen'):
        skip_autogen = node.getAttribute('skip-autogen')
        if skip_autogen == 'true':
            instance.skip_autogen = True
        elif skip_autogen == 'never':
            instance.skip_autogen = 'never'
    if node.hasAttribute('skip-install'):
        skip_install = node.getAttribute('skip-install')
        if skip_install.lower() in ('true', 'yes'):
            instance.skip_install_phase = True
        else:
            instance.skip_install_phase = False
    if node.hasAttribute('uninstall-before-install'):
        instance.uninstall_before_install = (node.getAttribute('uninstall-before-install') == 'true')

    if node.hasAttribute('check-target'):
        instance.check_target = (node.getAttribute('check-target') == 'true')
    if node.hasAttribute('supports-static-analyzer'):
        instance.supports_static_analyzer = (node.getAttribute('supports-static-analyzer') == 'true')

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

