# jhbuild - a build script for GNOME 2.x
# Copyright (C) 2009  Frederic Peters
#
#   goalreport.py: report GNOME modules status wrt various goals
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
from optparse import make_option
import re

from jhbuild.commands import Command, register_command
from jhbuild.utils import _

from .goalreport import cmd_goalreport, ExcludedModuleException, \
         Check, ShellCheck, DeprecatedSymbolsCheck, FIND_C

class LibBonobo(ShellCheck):
    cmds = (
        FIND_C + " | grep -v .dead.c | xargs grep '^#include <libbonobo'",
        FIND_C + " | grep -v .dead.c | xargs grep '^#include <bonobo'",
        FIND_C + " | grep -v .dead.c | xargs grep 'BonoboObject'",
        FIND_C + " | grep -v .dead.c | xargs grep 'BonoboApplication'",
        "find -name '*.py' | xargs grep 'import .*bonobo'",
    )

class LibGnome(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '^#include <libgnome/' | "\
                        "egrep -v 'gnome-desktop-item.h|gnome-desktop-utils.h'",
                        # gnome-desktop installs stuff under libgnome/
        FIND_C + " | xargs grep '^#include <gnome.h>'",
        "find -name '*.cs' | xargs grep 'Gnome.Url.'", # as 'using ...' is not mandatory
        "find -name '*.cs' | xargs grep 'Gnome.Program.'",
    )

class LibGnomeUi(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '^#include <libgnomeui/' | egrep -v '"\
                    "gnome-rr.h|"\
                    "gnome-rr-config.h|"\
                    "gnome-rr-labeler.h|"\
                    "gnome-desktop-thumbnail.h|"\
                    "gnome-bg-crossfade.h|"\
                    "gnome-bg.h'", # gnome-desktop installs stuff under libgnomeui/
        "find -name '*.py' | xargs grep 'import .*gnome\\.ui'",
    )

class LibGnomeCanvas(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '^#include <libgnomecanvas/'",
        "find -name '*.py' | xargs grep 'import .*gnomecanvas'",
    )

class LibArtLgpl(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '^#include <libart_lgpl/'",
        "find -name '*.cs' | xargs grep '^using Art;'",
    )

class LibGnomeVfs(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '^#include <libgnomevfs/'",
        "find -name '*.py' | xargs grep 'import .*gnomevfs'",
        "find -name '*.cs' | xargs grep '^using Gnome.Vfs'",
        "find -name '*.cs' | xargs grep 'Gnome.Vfs.Initialize'",
    )

class LibGnomePrint(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '^#include <libgnomeprint'",
        "find -name '*.py' | xargs grep 'import .*gnomeprint'",
    )


class Esound(ShellCheck):
    cmd = FIND_C + " | xargs grep '^#include <esd.h>'"

class Orbit(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '^#include <orbit'",
        "find -name '*.py' | xargs grep 'import .*bonobo'",
    )

class LibGlade(ShellCheck):
    excluded_modules = ('libglade',)
    cmds = (
        FIND_C + " | xargs grep '^#include <glade/'",
        FIND_C + " | xargs grep '^#include <libglademm.h>'",
        "find -name '*.py' | xargs grep 'import .*glade'",
        "find -name '*.cs' | xargs grep '^using Glade'",
    )

class GConf(ShellCheck):
    excluded_modules = ('gconf',)
    cmds = (
        FIND_C + " | xargs grep '^#include <gconf/'",
        "find -name '*.py' | xargs grep 'import .*gconf'",
        "find -name '*.cs' | xargs grep '^using GConf'",
    )

class GlibDeprecatedSymbols(DeprecatedSymbolsCheck):
    devhelp_filenames = ('glib.devhelp2', 'gobject.devhelp2', 'gio.devhelp2')
    excluded_modules = ('glib',)

class GtkDeprecatedSymbols(DeprecatedSymbolsCheck):
    devhelp_filenames = ('gdk.devhelp2', 'gdk-pixbuf.devhelp2', 'gtk.devhelp2')
    excluded_modules = ('gtk+',)

class GObjectIntrospectionSupport(Check):
    def run(self):
        pkg_config = False
        gir_file = False
        try:
            for base, dirnames, filenames in os.walk(self.module.branch.srcdir):
                if [x for x in filenames if x.endswith('.pc') or x.endswith('.pc.in')]:
                    pkg_config = True
                if [x for x in filenames if x.endswith('.gir')]:
                    gir_file = True
                if not gir_file and 'Makefile.am' in filenames:
                    # if there is no .gir, we may simply be in an unbuilt module,
                    # let's look up for a .gir target in the Makefile.am
                    makefile_am = open(os.path.join(base, 'Makefile.am')).read()
                    if re.findall(r'^[A-Za-z0-9.\-\$\(\)_]+\.gir:', makefile_am, re.MULTILINE):
                        gir_file = True
                if pkg_config and gir_file:
                    break
        except UnicodeDecodeError:
            raise ExcludedModuleException()

        if not pkg_config:
            raise ExcludedModuleException()

        if gir_file:
            self.status = 'ok'
        else:
            self.status = 'todo'
            self.complexity = 'average'

    def fix_false_positive(self, false_positive):
        if not false_positive:
            return
        if false_positive == 'n/a':
            raise ExcludedModuleException()
        self.status = 'ok'



class cmd_twoninetynine(cmd_goalreport):
    doc = _('Report GNOME modules status wrt 3.0 goals')
    name = 'twoninetynine'

    checks = [LibBonobo, LibGnome, LibGnomeUi, LibGnomeCanvas, LibArtLgpl,
              LibGnomeVfs, LibGnomePrint, Esound, Orbit, LibGlade, GConf,
              GlibDeprecatedSymbols, GtkDeprecatedSymbols,
              GObjectIntrospectionSupport]
    title = '2.99'
    
    page_intro = '''
<p style="font-size: small;">
Disclaimer: Complexities are (mis)calculated arbitrary on the following basis:
1) for libraries low/average/complex are relative to the number of includes
of a library header (&lt;5/&lt;20/&gt;=20); 2) for deprecated symbols thet are
relative to the number of deprecated symbols in use (&lt;5/&lt;20/&gt;=20).
</p>
'''

    
    def __init__(self):
        Command.__init__(self, [
            make_option('-o', '--output', metavar='FILE',
                    action='store', dest='output', default=None),
            make_option('--devhelp-dirname', metavar='DIR',
                    action='store', dest='devhelp_dirname', default=None),
            make_option('--no-cache',
                    action='store_true', dest='nocache', default=False),
            make_option('--all-modules',
                        action='store_true', dest='list_all_modules', default=False),
            ])

    def run(self, config, options, args, help=None):
        options.cache = 'twoninetynine.pck'
        if options.nocache:
            options.cache = None
        options.bugfile = 'http://live.gnome.org/FredericPeters/Bugs299?action=raw'
        options.falsepositivesfile = 'http://live.gnome.org/FredericPeters/FalsePositives299?action=raw'
        return cmd_goalreport.run(self, config, options, args)

register_command(cmd_twoninetynine)
