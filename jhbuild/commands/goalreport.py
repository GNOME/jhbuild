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

from __future__ import print_function

import os
import re
import socket
import sys
import subprocess
import time
import types
import pickle
import logging
from optparse import make_option
import xml.etree.ElementTree as ET

try:
    import curses
except ImportError:
    curses = None

import jhbuild.moduleset
from jhbuild.errors import CommandError
from jhbuild.commands import Command, register_command
from jhbuild.utils import httpcache, cmds, _, open_text
from jhbuild.modtypes import MetaModule
from jhbuild.utils.compat import TextIO

try:
    t_bold = cmds.get_output(['tput', 'bold'])
except CommandError:
    try:
        t_bold = cmds.get_output(['tput', 'md'])
    except CommandError:
        t_bold = ''

try:
    t_reset = cmds.get_output(['tput', 'sgr0'])
except CommandError:
    try:
        t_reset = cmds.get_output(['tput', 'me'])
    except CommandError:
        t_reset = ''

HTML_AT_TOP = '''<html>
<head>
<title>%(title)s</title>
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

a.has-patch {
    padding-right: 20px;
    background: transparent url(http://bugzilla.gnome.org/images/emblems/P.png) center right no-repeat;
}
</style>
</head>
<body>

'''

class ExcludedModuleException(Exception):
    pass

class CouldNotPerformCheckException(Exception):
    pass


class Check:
    header_note = None

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
        if false_positive == 'n/a':
            raise ExcludedModuleException()
        self.status = 'ok'

    def create_from_args(cls, *args):
        pass
    create_from_args = classmethod(create_from_args)


class ShellCheck(Check):
    cmd = None
    cmds = None

    def run(self):
        if not self.cmds:
            self.cmds = [self.cmd]
        outputs = []
        rc = 0
        for cmd in self.cmds:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True,
                            cwd=self.module.branch.srcdir)
            outputs.append(process.communicate()[0].strip())
            rc = process.wait() or rc
        if rc == 1:
            raise ExcludedModuleException()
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

    def create_from_args(cls, arg):
        new_class = types.ClassType('ShellCheck (%s)' % arg.split('/')[-1],
                (cls,), {'cmd': arg})
        return new_class
    create_from_args = classmethod(create_from_args)


FIND_C = "find -name '*.[ch]' -or -name '*.cpp' -or -name '*.cc'"


class SymbolsCheck(Check):
    def run(self):
        symbol_regex = re.compile(r'[\s\(\){}\+\|&-](%s)[\s\(\){}\+\|&-]' % '|'.join(self.symbols))
        deprecated_and_used = {}
        try:
            for base, dirnames, filenames in os.walk(self.module.branch.srcdir):
                filenames = [x for x in filenames if \
                             os.path.splitext(x)[-1] in ('.c', '.cc', '.cpp', '.h', '.glade')]
                for filename in filenames:
                    for s in symbol_regex.findall(open(os.path.join(base, filename)).read()):
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

    def fix_false_positive(self, false_positive):
        if not false_positive:
            return
        if len(self.symbols) == 1 and false_positive == '-':
            self.bad_symbols = []
            self.compute_status()
            return
        for symbol in false_positive.split(','):
            symbol = symbol.strip()
            if symbol in self.bad_symbols:
                self.bad_symbols.remove(symbol)
        self.compute_status()

    def create_from_args(cls, *args):
        new_class = types.ClassType('SymbolsCheck (%s)' % ', '.join(args),
                (cls,), {'symbols': args})
        return new_class
    create_from_args = classmethod(create_from_args)


class GrepCheck(Check):
    def run(self):
        self.nb_occurences = 0
        try:
            for base, dirnames, filenames in os.walk(self.module.branch.srcdir):
                filenames = [x for x in filenames if \
                             os.path.splitext(x)[-1] in ('.c', '.cc', '.cpp', '.h', '.glade')]
                for filename in filenames:
                    if self.grep in open(os.path.join(base, filename)).read():
                        self.nb_occurences += 1
        except UnicodeDecodeError:
            raise ExcludedModuleException()
        self.compute_status()

    def compute_status(self):
        if self.nb_occurences == 0:
            self.status = 'ok'
        elif self.nb_occurences <= 5:
            self.status = 'todo'
            self.complexity = 'low'
        elif self.nb_occurences <= 20:
            self.status = 'todo'
            self.complexity = 'average'
        else:
            self.status = 'todo'
            self.complexity = 'complex'
        if self.status == 'todo':
            self.result_comment = self.nb_occurences
        else:
            self.result_comment = None

    def create_from_args(cls, *args):
        new_class = types.ClassType('GrepCheck (%s)' % ', '.join(args),
                (cls,), {'grep': args[0]})
        return new_class
    create_from_args = classmethod(create_from_args)


class FilenamesCheck(Check):
    def run(self):
        for base, dirnames, filenames in os.walk(self.module.branch.srcdir):
            for f in self.filenames:
                if f in filenames:
                    self.found = True
                    self.compute_status()
                    return
        self.found = False
        self.compute_status()

    def compute_status(self):
        self.status = 'ok'
        if self.found:
            self.status = 'todo'
            self.complexity = 'average'

    def create_from_args(cls, *args):
        new_class = types.ClassType('FilenamesCheck (%s)' % ', '.join(args),
                (cls,), {'filenames': args})
        return new_class
    create_from_args = classmethod(create_from_args)


class DeprecatedSymbolsCheck(SymbolsCheck):
    cached_symbols = {}

    @property
    def symbols(self):
        if self.cached_symbols.get(self.devhelp_filenames):
            return self.cached_symbols.get(self.devhelp_filenames)
        symbols = []
        for devhelp_filename in self.devhelp_filenames:
            try:
                devhelp_path = os.path.join(self.config.devhelp_dirname, devhelp_filename)
                tree = ET.parse(devhelp_path)
            except Exception:
                raise CouldNotPerformCheckException()
            for keyword in tree.findall('//{http://www.devhelp.net/book}keyword'):
                if 'deprecated' not in keyword.attrib:
                    continue
                name = keyword.attrib.get('name').replace('enum ', '').replace('()', '').strip()
                symbols.append(name)
        DeprecatedSymbolsCheck.cached_symbols[self.devhelp_filenames] = symbols
        return symbols


class cmd_goalreport(Command):
    doc = _('Report GNOME modules status wrt various goals')
    name = 'goalreport'

    checks = None
    page_intro = None
    title = 'GNOME Goal Report'
    
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
            make_option('--cache', metavar='FILE',
                    action='store', dest='cache', default=None),
            make_option('--all-modules',
                        action='store_true', dest='list_all_modules', default=False),
            make_option('--check', metavar='CHECK',
                        action='append', dest='checks', default=[],
                        help=_('check to perform')),
            ])

    def load_checks_from_options(self, checks):
        self.checks = []
        for check_option in checks:
            check_class_name, args = check_option.split(':', 1)
            args = args.split(',')
            check_base_class = globals().get(check_class_name)
            check = check_base_class.create_from_args(*args)
            self.checks.append(check)


    def run(self, config, options, args, help=None):
        if options.output:
            output = TextIO()
            global curses
            if curses and config.progress_bar:
                try:
                    curses.setupterm()
                except Exception:
                    curses = None
        else:
            output = sys.stdout

        if not self.checks:
            self.load_checks_from_options(options.checks)

        self.load_bugs(options.bugfile)
        self.load_false_positives(options.falsepositivesfile)

        config.devhelp_dirname = options.devhelp_dirname
        config.partial_build = False

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
        if options.cache:
            try:
                results = pickle.load(open(os.path.join(cachedir, options.cache), "rb"))
            except Exception:
                pass

        self.repeat_row_header = 0
        if len(self.checks) > 4:
            self.repeat_row_header = 1

        for module_num, mod in enumerate(self.module_list):
            if mod.type in ('meta', 'tarball'):
                continue
            if not mod.branch or mod.branch.repository.__class__.__name__ not in (
                    'SubversionRepository', 'GitRepository'):
                if not mod.moduleset_name.startswith('gnome-external-deps'):
                    continue

            if not os.path.exists(mod.branch.srcdir):
                continue

            tree_id = mod.branch.tree_id()
            valid_cache = (tree_id and results.get(mod.name, {}).get('tree-id') == tree_id)

            if mod.name not in results:
                results[mod.name] = {
                    'results': {}
                }
            results[mod.name]['tree-id'] = tree_id
            r = results[mod.name]['results']
            for check in self.checks:
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
        if options.cache:
            pickle.dump(results, open(os.path.join(cachedir, options.cache), 'wb'))

        print(HTML_AT_TOP % {'title': self.title}, file=output)
        if self.page_intro:
            print(self.page_intro, file=output)
        print('<table>', file=output)
        print('<thead>', file=output)
        print('<tr><td></td>', file=output)
        for check in self.checks:
            print('<th>%s</th>' % check.__name__, file=output)
        print('<td></td></tr>', file=output)
        if [x for x in self.checks if x.header_note]:
            print('<tr><td></td>', file=output)
            for check in self.checks:
                print('<td>%s</td>' % (check.header_note or ''), file=output)
            print('</tr>', file=output)
        print('</thead>', file=output)
        print('<tbody>', file=output)

        processed_modules = {'gnome-common': True}
        suites = []
        for module_key, module in module_set.modules.items():
            if not isinstance(module_set.get_module(module_key), MetaModule):
                continue
            if module_key.endswith('upcoming-deprecations'):
                # mark deprecated modules as processed, so they don't show in "Others"
                try:
                    metamodule = module_set.get_module(module_key)
                except KeyError:
                    continue
                for module_name in metamodule.dependencies:
                    processed_modules[module_name] = True
            else:
                suites.append([module_key, module_key.replace('meta-', '')])

        not_other_module_names = []
        for suite_key, suite_label in suites:
            metamodule = module_set.get_module(suite_key)
            module_names = [x for x in metamodule.dependencies if x in results]
            if not module_names:
                continue
            print('<tr><td class="heading" colspan="%d">%s</td></tr>' % (
                    1+len(self.checks)+self.repeat_row_header, suite_label), file=output)
            for module_name in module_names:
                if module_name in not_other_module_names:
                    continue
                r = results[module_name].get('results')
                print(self.get_mod_line(module_name, r), file=output)
                processed_modules[module_name] = True
            not_other_module_names.extend(module_names)

        external_deps = [x for x in results.keys() if \
                         x in [y.name for y in self.module_list] and \
                         x not in processed_modules and \
                         module_set.get_module(x).moduleset_name.startswith('gnome-external-deps')]
        if external_deps:
            print('<tr><td class="heading" colspan="%d">%s</td></tr>' % (
                    1+len(self.checks)+self.repeat_row_header, 'External Dependencies'), file=output)
            for module_name in sorted(external_deps):
                if module_name not in results:
                    continue
                r = results[module_name].get('results')
                try:
                    version = module_set.get_module(module_name).branch.version
                except Exception:
                    version = None
                print(self.get_mod_line(module_name, r, version_number=version), file=output)

        other_module_names = [x for x in results.keys() if \
                              x not in processed_modules and x not in external_deps]
        if other_module_names:
            print('<tr><td class="heading" colspan="%d">%s</td></tr>' % (
                    1+len(self.checks)+self.repeat_row_header, 'Others'), file=output)
            for module_name in sorted(other_module_names):
                if module_name not in results:
                    continue
                r = results[module_name].get('results')
                print(self.get_mod_line(module_name, r), file=output)
        print('</tbody>', file=output)
        print('<tfoot>', file=output)

        print('<tr><td></td>', file=output)
        for check in self.checks:
            print('<th>%s</th>' % check.__name__, file=output)
        print('<td></td></tr>', file=output)

        print(self.get_stat_line(results, not_other_module_names), file=output)
        print('</tfoot>', file=output)
        print('</table>', file=output)

        if (options.bugfile and options.bugfile.startswith('http://')) or \
                (options.falsepositivesfile and options.falsepositivesfile.startswith('http://')):
            print('<div id="data">', file=output)
            print('<p>The following data sources are used:</p>', file=output)
            print('<ul>', file=output)
            if options.bugfile.startswith('http://'):
                print('  <li><a href="%s">Bugs</a></li>' % options.bugfile, file=output)
            if options.falsepositivesfile.startswith('http://'):
                print('  <li><a href="%s">False positives</a></li>' % options.falsepositivesfile, file=output)
            print('</ul>', file=output)
            print('</div>', file=output)

        print('<div id="footer">', file=output)
        print('Generated:', time.strftime('%Y-%m-%d %H:%M:%S %z'), file=output)
        print('on ', socket.getfqdn(), file=output)
        print('</div>', file=output)

        print('</body>', file=output)
        print('</html>', file=output)

        if output != sys.stdout:
            open_text(options.output, 'w').write(output.getvalue())

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
        for check in self.checks:
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
                bug_classes = []
                if self.bug_status.get(self.bugs[k], {}).get('resolution'):
                    bug_classes.append('bug-closed')
                    if label:
                        bug_classes.append('warn-bug-status')

                if label and self.bug_status.get(self.bugs[k], {}).get('patch'):
                    bug_classes.append('has-patch')

                bug_class = ''
                if bug_classes:
                    bug_class = ' class="%s"' % ' '.join(bug_classes)
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
        if self.repeat_row_header:
            s.append('<th>%s</th>' % module_name)
        s.append('</tr>')
        return '\n'.join(s)

    def get_stat_line(self, results, module_names):
        s = []
        s.append('<tr>')
        s.append('<td>Stats<br/>(excluding "Others")</td>')
        for check in self.checks:
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
                if k not in self.bugs or check.__name__ not in results[module_name]['results']:
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
        #
        # Alternatively, the $(checkname) can be replaced by a column number,
        # like: evolution/col:2 543234
        #
        # also, if there is only a single check, the /$(checkname) part
        # can be skipped.
        self.bugs = {}
        if not filename:
            return
        if filename.startswith('http://'):
            if filename.startswith('http://live.gnome.org') and not filename.endswith('?action=raw'):
                filename += '?action=raw'
            try:
                filename = httpcache.load(filename, age=0)
            except Exception as e:
                logging.warning('could not download %s: %s' % (filename, e))
                return
        for line in open(filename):
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            part, bugnumber = line.split()
            if '/' in part:
                module_name, check = part.split('/')
                if check.startswith('col:'):
                    check = self.checks[int(check[4:])-1].__name__
            elif len(self.checks) == 1:
                module_name = part
                check = self.checks[0].__name__
            else:
                continue
            self.bugs[(module_name, check)] = bugnumber

        self.bug_status = {}

        bug_status = httpcache.load(
                'http://bugzilla.gnome.org/show_bug.cgi?%s&'
                'ctype=xml&field=bug_id&field=bug_status&field=emblems&'
                'field=resolution' % '&'.join(['id=' + x for x in self.bugs.values() if x.isdigit()]),
                age=0)
        tree = ET.parse(bug_status)
        for bug in tree.findall('bug'):
            bug_id = bug.find('bug_id').text
            bug_resolved = (bug.find('resolution') is not None)
            bug_has_patch = (bug.find('emblems') is not None and 'P' in bug.find('emblems').text)
            self.bug_status[bug_id] = {
                'resolution': bug_resolved,
                'patch': bug_has_patch,
                }

    def load_false_positives(self, filename):
        self.false_positives = {}
        if not filename:
            return
        if filename.startswith('http://'):
            if filename.startswith('http://live.gnome.org') and not filename.endswith('?action=raw'):
                filename += '?action=raw'
            try:
                filename = httpcache.load(filename, age=0)
            except Exception as e:
                logging.warning('could not download %s: %s' % (filename, e))
                return
        for line in open(filename):
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            if ' ' in line:
                part, extra = line.split(' ', 1)
            else:
                part, extra = line, '-'

            if '/' in part:
                module_name, check = part.split('/')
                if check.startswith('col:'):
                    check = self.checks[int(check[4:])-1].__name__
            elif len(self.checks) == 1:
                module_name = part
                check = self.checks[0].__name__
            else:
                continue

            self.false_positives[(module_name, check)] = extra


    def display_status_line(self, progress, module_num, message):
        if not curses:
            return
        columns = curses.tigetnum('cols')
        width = columns // 2
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
