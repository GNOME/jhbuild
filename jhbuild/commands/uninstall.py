# jhbuild - a tool to ease building collections of source packages
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

import logging

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import FatalError
from jhbuild.commands import Command, register_command
from jhbuild.modtypes.autotools import AutogenModule
from jhbuild.utils import N_, _


class cmd_uninstall(Command):
    doc = _('Uninstall all modules')

    name = 'uninstall'
    usage_args = N_('[ modules ... ]')

    def run(self, config, options, args, help=None):
        config.set_from_cmdline_options(options)

        module_set = jhbuild.moduleset.load(config)
        module_list = []
        default_repo = jhbuild.moduleset.get_default_repo()
        for modname in args:
            try:
                module = module_set.get_module(modname,
                                               ignore_case = True)
            except KeyError:
                if not default_repo:
                    raise FatalError(_('unknown module %s and no default repository to try an automatic module') % modname)

                logging.info(_('module "%(modname)s" does not exist, created automatically using repository "%(reponame)s"') % \
                         {'modname': modname, 'reponame': default_repo.name})
                module = AutogenModule(modname, default_repo.branch(modname))
                module.config = config

            module_list.append(module)

        if not module_list:
            self.parser.error(_('This command requires a module parameter.'))

        # remove modules that are not marked as installed
        packagedb = module_set.packagedb
        for module in module_list[:]:
            if not packagedb.check(module.name):
                logging.warn(_('Module %(mod)r is not installed') % {'mod': module.name })
                module_list.remove(module)
            else:
                packagedb.uninstall(module.name)


register_command(cmd_uninstall)
