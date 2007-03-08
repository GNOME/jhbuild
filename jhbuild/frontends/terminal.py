# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
# Copyright (C) 2003-2004  Seth Nickell
#
#   terminal.py: build logic for a terminal interface
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

import sys
import os
import signal
import subprocess

from jhbuild.frontends import buildscript
from jhbuild.utils import cmds
from jhbuild.utils import trayicon
from jhbuild.utils import notify
from jhbuild.errors import CommandError

term = os.environ.get('TERM', '')
is_xterm = term.find('xterm') >= 0 or term == 'rxvt'
del term

try: t_bold = cmds.get_output(['tput', 'bold'])
except: t_bold = ''
try: t_reset = cmds.get_output(['tput', 'sgr0'])
except: t_reset = ''
t_colour = [''] * 16
try:
    for i in range(8):
        t_colour[i] = cmds.get_output(['tput', 'setf', '%d' % i])
        t_colour[i+8] = t_bold + t_colour[i]
except: pass

user_shell = os.environ.get('SHELL', '/bin/sh')

# tray icon stuff ...
icondir = os.path.join(os.path.dirname(__file__), 'icons')
phase_map = {
    'checkout':       'checkout.png',
    'force_checkout': 'checkout.png',
    'download':       'checkout.png',
    'unpack':         'checkout.png',
    'patch':          'checkout.png',
    'configure':      'configure.png',
    #'clean':          'clean.png',
    'build':          'build.png',
    #'check':          'check.png',
    'install':        'install.png',
    }

class TerminalBuildScript(buildscript.BuildScript):
    def __init__(self, config, module_list):
        buildscript.BuildScript.__init__(self, config, module_list)
        self.trayicon = trayicon.TrayIcon()
        self.notify = notify.Notify(config)

    def message(self, msg, module_num=-1):
        '''Display a message to the user'''
        
        if module_num == -1:
            module_num = self.module_num
        if module_num > 0:
            progress = ' [%d/%d]' % (module_num, len(self.modulelist))
        else:
            progress = ''
        print '%s*** %s ***%s%s' % (t_bold, msg, progress, t_reset)
        if is_xterm:
            print '\033]0;jhbuild: %s%s\007' % (msg, progress)
        self.trayicon.set_tooltip('%s%s' % (msg, progress))

    def set_action(self, action, module, module_num=-1, action_target=None):
        if module_num == -1:
            module_num = self.module_num
        if not action_target:
            action_target = module.name
        self.message('%s %s' % (action, action_target), module_num)

    def execute(self, command, hint=None, cwd=None, extra_env=None):
        '''executes a command, and returns the error code'''
        kws = {
            'close_fds': True
            }
        if isinstance(command, (str, unicode)):
            kws['shell'] = True
            pretty_command = command
        else:
            pretty_command = ' '.join(command)
        print pretty_command

        # get rid of hint if pretty printing is disabled.
        if not self.config.pretty_print:
            hint = None

        kws['stdin'] = subprocess.PIPE
        if hint in ('cvs', 'svn'):
            kws['stdout'] = subprocess.PIPE
            kws['stderr'] = subprocess.STDOUT
        else:
            kws['stdout'] = None
            kws['stderr'] = None

        if cwd is not None:
            kws['cwd'] = cwd

        if extra_env is not None:
            kws['env'] = os.environ.copy()
            kws['env'].update(extra_env)

        try:
            p = subprocess.Popen(command, **kws)
        except OSError, e:
            sys.stderr.write('Error: %s\n' % str(e))
            raise CommandError(str(e))

        if hint in ('cvs', 'svn'):
            conflicts = []
            def format_line(line, error_output, conflicts=conflicts):
                if line[-1] == '\n': line = line[:-1]
                if line.startswith('C '):
                    conflicts.append(line)
                    print '%s%s%s' % (t_colour[12], line, t_reset)
                elif line.startswith('M '):
                    print '%s%s%s' % (t_colour[10], line, t_reset)
                elif line.startswith('? '):
                    print '%s%s%s' % (t_colour[8], line, t_reset)
                else:
                    print line
            cmds.pprint_output(p, format_line)
            if conflicts:
                sys.stdout.write('\nConflicts during checkout:\n')
                for line in conflicts:
                    sys.stdout.write('%s  %s%s\n'
                                     % (t_colour[12], line, t_reset))
                # make sure conflicts fail
                if p.returncode == 0 and hint == 'cvs': p.returncode = 1
        else:
            try:
                p.communicate()
            except KeyboardInterrupt:
                try:
                    os.kill(p.pid, signal.SIGINT)
                except OSError:
                    # process might already be dead.
                    pass
        if p.wait() != 0:
            raise CommandError('########## Error running %s' % pretty_command, p.returncode)

    def start_phase(self, module, state):
        self.trayicon.set_icon(os.path.join(icondir,
                               phase_map.get(state, 'build.png')))

    def end_build(self, failures):
        if len(failures) == 0:
            self.message('success')
        else:
            self.message('the following modules were not built')
            for module in failures:
                print module,
            print

    def handle_error(self, module, state, nextstate, error, altstates):
        '''handle error during build'''
        summary = 'error during stage %s of %s' % (state, module.name)
        self.message('%s: %s' % (summary, error))
        self.trayicon.set_icon(os.path.join(icondir, 'error.png'))
        self.notify.notify(summary = summary, body = error, icon = 'dialog-error', expire = 20)

        if not self.config.interact:
            return 'fail'
        while True:
            print
            print '  [1] rerun stage %s' % state
            print '  [2] ignore error and continue to %s' % nextstate
            print '  [3] give up on module'
            print '  [4] start shell'
            i = 5
            for altstate in altstates:
                print '  [%d] go to stage %s' % (i, altstate)
                i = i + 1
            val = raw_input('choice: ')
            val = val.strip()
            if val == '1':
                return state
            elif val == '2':
                return nextstate
            elif val == '3':
                return 'fail'
            elif val == '4':
                try:
                    os.chdir(module.get_builddir(self))
                except OSError:
                    os.chdir(self.config.checkoutroot)
                print 'exit shell to continue with build'
                os.system(user_shell)
            else:
                try:
                    val = int(val)
                    return altstates[val - 5]
                except:
                    print 'invalid choice'
        assert False, 'not reached'

BUILD_SCRIPT = TerminalBuildScript
