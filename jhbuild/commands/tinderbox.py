# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   tinderbox.py: non-interactive build that generates a report
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

from optparse import make_option

from jhbuild.errors import UsageError, FatalError
from jhbuild.commands import Command, BuildCommand, register_command
import jhbuild.frontends
from jhbuild.utils import N_, _


class cmd_tinderbox(BuildCommand):
    doc = N_('Build modules non-interactively and store build logs')

    name = 'tinderbox'
    usage_args = N_('[ options ... ] [ modules ... ]')

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='autogen', default=False,
                        help=_('always run autogen.sh')),
            make_option('', '--distclean',
                        action='store_true', dest='distclean', default=False,
                        help=_('completely clean source tree')),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help=_('run make clean before make')),
            make_option('--check',
                        action='store_true', dest='check', default=False,
                        help=_('run make check after building')),
            make_option('-n', '--no-network',
                        action='store_true', dest='nonetwork', default=False,
                        help=_('skip version control update')),
            make_option('-o', '--output', metavar='DIR',
                        action='store', dest='outputdir', default=None,
                        help=_('directory to store build logs in')),
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help=_('treat the given modules as up to date')),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help=_('start building at the given module')),
            make_option('-D', metavar='DATE-SPEC',
                        action='store', dest='sticky_date', default=None,
                        help=_('set a sticky date when checking out modules')),
            make_option('-C', '--try-checkout',
                        action='store_true', dest='trycheckout', default=False,
                        help=_('try to force checkout and autogen on failure')),
            make_option('-N', '--no-poison',
                        action='store_true', dest='nopoison', default=False,
                        help=_("don't poison modules on failure")),
            make_option('-f', '--force',
                        action='store_true', dest='force_policy', default=False,
                        help=_('build even if policy says not to')),
            make_option('--nodeps',
                        action='store_false', dest='check_sysdeps', default=None,
                        help=_('ignore missing system dependencies'))
            ])

    def run(self, config, options, args, help=None):
        config.set_from_cmdline_options(options)
        config.buildscript = 'tinderbox'

        if options.outputdir is not None:
            config.tinderbox_outputdir = options.outputdir

        if not config.tinderbox_outputdir:
            raise UsageError(_('output directory for tinderbox build not specified'))

        module_set = jhbuild.moduleset.load(config)
        full_module_list = module_set.get_full_module_list(
            args or config.modules, config.skip)
        module_list = module_set.remove_system_modules(full_module_list)

        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError(_('%s not in module list') % options.startat)

        if config.check_sysdeps:
            module_state = module_set.get_module_state(full_module_list)
            if not self.required_system_dependencies_installed(module_state):
                self.print_system_dependencies(module_state)
                raise FatalError(_('Required system dependencies not installed.'
                                   ' Install using the command %(cmd)s or to '
                                   'ignore system dependencies use command-line'
                                   ' option %(opt)s' \
                                   % {'cmd' : "'jhbuild sysdeps --install'",
                                      'opt' : '--nodeps'}))

        build = jhbuild.frontends.get_buildscript(config, module_list, module_set=module_set)
        return build.build()

register_command(cmd_tinderbox)
