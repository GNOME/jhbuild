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
import re
import sys
import subprocess
import cPickle
from optparse import make_option
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import elementtree.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

try:
    import curses
except ImportError:
    curses = None

from jhbuild.errors import FatalError
import jhbuild.moduleset
from jhbuild.commands import Command, register_command
from jhbuild.utils import httpcache


try: t_bold = cmds.get_output(['tput', 'bold'])
except: t_bold = ''
try: t_reset = cmds.get_output(['tput', 'sgr0'])
except: t_reset = ''


HTML_AT_TOP = '''<html>
<head>
<title>2.99</title>
<style type="text/css">
body {
    font-family: sans-serif;
}
tfoot th, thead th {
    font-weight: normal;
}
td.dunno { background: #aaa; }
td.todo-low { background: #fce94f; }
td.todo-average { background: #fcaf3e; }
td.todo-complex { background: #ef2929; }
td.ok { background: #8ae234; }
td.heading {
    text-align: center;
    background: #555753;
    color: white;
    font-weight: bold;
}
tbody th {
    background: #d3d7cf;
    text-align: left;
}
tbody td {
    text-align: center;
}
tfoot td {
    padding-top: 1em;
    vertical-align: top;
}

tbody tr:hover th {
    background: #2e3436;
    color: #d3d7cf;
}

a.bug-closed {
    text-decoration: line-through;
}

a.warn-bug-status::after {
    content: " \\26A0";
    color: #ef2929;
    font-weight: bold;
}

</style>
</head>
<body>

<p style="font-size: small;">
Disclaimer: Complexities are (mis)calculated arbitrary on the following basis:
1) for libraries low/average/complex are relative to the number of includes
of a library header (&lt;5/&lt;20/&gt;=20); 2) for deprecated symbols thet are
relative to the number of deprecated symbols in use (&lt;5/&lt;20/&gt;=20).
</p>

'''

class ExcludedModuleException(Exception):
    pass

class CouldNotPerformCheckException(Exception):
    pass


class Check:
    complexity = 'average'
    status = 'dunno'
    result_comment = None

    excluded_modules = []

    def __init__(self, config, module):
        if module.name in (self.excluded_modules or []):
            raise ExcludedModuleException()
        self.config = config
        self.module = module

    def fix_false_positive(self, false_positive):
        if not false_positive:
            return
        self.status = 'ok'


class ShellCheck(Check):
    cmd = None
    cmds = None

    def run(self):
        if not self.cmds:
            self.cmds = [self.cmd]
        outputs = []
        for cmd in self.cmds:
            outputs.append(subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True,
                    cwd=self.module.branch.srcdir).communicate()[0].strip())
        nb_lines = sum([len(x.splitlines()) for x in outputs])
        if nb_lines == 0:
            self.status = 'ok'
        elif nb_lines <= 5:
            self.status = 'todo'
            self.complexity = 'low'
        elif nb_lines <= 20:
            self.status = 'todo'
            self.complexity = 'average'
        else:
            self.status = 'todo'
            self.complexity = 'complex'

FIND_C = "find -name '*.[ch]' -or -name '*.cpp' -or -name '*.cc'"

class LibBonobo(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '#include <libbonobo'",
        FIND_C + " | xargs grep '#include <bonobo'",
        FIND_C + " | xargs grep 'BonoboObject'",
        FIND_C + " | xargs grep 'BonoboApplication'",
        "find -name '*.py' | xargs grep 'import .*bonobo'",
    )

class LibGnome(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '#include <libgnome/' | "\
                        "egrep -v 'gnome-desktop-item.h|gnome-desktop-utils.h'",
                        # gnome-desktop installs stuff under libgnome/
        FIND_C + " | xargs grep '#include <gnome.h>'",
        "find -name '*.cs' | xargs grep 'Gnome.Url.'", # as 'using ...' is not mandatory
    )

class LibGnomeUi(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '#include <libgnomeui/' | egrep -v '"\
                    "gnome-rr.h|"\
                    "gnome-rr-config.h|"\
                    "gnome-desktop-thumbnail.h|"\
                    "gnome-bg-crossfade.h|"\
                    "gnome-bg.h'", # gnome-desktop installs stuff under libgnomeui/
        "find -name '*.py' | xargs grep 'import .*gnome\.ui'",
    )

class LibGnomeCanvas(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '#include <libgnomecanvas/'",
        "find -name '*.py' | xargs grep 'import .*gnomecanvas'",
    )

class LibArtLgpl(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '#include <libart_lgpl/'",
        "find -name '*.cs' | xargs grep '^using Art;'",
    )

class LibGnomeVfs(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '#include <libgnomevfs/'",
        "find -name '*.py' | xargs grep 'import .*gnomevfs'",
        "find -name '*.cs' | xargs grep '^using Gnome.Vfs'",
    )

class LibGnomePrint(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '#include <libgnomeprint'",
        "find -name '*.py' | xargs grep 'import .*gnomeprint'",
    )


class Esound(ShellCheck):
    cmd = FIND_C + " | xargs grep '#include <esd.h>'"

class Orbit(ShellCheck):
    cmds = (
        FIND_C + " | xargs grep '#include <orbit'",
        "find -name '*.py' | xargs grep 'import .*bonobo'",
    )

class LibGlade(ShellCheck):
    excluded_modules = ('libglade',)
    cmds = (
        FIND_C + " | xargs grep '#include <glade/'",
        "find -name '*.py' | xargs grep 'import .*glade'",
        "find -name '*.cs' | xargs grep '^using Glade'",
    )

class GConf(ShellCheck):
    excluded_modules = ('gconf',)
    cmds = (
        FIND_C + " | xargs grep '#include <gconf/'",
        "find -name '*.py' | xargs grep 'import .*gconf'",
        "find -name '*.cs' | xargs grep '^using GConf'",
    )


class DeprecatedSymbolsCheck(Check):
    cached_symbols = {}

    def run(self):
        symbols = self.load_deprecated_symbols()
        symbol_regex = re.compile(r'[\s\(\){}\+\|&-](%s)[\s\(\){}\+\|&-]' % '|'.join(symbols))
        deprecated_and_used = {}
        try:
            for base, dirnames, filenames in os.walk(self.module.branch.srcdir):
                filenames = [x for x in filenames if \
                             os.path.splitext(x)[-1] in ('.c', '.cc', '.cpp', '.h', '.glade')]
                for filename in filenames:
                    for s in symbol_regex.findall(file(os.path.join(base, filename)).read()):
                        deprecated_and_used[s] = True
        except UnicodeDecodeError:
            raise ExcludedModuleException()
        self.bad_symbols = deprecated_and_used.keys()
        self.compute_status()

    def compute_status(self):
        nb_symbols = len(self.bad_symbols)
        if nb_symbols == 0:
            self.status = 'ok'
        elif nb_symbols <= 5:
            self.status = 'todo'
            self.complexity = 'low'
        elif nb_symbols <= 20:
            self.status = 'todo'
            self.complexity = 'average'
        else:
            self.status = 'todo'
            self.complexity = 'complex'
        if self.status == 'todo':
            self.result_comment = ', '.join(sorted(self.bad_symbols))
        else:
            self.result_comment = None

    def load_deprecated_symbols(self):
        if self.cached_symbols.get(self.devhelp_filenames):
            return self.cached_symbols.get(self.devhelp_filenames)
        symbols = []
        for devhelp_filename in self.devhelp_filenames:
            try:
                devhelp_path = os.path.join(self.config.devhelp_dirname, devhelp_filename)
                tree = ET.parse(devhelp_path)
            except:
                raise CouldNotPerformCheckException()
            for keyword in tree.findall('//{http://www.devhelp.net/book}keyword'):
                if not keyword.attrib.has_key('deprecated'):
                    continue
                name = keyword.attrib.get('name').replace('enum ', '').replace('()', '').strip()
                symbols.append(name)
        DeprecatedSymbolsCheck.cached_symbols[self.devhelp_filenames] = symbols
        return symbols

    def fix_false_positive(self, false_positive):
        if not false_positive:
            return
        for symbol in false_positive.split(','):
	    symbol = symbol.strip()
            if symbol in self.bad_symbols:
                self.bad_symbols.remove(symbol)
        self.compute_status()


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
                    makefile_am = file(os.path.join(base, 'Makefile.am')).read()
                    if re.findall(r'^[A-Za-z0-9.\-]+\.gir:', makefile_am, re.MULTILINE):
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


checks = [LibBonobo, LibGnome, LibGnomeUi, LibGnomeCanvas, LibArtLgpl,
          LibGnomeVfs, LibGnomePrint, Esound, Orbit, LibGlade, GConf,
          GlibDeprecatedSymbols, GtkDeprecatedSymbols,
          GObjectIntrospectionSupport]

class cmd_goalreport(Command):
    doc = _('Report GNOME modules status wrt various goals')
    name = 'goalreport'
    
    def __init__(self):
        Command.__init__(self, [
            make_option('-o', '--output', metavar='FILE',
                    action='store', dest='output', default=None),
            make_option('--bugs-file', metavar='BUGFILE',
                    action='store', dest='bugfile', default=None),
            make_option('--false-positives-file', metavar='FILE',
                    action='store', dest='falsepositivesfile', default=None),
            make_option('--devhelp-dirname', metavar='DIR',
                    action='store', dest='devhelp_dirname', default=None),
            make_option('--no-cache',
                    action='store_true', dest='nocache', default=False),
            make_option('--all-modules',
                        action='store_true', dest='list_all_modules', default=False),
            ])

    def run(self, config, options, args):
        if options.output:
            output = StringIO()
            global curses
            if curses and config.progress_bar:
                try:
                    curses.setupterm()
                except:
                    curses = None
        else:
            output = sys.stdout

        self.load_bugs(options.bugfile)
        self.load_false_positives(options.falsepositivesfile)

        config.devhelp_dirname = options.devhelp_dirname

        module_set = jhbuild.moduleset.load(config)
        if options.list_all_modules:
            self.module_list = module_set.modules.values()
        else:
            self.module_list = module_set.get_module_list(args or config.modules, config.skip)

        results = {}
        try:
            cachedir = os.path.join(os.environ['XDG_CACHE_HOME'], 'jhbuild')
        except KeyError:
            cachedir = os.path.join(os.environ['HOME'], '.cache','jhbuild')
        if not options.nocache:
            try:
                results = cPickle.load(file(os.path.join(cachedir, 'twoninetynine.pck')))
            except:
                pass

        for module_num, mod in enumerate(self.module_list):
            if mod.type in ('meta', 'tarball'):
                continue
            if not mod.branch or not mod.branch.repository.__class__.__name__ in (
                    'SubversionRepository', 'GitRepository'):
                if not mod.moduleset_name.startswith('gnome-external-deps'):
                    continue

            if not os.path.exists(mod.branch.srcdir):
                continue

            tree_id = mod.branch.tree_id()
            valid_cache = (tree_id and results.get(mod.name, {}).get('tree-id') == tree_id)

            if not mod.name in results:
                results[mod.name] = {
                    'results': {}
                }
            results[mod.name]['tree-id'] = tree_id
            r = results[mod.name]['results']
            for check in checks:
                if valid_cache and check.__name__ in r:
                    continue
                try:
                    c = check(config, mod)
                except ExcludedModuleException:
                    continue

                if output != sys.stdout and config.progress_bar:
                    progress_percent = 1.0 * (module_num-1) / len(self.module_list)
                    msg = '%s: %s' % (mod.name, check.__name__)
                    self.display_status_line(progress_percent, module_num, msg)

                try:
                    c.run()
                except CouldNotPerformCheckException:
                    continue
                except ExcludedModuleException:
                    continue

                try:
                    c.fix_false_positive(self.false_positives.get((mod.name, check.__name__)))
                except ExcludedModuleException:
                    continue

                r[check.__name__] = [c.status, c.complexity, c.result_comment]

        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        cPickle.dump(results, file(os.path.join(cachedir, 'twoninetynine.pck'), 'w'))

        print >> output, HTML_AT_TOP
        print >> output, '<table>'
        print >> output, '<thead>'
        print >> output, '<tr><td></td>'
        for check in checks:
            print >> output, '<th>%s</th>' % check.__name__
        print >> output, '<td></td></tr>'
        print >> output, '</thead>'
        print >> output, '<tbody>'

        suites = [
            ('meta-gnome-desktop-suite', 'Desktop'),
            ('meta-gnome-devel-platform', 'Platform'),
            ('meta-gnome-admin', 'Admin'),
            ('meta-gnome-devtools-suite', 'Development Tools'),
            ('meta-gnome-bindings-c++', 'Bindings (C++)'),
            ('meta-gnome-bindings-python', 'Bindings (Python)'),
            ('meta-gnome-bindings-mono', 'Bindings (Mono)'),
        ]

        processed_modules = {'gnome-common': True}

        # mark deprecated modules as processed, so they don't show in "Others"
        for meta_key in ('meta-gnome-devel-platform-upcoming-deprecations',
                         'meta-gnome-desktop-upcoming-deprecations'):
            metamodule = module_set.get_module(meta_key)
            for module_name in metamodule.dependencies:
                processed_modules[module_name] = True

        not_other_module_names = []
        for suite_key, suite_label in suites:
            metamodule = module_set.get_module(suite_key)
            module_names = [x for x in metamodule.dependencies if x in results]
            if not module_names:
                continue
            print >> output, '<tr><td class="heading" colspan="%d">%s</td></tr>' % (
                    2+len(checks), suite_label)
            for module_name in module_names:
                r = results[module_name].get('results')
                print >> output, self.get_mod_line(module_name, r)
                processed_modules[module_name] = True
            not_other_module_names.extend(module_names)

        external_deps = [x for x in results.keys() if \
                         not x in processed_modules and \
                         module_set.get_module(x).moduleset_name.startswith('gnome-external-deps')]
        if external_deps:
            print >> output, '<tr><td class="heading" colspan="%d">%s</td></tr>' % (
                    2+len(checks), 'External Dependencies')
            for module_name in sorted(external_deps):
                if not module_name in results:
                    continue
                r = results[module_name].get('results')
                try:
                    version = module_set.get_module(module_name).branch.version
                except:
                    version = None
                print >> output, self.get_mod_line(module_name, r, version_number=version)

        other_module_names = [x for x in results.keys() if \
                              not x in processed_modules and not x in external_deps]
        if other_module_names:
            print >> output, '<tr><td class="heading" colspan="%d">%s</td></tr>' % (
                    2+len(checks), 'Others')
            for module_name in sorted(other_module_names):
                if not module_name in results:
                    continue
                r = results[module_name].get('results')
                print >> output, self.get_mod_line(module_name, r)
        print >> output, '</tbody>'
        print >> output, '<tfoot>'

        print >> output, '<tr><td></td>'
        for check in checks:
            print >> output, '<th>%s</th>' % check.__name__
        print >> output, '<td></td></tr>'

        print >> output, self.get_stat_line(results, not_other_module_names)
        print >> output, '</tfoot>'
        print >> output, '</table>'

        print >> output, '</body>'
        print >> output, '</html>'

        if output != sys.stdout:
            file(options.output, 'w').write(output.getvalue())

        if output != sys.stdout and config.progress_bar:
            sys.stdout.write('\n')
            sys.stdout.flush()


    def get_mod_line(self, module_name, r, version_number=None):
        s = []
        s.append('<tr>')
        if version_number:
            s.append('<th>%s&nbsp;(%s)</th>' % (module_name, version_number))
        else:
            s.append('<th>%s</th>' % module_name)
        for check in checks:
            ri = r.get(check.__name__)
            if not ri:
                classname = 'n-a'
                label = 'n/a'
                comment = ''
            else:
                classname = ri[0]
                if classname == 'todo':
                    classname += '-' + ri[1]
                    label = ri[1]
                else:
                    label = ri[0]
                comment = ri[2] or ''
                if label == 'ok':
                    label = ''
            s.append('<td class="%s" title="%s">' % (classname, comment))
            k = (module_name, check.__name__)
            if k in self.bugs:
                bug_class = ''
                if self.bug_status.get(self.bugs[k]):
                    if label == '':
                        bug_class = ' class="bug-closed"'
                    else:
                        bug_class = ' class="bug-closed warn-bug-status"'
                if self.bugs[k].isdigit():
                    s.append('<a href="http://bugzilla.gnome.org/show_bug.cgi?id=%s"%s>' % (
                                self.bugs[k], bug_class))
                else:
                    s.append('<a href="%s"%s>' % (self.bugs[k], bug_class))
                if label == '':
                    label = 'done'
            s.append(label)
            if k in self.bugs:
                s.append('</a>')
            s.append('</td>')
        s.append('<th>%s</th>' % module_name)
        s.append('</tr>')
        return '\n'.join(s)

    def get_stat_line(self, results, module_names):
        s = []
        s.append('<tr>')
        s.append('<td>Stats<br/>(excluding "Others")</td>')
        for check in checks:
            s.append('<td>')
            for complexity in ('low', 'average', 'complex'):
                nb_modules = len([x for x in module_names if \
                        results[x].get('results') and 
                        results[x]['results'].get(check.__name__) and
                        results[x]['results'][check.__name__][0] == 'todo' and
                        results[x]['results'][check.__name__][1] == complexity])
                s.append('%s:&nbsp;%s' % (complexity, nb_modules))
                s.append('<br/>')
            nb_with_bugs = 0
            nb_with_bugs_done = 0
            for module_name in module_names:
                k = (module_name, check.__name__)
                if not k in self.bugs or not check.__name__ in results[module_name]['results']:
                    continue
                nb_with_bugs += 1
                if results[module_name]['results'][check.__name__][0] == 'ok':
                    nb_with_bugs_done += 1
            if nb_with_bugs:
                s.append('<br/>')
                s.append('fixed:&nbsp;%d%%' % (100.*nb_with_bugs_done/nb_with_bugs))
            s.append('</td>')
        s.append('<td></td>')
        s.append('</tr>')
        return '\n'.join(s)

    def load_bugs(self, filename):
        # Bug file format:
        #  $(module)/$(checkname) $(bugnumber)
        # Sample bug file:
        #  evolution/LibGnomeCanvas 571742
        if not filename:
            filename = 'http://live.gnome.org/FredericPeters/Bugs299?action=raw'
        if filename.startswith('http://'):
            try:
                filename = httpcache.load(filename, age=0)
            except Exception, e:
                raise FatalError(_('could not download %s: %s') % (filename, e))
        self.bugs = {}
        for line in file(filename):
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            part, bugnumber = line.split()
            module_name, check = part.split('/')
            self.bugs[(module_name, check)] = bugnumber

        self.bug_status = {}

        bug_status = httpcache.load(
                'http://bugzilla.gnome.org/show_bug.cgi?%s&'
                'ctype=xml&field=bug_id&field=bug_status&'
                'field=resolution' % '&'.join(['id=' + x for x in self.bugs.values() if x.isdigit()]))
        tree = ET.parse(bug_status)
        for bug in tree.findall('bug'):
            bug_id = bug.find('bug_id').text
            bug_resolved = (bug.find('resolution') is not None)
            self.bug_status[bug_id] = bug_resolved

    def load_false_positives(self, filename):
        if not filename:
            filename = 'http://live.gnome.org/FredericPeters/FalsePositives299?action=raw'
        if filename.startswith('http://'):
            try:
                filename = httpcache.load(filename, age=0)
            except Exception, e:
                raise FatalError(_('could not download %s: %s') % (filename, e))
        self.false_positives = {}
        for line in file(filename):
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            if ' ' in line:
                part, extra = line.split(' ', 1)
            else:
                part, extra = line, '-'
            module_name, check = part.split('/')
            self.false_positives[(module_name, check)] = extra


    def display_status_line(self, progress, module_num, message):
        if not curses:
            return
        columns = curses.tigetnum('cols')
        width = columns / 2
        num_hashes = int(round(progress * width))
        progress_bar = '[' + (num_hashes * '=') + ((width - num_hashes) * '-') + ']'

        module_no_digits = len(str(len(self.module_list)))
        format_str = '%%%dd' % module_no_digits
        module_pos = '[' + format_str % (module_num+1) + '/' + format_str % len(self.module_list) + ']'

        output = '%s %s %s%s%s' % (progress_bar, module_pos, t_bold, message, t_reset)
        if len(output) > columns:
            output = output[:columns]
        else:
            output += ' ' * (columns-len(output))

        sys.stdout.write(output + '\r')
        sys.stdout.flush()


register_command(cmd_goalreport)
