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


def parse_relative_time(s):
    m = re.match(r'(\d+) *([smhdw])', s.lower())
    if m:
        coeffs = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w':7*86400}
        return float(m.group(1)) * coeffs[m.group(2)]
    else:
        raise ValueError(_('unable to parse \'%s\' as relative time.') % s)


class cmd_update(Command):
    doc = _('Update all modules from version control')

    name = 'update'
    usage_args = '[ options ... ] [ modules ... ]'

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

    def run(self, config, options, args):
        for item in options.skip:
            config.skip += item.split(',')
        for item in options.tags:
            config.tags += item.split(',')
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date
        if options.ignore_suggests:
            config.ignore_suggests = True

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
        config.nobuild = True
        config.nonetwork = False

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_update)


class cmd_updateone(Command):
    doc = _('Update one or more modules from version control')

    name = 'updateone'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help=_('set a sticky date when checking out modules')),
            ])

    def run(self, config, options, args):
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date
        
        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.get_module(modname, ignore_case = True) for modname in args]
        except KeyError, e:
            raise FatalError(_("A module called '%s' could not be found.") % e)

        if not module_list:
            self.parser.error(_('This command requires a module parameter.'))

        # don't actually perform build ...
        config.nobuild = True
        config.nonetwork = False

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_updateone)


class cmd_cleanone(Command):
    doc = _('Clean one or more modules')

    name = 'cleanone'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('--honour-config',
                        action='store_true', dest='honour_config', default=False,
                        help=_('honour the makeclean setting in config file')),
            ])

    def run(self, config, options, args):
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

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.clean()

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
    packagedb = jhbuild.frontends.get_buildscript(config, []).packagedb

    max_install_date = max([
            packagedb.installdate(module.name)
            for module in module_set.modules.values()])

    if max_install_date is None:
        # bootstrap module has never been built; probably the user doesn't want
        # to use it
        return

    updated_modules = []
    for module in module_set.modules.values():
        if not packagedb.entries.has_key(module.name):
            continue
        p_version = packagedb.entries.get(module.name)[0]
        if p_version != module.get_revision():
            updated_modules.append(module.name)

    bootstrap_uri = os.path.join(config.modulesets_dir, 'bootstrap.modules')
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
    doc = _('Update and compile all modules (the default)')

    name = 'build'
    usage_args = _('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='autogen', default=False,
                        help=_('always run autogen.sh')),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help=_('run make clean before make')),
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

    def run(self, config, options, args):
        if options.autogen:
            config.alwaysautogen = True
        if options.clean:
            config.makeclean = True
        if options.dist:
            config.makedist = True
        if options.ignore_suggests:
            config.ignore_suggests = True
        if options.distcheck:
            config.makedistcheck = True
        if options.nonetwork:
            config.nonetwork = True
        for item in options.skip:
            config.skip += item.split(',')
        for item in options.tags:
            config.tags += item.split(',')
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date
        if options.noxvfb is not None:
            config.noxvfb = options.noxvfb
        if options.trycheckout:
            config.trycheckout = True
        if options.nopoison:
            config.nopoison = True
        if options.quiet:
            config.quiet_mode = True
        if options.force_policy:
            config.build_policy = 'all'
        if options.min_age:
            try:
                config.min_time = time.time() - parse_relative_time(options.min_age)
            except ValueError:
                raise FatalError(_('Failed to parse relative time'))

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

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_build)


class cmd_buildone(Command):
    doc = _('Update and compile one or more modules')

    name = 'buildone'
    usage_args = _('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='autogen', default=False,
                        help=_('always run autogen.sh')),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help=_('run make clean before make')),
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

    def run(self, config, options, args):
        if options.autogen:
            config.alwaysautogen = True
        if options.clean:
            config.makeclean = True
        if options.dist:
            config.makedist = True
        if options.distcheck:
            config.makedistcheck = True
        if options.nonetwork:
            config.nonetwork = True
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date
        if options.noxvfb is not None:
            config.noxvfb = options.noxvfb
        if options.quiet:
            config.quiet_mode = True
        if options.force_policy:
            config.build_policy = 'all'
        if options.min_age:
            try:
                config.min_time = time.time() - parse_relative_time(options.min_age)
            except ValueError:
                raise FatalError(_('Failed to parse relative time'))

        if not config.quiet_mode:
            check_bootstrap_updateness(config)

        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.get_module(modname, ignore_case = True) for modname in args]
        except KeyError, e:
            raise FatalError(_("A module called '%s' could not be found.") % e)

        if not module_list:
            self.parser.error(_('This command requires a module parameter.'))

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_buildone)


class cmd_run(Command):
    doc = _('Run a command under the JHBuild environment')

    name = 'run'
    usage_args = _('[ options ... ] program [ arguments ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('--in-builddir', metavar='MODULE',
                        action='store', dest='in_builddir', default = None,
                        help=_('run command in build dir of the given module')),
            ])

    def execute(self, config, args):
        if not args or args[0] in ('--', '--in-builddir', '--help'):
            options, args = self.parse_args(args)
            return self.run(config, options, args)
        try:
            return os.execlp(args[0], *args)
        except OSError, exc:
            raise FatalError(_("Unable to execute the command '%(command)s': %(err)s") % {
                    'command':args[0], 'err':str(exc)})

    def run(self, config, options, args):
        if options.in_builddir:
            module_set = jhbuild.moduleset.load(config)
            try:
                module_list = [module_set.get_module(options.in_builddir, ignore_case = True)
                               for modname in args]
            except KeyError, e:
                raise FatalError(_("A module called '%s' could not be found.") % e)

            build = jhbuild.frontends.get_buildscript(config, module_list)
            builddir = module_list[0].get_builddir(build)
            try:
                build.execute(args, cwd=builddir)
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
    doc = _('Start a shell under the JHBuild environment')

    name = 'shell'
    usage_args = ''

    def execute(self, config, args):
        if "--help" in args:
            self.parse_args(args) # This doesn't return
        user_shell = os.environ.get('SHELL', '/bin/sh')
        os.execlp(user_shell, user_shell)

register_command(cmd_shell)


class cmd_list(Command):
    doc = _('List the modules that would be built')

    name = 'list'
    usage_args = _('[ options ... ] [ modules ... ]')

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

    def run(self, config, options, args):
        for item in options.skip:
            config.skip += item.split(',')
        for item in options.tags:
            config.tags += item.split(',')
        if options.ignore_suggests:
            config.ignore_suggests = True
        module_set = jhbuild.moduleset.load(config)
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
    doc = _('Output a Graphviz dependency graph for one or more modules')

    name = 'dot'
    usage_args = _('[ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('--soft-deps',
                        action='store_true', dest='soft_deps', default=False,
                        help=_('add dotted lines to soft dependencies')),
            make_option('--clusters',
                        action='store_true', dest='clusters', default=False,
                        help=_('group modules from metamodule together')),
            ])

    def run(self, config, options, args):
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
