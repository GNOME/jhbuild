# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
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

import getopt
from jhbuild.errors import UsageError
from jhbuild.commands.base import register_command
import jhbuild.frontends

def do_tinderbox(config, args):
    config.buildscript = 'tinderbox'

    startat = None
    opts, args = getopt.getopt(args, 'acno:s:t:D:',
                               ['autogen', 'clean', 'no-network', 'output=',
                                'skip=', 'start-at='])

    for opt, arg in opts:
        if opt in ('-a', '--autogen'):
            config.alwaysautogen = True
        elif opt in ('-c', '--clean'):
            config.makeclean = True
        elif opt in ('-n', '--no-network'):
            config.nonetwork = True
        elif opt in ('-s', '--skip'):
            config.skip = config.skip + arg.split(',')
        elif opt in ('-t', '--start-at'):
            startat = arg
        elif opt in ('-o', '--output'):
            config.tinderbox_outputdir = arg
        elif opt == '-D':
            config.sticky_date = arg

    if not config.tinderbox_outputdir:
        raise UsageError('output directory for tinderbox build not specified')

    module_set = jhbuild.moduleset.load(config)
    module_list = module_set.get_module_list(args or config.modules,
                                             config.skip)

    # remove modules up to startat
    if startat:
        while module_list and module_list[0].name != startat:
            del module_list[0]
        if not module_list:
            raise FatalError('%s not in module list' % startat)

    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('tinderbox', do_tinderbox)
