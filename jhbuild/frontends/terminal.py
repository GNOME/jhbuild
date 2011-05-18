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
import locale

from jhbuild.frontends import buildscript
from jhbuild.utils import cmds
from jhbuild.utils import trayicon
from jhbuild.utils import notify
from jhbuild.errors import CommandError, FatalError

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

try:
    import curses
except ImportError:
    curses = None
else:
    try:
        curses.setupterm()
    except:
        pass

# tray icon stuff ...
if DATADIR:
    icondir = os.path.join(DATADIR, 'jhbuild')
else:
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
    'check':          'check.png',
    'install':        'install.png',
    }

class TerminalBuildScript(buildscript.BuildScript):
    triedcheckout = None
    is_end_of_build = False

    def __init__(self, config, module_list, module_set=None):
        buildscript.BuildScript.__init__(self, config, module_list, module_set=module_set)
        self.trayicon = trayicon.TrayIcon(config)
        self.notify = notify.Notify(config)
        
    def message(self, msg, module_num=-1):
        '''Display a message to the user'''
        
        if module_num == -1:
            module_num = self.module_num
        if module_num > 0:
            progress = ' [%d/%d]' % (module_num, len(self.modulelist))
        else:
            progress = ''

        if not (self.config.quiet_mode and self.config.progress_bar):
            uprint('%s*** %s ***%s%s' % (t_bold, msg, progress, t_reset))
        else:
            progress_percent = 1.0 * (module_num-1) / len(self.modulelist)
            self.display_status_line(progress_percent, module_num, msg)

        if is_xterm:
            sys.stdout.write('\033]0;jhbuild:%s%s\007' % (uencode(msg), progress))
            sys.stdout.flush()
        self.trayicon.set_tooltip('%s%s' % (msg, progress))

    def set_action(self, action, module, module_num=-1, action_target=None):
        if module_num == -1:
            module_num = self.module_num
        if not action_target:
            action_target = module.name
        self.message('%s %s' % (action, action_target), module_num)

    def display_status_line(self, progress, module_num, message):
        if self.is_end_of_build:
            # hardcode progress to 100% at the end of the build
            progress = 1

        columns = curses.tigetnum('cols')
        width = columns / 2
        num_hashes = int(round(progress * width))
        progress_bar = '[' + (num_hashes * '=') + ((width - num_hashes) * '-') + ']'

        module_no_digits = len(str(len(self.modulelist)))
        format_str = '%%%dd' % module_no_digits
        module_pos = '[' + format_str % module_num + '/' + format_str % len(self.modulelist) + ']'

        output = '%s %s %s%s%s' % (progress_bar, module_pos, t_bold, message, t_reset)
        text_width = len(output) - (len(t_bold) + len(t_reset))
        if text_width > columns:
            output = output[:columns+len(t_bold)] + t_reset
        else:
            output += ' ' * (columns-text_width)

        sys.stdout.write('\r'+output)
        if self.is_end_of_build:
            sys.stdout.write('\n')
        sys.stdout.flush()


    def execute(self, command, hint=None, cwd=None, extra_env=None):
        if not command:
            raise CommandError(_('No command given'))

        kws = {
            'close_fds': True
            }
        print_args = {'cwd': ''}
        if cwd:
            print_args['cwd'] = cwd
        else:
            try:
                print_args['cwd'] = os.getcwd()
            except OSError:
                pass

        if isinstance(command, (str, unicode)):
            kws['shell'] = True
            print_args['command'] = command
        else:
            print_args['command'] = ' '.join(command)

        if not self.config.quiet_mode:
            if self.config.print_command_pattern:
                try:
                    print self.config.print_command_pattern % print_args
                except TypeError, e:
                    raise FatalError('\'print_command_pattern\' %s' % e)
                except KeyError, e:
                    raise FatalError(_('%(configuration_variable)s invalid key'
                                       ' %(key)s' % \
                                       {'configuration_variable' :
                                            '\'print_command_pattern\'',
                                        'key' : e}))

        kws['stdin'] = subprocess.PIPE
        if hint in ('cvs', 'svn', 'hg-update.py'):
            kws['stdout'] = subprocess.PIPE
            kws['stderr'] = subprocess.STDOUT
        else:
            kws['stdout'] = None
            kws['stderr'] = None

        if self.config.quiet_mode:
            kws['stdout'] = subprocess.PIPE
            kws['stderr'] = subprocess.STDOUT

        if cwd is not None:
            kws['cwd'] = cwd

        if extra_env is not None:
            kws['env'] = os.environ.copy()
            kws['env'].update(extra_env)

        command = self._prepare_execute(command)

        try:
            p = subprocess.Popen(command, **kws)
        except OSError, e:
            raise CommandError(str(e))

        output = []
        if hint in ('cvs', 'svn', 'hg-update.py'):
            conflicts = []
            def format_line(line, error_output, conflicts = conflicts, output = output):
                if line.startswith('C '):
                    conflicts.append(line)

                if self.config.quiet_mode:
                    output.append(line)
                    return

                if line[-1] == '\n': line = line[:-1]
                if not self.config.pretty_print:
                    hint = None
                    print line
                    return

                if line.startswith('C '):
                    print '%s%s%s' % (t_colour[12], line, t_reset)
                elif line.startswith('M '):
                    print '%s%s%s' % (t_colour[10], line, t_reset)
                elif line.startswith('? '):
                    print '%s%s%s' % (t_colour[8], line, t_reset)
                else:
                    print line

            cmds.pprint_output(p, format_line)
            if conflicts:
                uprint(_('\nConflicts during checkout:\n'))
                for line in conflicts:
                    sys.stdout.write('%s  %s%s\n'
                                     % (t_colour[12], line, t_reset))
                # make sure conflicts fail
                if p.returncode == 0 and hint == 'cvs': p.returncode = 1
        elif self.config.quiet_mode:
            def format_line(line, error_output, output = output):
                output.append(line)
            cmds.pprint_output(p, format_line)
        else:
            try:
                p.communicate()
            except KeyboardInterrupt:
                try:
                    os.kill(p.pid, signal.SIGINT)
                except OSError:
                    # process might already be dead.
                    pass
        try:
            if p.wait() != 0:
                if self.config.quiet_mode:
                    print ''.join(output)
                raise CommandError(_('########## Error running %s')
                                   % print_args['command'], p.returncode)
        except OSError:
            # it could happen on a really badly-timed ctrl-c (see bug 551641)
            raise CommandError(_('########## Error running %s')
                               % print_args['command'])

    def start_phase(self, module, phase):
        self.notify.clear()
        self.trayicon.set_icon(os.path.join(icondir,
                               phase_map.get(phase, 'build.png')))

    def end_build(self, failures):
        self.is_end_of_build = True
        if len(failures) == 0:
            self.message(_('success'))
        else:
            self.message(_('the following modules were not built'))
            for module in failures:
                print module,
            print

    def handle_error(self, module, phase, nextphase, error, altphases):
        '''handle error during build'''
        summary = _('Error during phase %(phase)s of %(module)s') % {
            'phase': phase, 'module':module.name}
        try:
            error_message = error.args[0]
            self.message('%s: %s' % (summary, error_message))
        except:
            error_message = None
            self.message(summary)
        self.trayicon.set_icon(os.path.join(icondir, 'error.png'))
        self.notify.notify(summary = summary, body = error_message,
                icon = 'dialog-error', expire = 20)

        if self.config.trycheckout:
            if self.triedcheckout is None and altphases.count('configure'):
                self.triedcheckout = 'configure'
                self.message(_('automatically retrying configure'))
                return 'configure'
            elif self.triedcheckout == 'configure' and altphases.count('force_checkout'):
                self.triedcheckout = 'done'
                self.message(_('automatically forcing a fresh checkout'))
                return 'force_checkout'
        self.triedcheckout = None

        if not self.config.interact:
            return 'fail'
        while True:
            print
            uprint('  [1] %s' % _('Rerun phase %s') % phase)
            if nextphase:
                uprint('  [2] %s' % _('Ignore error and continue to %s') % nextphase)
            else:
                uprint('  [2] %s' % _('Ignore error and continue to next module'))
            uprint('  [3] %s' % _('Give up on module'))
            uprint('  [4] %s' % _('Start shell'))
            uprint('  [5] %s' % _('Reload configuration'))
            nb_options = i = 6
            for altphase in altphases:
                try:
                    altphase_label = _(getattr(getattr(module, 'do_' + altphase), 'label'))
                except AttributeError:
                    altphase_label = altphase
                uprint('  [%d] %s' % (i, _('Go to phase "%s"') % altphase_label))
                i += 1
            val = raw_input(uencode(_('choice: ')))
            val = udecode(val)
            val = val.strip()
            if val == '1':
                return phase
            elif val == '2':
                return nextphase
            elif val == '3':
                return 'fail'
            elif val == '4':
                cwd = os.getcwd()
                try:
                    os.chdir(module.get_builddir(self))
                except OSError:
                    os.chdir(self.config.checkoutroot)
                uprint(_('exit shell to continue with build'))
                os.system(user_shell)
                os.chdir(cwd) # restor working directory
            elif val == '5':
                self.config.reload()
            else:
                try:
                    val = int(val)
                    selected_phase = altphases[val - nb_options]
                except:
                    uprint(_('invalid choice'))
                    continue
                try:
                    needs_confirmation = getattr(
                            getattr(module, 'do_' + selected_phase), 'needs_confirmation')
                except AttributeError:
                    needs_confirmation = False
                if needs_confirmation:
                    val = raw_input(uencode(_('Type "yes" to confirm the action: ')))
                    val = udecode(val)
                    val = val.strip()
                    if val.lower() in ('yes', _('yes').lower()):
                        return selected_phase
                    continue
                return selected_phase
        assert False, 'not reached'

BUILD_SCRIPT = TerminalBuildScript
