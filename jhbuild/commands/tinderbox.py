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
from jhbuild.commands.base import register_command
import jhbuild.frontends

def do_tinderbox(config, args):
    config.buildscript = 'tinderbox'

    opts, args = getopt.getopt(args, 'o:D:', ['output='])
    for opt, arg in opts:
        if opt in ('-o', '--output'):
            config.tinderbox_outputdir = arg
        elif opt == '-D':
            config.sticky_date = arg

    module_set = jhbuild.moduleset.load(config)
    module_list = module_set.get_module_list(args or config.modules,
                                             config.skip)

    build = jhbuild.frontends.get_buildscript(config, module_list)
    build.build()

register_command('tinderbox', do_tinderbox)
