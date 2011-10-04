# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   base.py: the most common jhbuild commands
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

import os
import re
import stat
import sys
import time
from optparse import make_option
import logging

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import UsageError, FatalError, CommandError
from jhbuild.commands import Command, register_command

from jhbuild.config import parse_relative_time


class cmd_update(Command):
    doc = N_('Update all modules from version control')

    name = 'update'
    usage_args = N_('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help=_('treat the given modules as up to date')),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help=_('start building at the given module')),
            make_option('--tags',
                        action='append', dest='tags', default=[],
                        help=_('build only modules with the given tags')),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help=_('set a sticky date when checking out modules')),
            make_option('--ignore-suggests',
                        action='store_true', dest='ignore_suggests', default=False,
                        help=_('ignore all soft-dependencies')),
            ])

    def run(self, config, options, args, help=None):
        config.set_from_cmdline_options(options)
        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                config.skip, tags=config.tags,
                ignore_suggests=config.ignore_suggests)
        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError(_('%s not in module list') % options.startat)

        # don't actually perform build ...
        config.build_targets = ['checkout']
        config.nonetwork = False

        build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
        return build.build()

register_command(cmd_update)


class cmd_updateone(Command):
    doc = N_('Update one or more modules from version control')

    name = 'updateone'
    usage_args = N_('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help=_('set a sticky date when checking out modules')),
            ])

    def run(self, config, options, args, help=None):
        config.set_from_cmdline_options(options)
        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.get_module(modname, ignore_case = True) for modname in args]
        except KeyError, e:
            raise FatalError(_("A module called '%s' could not be found.") % e)

        if not module_list:
            self.parser.error(_('This command requires a module parameter.'))

        # don't actually perform build ...
        config.build_targets = ['checkout']
        config.nonetwork = False

        build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
        return build.build()

register_command(cmd_updateone)


class cmd_cleanone(Command):
    doc = N_('Clean one or more modules')

    name = 'cleanone'
    usage_args = N_('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('--honour-config',
                        action='store_true', dest='honour_config', default=False,
                        help=_('honour the makeclean setting in config file')),
            ])

    def run(self, config, options, args, help=None):
        if options.honour_config is False:
            config.makeclean = True
        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.get_module(modname, ignore_case = True) for modname in args]
        except KeyError, e:
            raise FatalError(_("A module called '%s' could not be found.") % e)

        if not module_list:
            self.parser.error(_('This command requires a module parameter.'))

        if not config.makeclean:
            logging.info(
                    _('clean command called while makeclean is set to False, skipped.'))
            return 0

        build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
        return build.build(phases=['clean'])

register_command(cmd_cleanone)


def check_bootstrap_updateness(config):
    '''Check install date of bootstrap modules, and compare them to
       the bootstrap moduleset file last modification date.
    '''
    try:
        module_set = jhbuild.moduleset.load(config, uri = 'bootstrap')
    except:
        # failed to get bootstrap moduleset, silently ignore.
        return
    packagedb = module_set.packagedb

    max_install_date = max([
            packagedb.installdate(module.name)
            for module in module_set.modules.values()])

    if max_install_date is None:
        # bootstrap module has never been built; probably the user doesn't want
        # to use it
        return

    updated_modules = []
    for module in module_set.modules.values():
        pkg = packagedb.get(module.name)
        if pkg is None:
            continue
        p_version = pkg.version
        if p_version != module.get_revision():
            updated_modules.append(module.name)

    if not config.modulesets_dir:
        return
    bootstrap_uri = os.path.join(config.modulesets_dir, 'bootstrap.modules')
    if not os.path.exists(bootstrap_uri):
        return
    bootstrap_mtime = os.stat(bootstrap_uri)[stat.ST_MTIME]

    if max_install_date <= bootstrap_mtime:
        # general note, to cover added modules
        logging.info(
                _('bootstrap moduleset has been updated since the last time '\
                  'you used it, perhaps you should run jhbuild bootstrap.'))

    if updated_modules:
        # note about updated modules
        logging.info(
                _('some bootstrap modules have been updated, '\
                  'perhaps you should update them: %s.') % \
                  ', '.join(updated_modules))


class cmd_build(Command):
    doc = N_('Update and compile all modules (the default)')

    name = 'build'
    usage_args = N_('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='_unused', default=False,
                        help=_('This option does nothing anymore')),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help=_('run make clean before make')),
            make_option('--check',
                        action='store_true', dest='check', default=False,
                        help=_('run make check after building')),
            make_option('-d', '--dist',
                        action='store_true', dest='dist', default=False,
                        help=_('run make dist after building')),
            make_option('--distcheck',
                        action='store_true', dest='distcheck', default=False,
                        help=_('run make distcheck after building')),
            make_option('--ignore-suggests',
                        action='store_true', dest='ignore_suggests', default=False,
                        help=_('ignore all soft-dependencies')),
            make_option('-n', '--no-network',
                        action='store_true', dest='nonetwork', default=False,
                        help=_('skip version control update')),
            make_option('-q', '--quiet',
                        action='store_true', dest='quiet', default=False,
                        help=_('quiet (no output)')),
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help=_('treat the given modules as up to date')),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help=_('start building at the given module')),
            make_option('--tags',
                        action='append', dest='tags', default=[],
                        help=_('build only modules with the given tags')),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help=_('set a sticky date when checking out modules')),
            make_option('-x', '--no-xvfb',
                        action='store_true', dest='noxvfb', default=False,
                        help=_('run tests in real X and not in Xvfb')),
            make_option('-C', '--try-checkout',
                        action='store_true', dest='trycheckout', default=False,
                        help=_('try to force checkout and autogen on failure')),
            make_option('-N', '--no-poison',
                        action='store_true', dest='nopoison', default=False,
                        help=_("don't poison modules on failure")),
            make_option('-f', '--force',
                        action='store_true', dest='force_policy', default=False,
                        help=_('build even if policy says not to')),
            make_option('--build-optional-modules',
                        action='store_true', dest='build_optional_modules', default=False,
                        help=_('also build soft-dependencies that could be skipped')),
            make_option('--min-age', metavar='TIME-SPEC',
                        action='store', dest='min_age', default=None,
                        help=_('skip modules installed less than the given time ago')),
            ])

    def run(self, config, options, args, help=None):
        config.set_from_cmdline_options(options)

        if not config.quiet_mode:
            check_bootstrap_updateness(config)

        module_set = jhbuild.moduleset.load(config)
        modules = args or config.modules
        module_list = module_set.get_module_list(modules,
                config.skip, tags = config.tags,
                include_optional_modules=options.build_optional_modules,
                ignore_suggests=config.ignore_suggests)
        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError(_('%s not in module list') % options.startat)

        if len(module_list) == 0 and modules[0] in (config.skip or []):
            logging.info(
                    _('requested module is in the ignore list, nothing to do.'))
            return 0

        build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
        return build.build()

register_command(cmd_build)


class cmd_buildone(Command):
    doc = N_('Update and compile one or more modules')

    name = 'buildone'
    usage_args = N_('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='_unused', default=False,
                        help=_('This option does nothing anymore')),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help=_('run make clean before make')),
            make_option('--check',
                        action='store_true', dest='check', default=False,
                        help=_('run make check after building')),
            make_option('-d', '--dist',
                        action='store_true', dest='dist', default=False,
                        help=_('run make dist after building')),
            make_option('--distcheck',
                        action='store_true', dest='distcheck', default=False,
                        help=_('run make distcheck after building')),
            make_option('-n', '--no-network',
                        action='store_true', dest='nonetwork', default=False,
                        help=_('skip version control update')),
            make_option('-q', '--quiet',
                        action='store_true', dest='quiet', default=False,
                        help=_('quiet (no output)')),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help=_('set a sticky date when checking out modules')),
            make_option('-x', '--no-xvfb',
                        action='store_true', dest='noxvfb', default=False,
                        help=_('run tests in real X and not in Xvfb')),
            make_option('-f', '--force',
                        action='store_true', dest='force_policy', default=False,
                        help=_('build even if policy says not to')),
            make_option('--min-age', metavar='TIME-SPEC',
                        action='store', dest='min_age', default=None,
                        help=_('skip modules installed less than the given time ago')),
            ])

    def run(self, config, options, args, help=None):
        config.set_from_cmdline_options(options)

        if not config.quiet_mode:
            check_bootstrap_updateness(config)

        module_set = jhbuild.moduleset.load(config)
        module_list = []
        for modname in args:
            try:
                module = module_set.get_module(modname, ignore_case=True)
            except KeyError, e:
                default_repo = jhbuild.moduleset.get_default_repo()
                if not default_repo:
                    continue
                from jhbuild.modtypes.autotools import AutogenModule
                module = AutogenModule(modname, default_repo.branch(modname))
                module.config = config
                logging.info(_('module "%s" does not exist, created automatically using repository "%s"') % \
                                (modname, default_repo.name))
            module_list.append(module)

        if not module_list:
            self.parser.error(_('This command requires a module parameter.'))

        build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
        return build.build()

register_command(cmd_buildone)

class cmd_run(Command):
    doc = N_('Run a command under the JHBuild environment')

    name = 'run'
    usage_args = N_('[ options ... ] program [ arguments ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('--in-builddir', metavar='MODULE',
                        action='store', dest='in_builddir', default = None,
                        help=_('run command in build dir of the given module')),
            make_option('--in-checkoutdir', metavar='MODULE',
                        action='store', dest='in_checkoutdir', default = None,
                        help=_('run command in checkout dir of the given module')),
            ])

    def execute(self, config, args, help=None):
        # Do a shallow check of the arguments list
        # so that '--' isn't always required when command has arguments, 
        # only if some of them look like they might be for us
        if not args or args[0] in ('--', '--help') or args[0].startswith('--in-builddir') or args[0].startswith('--in-checkoutdir'):
            options, args = self.parse_args(args)
            return self.run(config, options, args)
        try:
            return os.execlp(args[0], *args)
        except OSError, exc:
            raise FatalError(_("Unable to execute the command '%(command)s': %(err)s") % {
                    'command':args[0], 'err':str(exc)})

    def run(self, config, options, args, help=None):
        if options.in_builddir:
            module_set = jhbuild.moduleset.load(config)
            try:
                module_list = [module_set.get_module(options.in_builddir, ignore_case = True)
                               for modname in args]
            except KeyError, e:
                raise FatalError(_("A module called '%s' could not be found.") % e)

            build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
            builddir = module_list[0].get_builddir(build)
            try:
                build.execute(args, cwd=builddir)
            except CommandError, exc:
                if args:
                    raise FatalError(_("Unable to execute the command '%s'") % args[0])
                else:
                    raise FatalError(str(exc))
        elif options.in_checkoutdir:
            module_set = jhbuild.moduleset.load(config)
            try:
                module_list = [module_set.get_module(options.in_checkoutdir, ignore_case = True)
                               for modname in args]
            except KeyError, e:
                raise FatalError(_("A module called '%s' could not be found.") % e)

            build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
            checkoutdir = module_list[0].get_srcdir(build)
            try:
                build.execute(args, cwd=checkoutdir)
            except CommandError, exc:
                if args:
                    raise FatalError(_("Unable to execute the command '%s'") % args[0])
                else:
                    raise FatalError(str(exc))
        else:
            try:
                os.execlp(args[0], *args)
            except IndexError:
                raise FatalError(_('No command given'))
            except OSError, exc:
                raise FatalError(_("Unable to execute the command '%(command)s': %(err)s") % {
                        'command':args[0], 'err':str(exc)})

register_command(cmd_run)


class cmd_shell(Command):
    doc = N_('Start a shell under the JHBuild environment')

    name = 'shell'
    usage_args = ''

    def execute(self, config, args, help=None):
        if "--help" in args:
            self.parse_args(args) # This doesn't return
        user_shell = os.environ.get('SHELL', '/bin/sh')
        os.execlp(user_shell, user_shell)

register_command(cmd_shell)


class cmd_list(Command):
    doc = N_('List the modules that would be built')

    name = 'list'
    usage_args = N_('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('-r', '--show-revision',
                        action='store_true', dest='show_rev', default=False,
                        help=_('show which revision will be built')),
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help=_('treat the given modules as up to date')),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help=_('start list at the given module')),
            make_option('--tags',
                        action='append', dest='tags', default=[],
                        help=_('build only modules with the given tags')),
            make_option('--ignore-suggests',
                        action='store_true', dest='ignore_suggests', default=False,
                        help=_('ignore all soft-dependencies')),
            make_option('--list-optional-modules',
                        action='store_true', dest='list_optional_modules', default=False,
                        help=_('also list soft-dependencies that could be skipped')),
            make_option('-a', '--all-modules',
                        action='store_true', dest='list_all_modules', default=False,
                        help=_('list all modules, not only those that would be built')),
            ])

    def run(self, config, options, args, help=None):
        config.set_from_cmdline_options(options)
        module_set = jhbuild.moduleset.load(config)
        if options.startat and options.list_all_modules:
            raise UsageError(_('Conflicting options specified '
                               '(\'%s\' and \'%s\')') % \
                               ('--start-at', '--all-modules'))

        if options.list_all_modules:
            module_list = module_set.modules.values()
        else:
            module_list = module_set.get_module_list(args or config.modules,
                                config.skip, tags = config.tags,
                                include_optional_modules = options.list_optional_modules,
                                ignore_suggests=config.ignore_suggests)

        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError(_('%s not in module list') % options.startat)

        for mod in module_list:
            if options.show_rev:
                rev = mod.get_revision()
                if rev:
                    uprint('%s (%s)' % (mod.name, rev))
                else:
                    uprint(mod.name)
            else:
                uprint(mod.name)

register_command(cmd_list)


class cmd_dot(Command):
    doc = N_('Output a Graphviz dependency graph for one or more modules')

    name = 'dot'
    usage_args = N_('[ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('--soft-deps',
                        action='store_true', dest='soft_deps', default=False,
                        help=_('add dotted lines to soft dependencies')),
            make_option('--clusters',
                        action='store_true', dest='clusters', default=False,
                        help=_('group modules from metamodule together')),
            ])

    def run(self, config, options, args, help=None):
        module_set = jhbuild.moduleset.load(config)
        if args:
            modules = args
        elif config.modules == 'all':
            modules = None
        else:
            modules = config.modules
        kwargs = {}
        if options.soft_deps:
            kwargs['suggests'] = True
        if options.clusters:
            kwargs['clusters'] = True
        module_set.write_dot(modules, **kwargs)

register_command(cmd_dot)
