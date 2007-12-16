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
import sys
from optparse import make_option

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import UsageError, FatalError, CommandError
from jhbuild.commands import Command, register_command


class cmd_update(Command):
    """Update all modules from version control"""

    name = 'update'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help='treat the given modules as up to date'),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help='start building at the given module'),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help='set a sticky date when checking out modules'),
            ])

    def run(self, config, options, args):
        for item in options.skip:
            config.skip += item.split(',')
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date

        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                                                 config.skip)
        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError('%s not in module list' % options.startat)

        # don't actually perform build ...
        config.nobuild = True
        config.nonetwork = False

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_update)


class cmd_updateone(Command):
    """Update one or more modules from version control"""

    name = 'updateone'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help='set a sticky date when checking out modules'),
            ])

    def run(self, config, options, args):
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date

        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.modules[modname] for modname in args]
        except KeyError, e:
            raise FatalError("A module called '%s' could not be found."
                             % str(e))

        # don't actually perform build ...
        config.nobuild = True
        config.nonetwork = False

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_updateone)


class cmd_build(Command):
    """Update and compile all modules (the default)"""

    name = 'build'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='autogen', default=False,
                        help='always run autogen.sh'),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help='run make clean before make'),
            make_option('-d', '--dist',
                        action='store_true', dest='dist', default=False,
                        help='run make dist after building'),
            make_option('--distcheck',
                        action='store_true', dest='distcheck', default=False,
                        help='run make distcheck after building'),
            make_option('-n', '--no-network',
                        action='store_true', dest='nonetwork', default=False,
                        help='skip version control update'),
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help='treat the given modules as up to date'),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help='start building at the given module'),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help='set a sticky date when checking out modules'),
            make_option('-x', '--no-xvfb',
                        action='store_true', dest='noxvfb', default=False,
                        help='run tests in real X and not in Xvfb'),
            make_option('-C', '--try-checkout',
                        action='store_true', dest='trycheckout', default=False,
                        help='try to force checkout and autogen on failure'),
            make_option('-N', '--no-poison',
                        action='store_true', dest='nopoison', default=False,
                        help="don't poison modules on failure"),
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
        for item in options.skip:
            config.skip += item.split(',')
        if options.sticky_date is not None:
            config.sticky_date = options.sticky_date
        if options.noxvfb is not None:
            config.noxvfb = options.noxvfb
        if options.trycheckout:
            config.trycheckout = True
        if options.nopoison:
            config.nopoison = True

        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                                                 config.skip)
        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError('%s not in module list' % options.startat)

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_build)


class cmd_buildone(Command):
    """Update and compile one or more modules"""

    name = 'buildone'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='autogen', default=False,
                        help='always run autogen.sh'),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help='run make clean before make'),
            make_option('-d', '--dist',
                        action='store_true', dest='dist', default=False,
                        help='run make dist after building'),
            make_option('--distcheck',
                        action='store_true', dest='distcheck', default=False,
                        help='run make distcheck after building'),
            make_option('-n', '--no-network',
                        action='store_true', dest='nonetwork', default=False,
                        help='skip version control update'),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help='set a sticky date when checking out modules'),
            make_option('-x', '--no-xvfb',
                        action='store_true', dest='noxvfb', default=False,
                        help='Run tests in real X and not in Xvfb')
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

        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.modules[modname] for modname in args]
        except KeyError, e:
            raise FatalError("A module called '%s' could not be found."
                             % str(e))

        build = jhbuild.frontends.get_buildscript(config, module_list)
        return build.build()

register_command(cmd_buildone)


class cmd_run(Command):
    """Run a command under the JHBuild environment"""

    name = 'run'
    usage_args = '[ options ... ] program [ arguments ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('--in-builddir', metavar='MODULE',
                        action='store', dest='in_builddir', default = None,
                        help='run command in build dir of the given module'),
            ])

    def execute(self, config, args):
        if not args or args[0] in ('--', '--in-builddir', '--help'):
            options, args = self.parse_args(args)
            return self.run(config, options, args)
        try:
            return os.execlp(args[0], *args)
        except OSError, exc:
            raise FatalError("Unable to execute the command '%s': %s" % (
                    args[0], str(exc)))

    def run(self, config, options, args):
        if options.in_builddir:
            module_set = jhbuild.moduleset.load(config)
            try:
                module_list = [module_set.modules[options.in_builddir]]
            except KeyError, e:
                raise FatalError("A module called '%s' could not be found." % e)

            build = jhbuild.frontends.get_buildscript(config, module_list)
            builddir = module_list[0].get_builddir(build)
            try:
                build.execute(args, cwd=builddir)
            except CommandError, exc:
                if args:
                    raise FatalError("Unable to execute the command '%s'" % args[0])
                else:
                    raise FatalError(str(exc))
        else:
            try:
                os.execlp(args[0], *args)
            except IndexError:
                raise FatalError('No command given')
            except OSError, exc:
                raise FatalError("Unable to execute the command '%s': %s" % (
                        args[0], str(exc)))

register_command(cmd_run)


class cmd_shell(Command):
    """Start a shell under the JHBuild environment"""

    name = 'shell'
    usage_args = ''

    def execute(self, config, args):
        if "--help" in args:
            self.parse_args(args) # This doesn't return
        user_shell = os.environ.get('SHELL', '/bin/sh')
        os.execlp(user_shell, user_shell)

register_command(cmd_shell)


class cmd_list(Command):
    """List the modules that would be built"""

    name = 'list'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-r', '--show-revision',
                        action='store_true', dest='show_rev', default=False,
                        help='show which revision will be built'),
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help='treat the given modules as up to date'),
            ])

    def run(self, config, options, args):
        for item in options.skip:
            config.skip += item.split(',')
        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                                                 config.skip)

        for mod in module_list:
            if options.show_rev:
                rev = mod.get_revision()
                if rev:
                    print '%s (%s)' % (mod.name, rev)
                else:
                    print mod.name
            else:
                print mod.name

register_command(cmd_list)


class cmd_dot(Command):
    """Output a Graphviz dependency graph for one or more modules"""

    name = 'dot'
    usage_args = '[ modules ... ]'

    def run(self, config, options, args):
        module_set = jhbuild.moduleset.load(config)
        if args:
            modules = args
        elif config.modules == 'all':
            modules = None
        else:
            modules = config.modules
        module_set.write_dot(modules)

register_command(cmd_dot)
