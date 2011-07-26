# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   tinderbox.py: build logic for a non-interactive reporting build
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
import time
import subprocess
import locale
import logging
import codecs
import sys

from jhbuild.main import _encoding
from jhbuild.utils import cmds
from jhbuild.errors import CommandError, FatalError
import buildscript
import commands

index_header = '''<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html;charset=%(charset)s">
    <title>JHBuild Results</title>
    <style type="text/css">
      .section {
        margin-after: 1.5em;
      }
      .success {
        color: black;
        background-color: #afa;
      }
      .failure {
        color: black;
        background-color: #faa;
      }
    </style>
  </head>
  <body>
    <h1>JHBuild Results</h1>

    <div class="section">
    <h2>Platform</h2>
    %(buildplatform)s
    </div>

    <div class="section">
    <h2>Summary</h2>
    <table>
      <tr>
        <th>Time</th>
        <th>Module</th>
        <th>Phases</th>
        <th>Status</th>
      </tr>
'''
index_footer = '''
    </table>
    </div>

    %(failures)s
  </body>
</html>
'''

buildlog_header = '''<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html;charset=%(charset)s">
    <title>%(module)s Build Log</title>
    <style type="text/css">
      pre {
        /* unfortunately, white-space: pre-wrap is not widely supported ... */
        white-space: -moz-pre-wrap; /* Mozilla based browsers */
        white-space: -pre-wrap;     /* Opera 4 - 6 */
        white-space: -o-pre-wrap;   /* Opera >= 7 */
        white-space: pre-wrap;      /* CSS3 */
        word-wrap: break-word;      /* IE 5.5+ */
      }
      .message {
        font-size: larger;
      }
      .timestamp{
        font-size: smaller;
        font-style: italic;
      }
      .command {
        color: blue;
      }
      .conflict {
        color: red;
      }
      .critical {
        background-color: red;
      }
      .error {
        color: red;
      }
      .warning {
        color: darkgreen;
        font-size: smaller;
      }
      .info {
        color: darkgreen;
        font-size: smaller;
      }
      .debug {
        color: gray;
        font-size: smaller;
      }
      .note {
        background-color: #FFFF66;
      }
    </style>
  </head>
  <body>
    <h1>%(module)s Build Log</h1>
'''
buildlog_footer = '''
  </body>
</html>
'''

def get_distro():
    # try using the lsb_release tool to get the distro info
    try:
        distro = cmds.get_output(['lsb_release', '--short', '--id']).strip()
        release = cmds.get_output(['lsb_release', '--short', '--release']).strip()
        codename = cmds.get_output(['lsb_release', '--short', '--codename']).strip()
        if codename:
            return '%s %s (%s)' % (distro, release, codename)
        else:
            return '%s %s' % (distro, release)
    except (CommandError, IOError):
        pass

    # otherwise, look for a /etc/*-release file
    release_files = ['/etc/redhat-release', '/etc/debian_version' ]
    release_files.extend([ os.path.join('/etc', fname)
                           for fname in os.listdir('/etc')
                             if fname.endswith('release') \
                                 and fname != 'lsb-release' ])
    for filename in release_files:
        if os.path.exists(filename):
            return open(filename, 'r').readline().strip()

    osx = commands.getoutput('sw_vers -productVersion')
    if osx:
        return 'Mac OS X ' + osx;

    # else:
    return None

def escape(string):
    if type(string) is not unicode:
        string = unicode(string, _encoding, 'replace')
    string = string.replace('&', '&amp;').replace('<','&lt;').replace(
            '>','&gt;').replace('\n','<br/>').replace(
            '\t','&nbsp;&nbsp;&nbsp;&nbsp;')
    return string

class LoggingFormatter(logging.Formatter):
    def __init__(self):
        logging.Formatter.__init__(self, '<div class="%(levelname)s">'
                                   '%(message)s</div>')

class TinderboxBuildScript(buildscript.BuildScript):
    help_url = 'http://live.gnome.org/JhbuildIssues/'
    triedcheckout = None

    def __init__(self, config, module_list, module_set=None):
        buildscript.BuildScript.__init__(self, config, module_list, module_set=module_set)
        self.indexfp = None
        self.modulefp = None

        for handle in logging.getLogger().handlers:
            handle.setFormatter(LoggingFormatter())

        self.outputdir = os.path.abspath(config.tinderbox_outputdir)
        if not os.path.exists(self.outputdir):
            os.makedirs(self.outputdir)

        os.environ['TERM'] = 'dumb'

        self.charset = _encoding

    def timestamp(self):
        tm = time.time()
        s = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tm))
        msecs = max(int((tm - int(tm)) * 1000), 0)
        return '%s.%03d' % (s, msecs)

    def message(self, msg, module_num=-1):
        '''Display a message to the user'''
        if self.modulefp:
            self.modulefp.write('<div><b class="message">%s</b> '
                                '<span class="timestamp">%s</span></div>\n'
                                % (escape(msg), self.timestamp()))
        else:
            # do something with messages outside of builds of module builds
            pass

    def set_action(self, action, module, module_num=-1, action_target=None):
        if module_num == -1:
            module_num = self.module_num
        if not action_target:
            action_target = module.name
        self.message('%s %s' % (action, action_target), module_num)

    def execute(self, command, hint=None, cwd=None, extra_env=None):
        assert self.modulefp, 'not currently building a module'

        kws = {
            'close_fds': True
            }
        print_args = {}
        if cwd:
            print_args['cwd'] = cwd
        else:
            print_args['cwd'] = os.getcwd()

        self.modulefp.write('<pre>')
        if isinstance(command, (str, unicode)):
            kws['shell'] = True
            print_args['command'] = command
        else:
            print_args['command'] = ' '.join(command)

        if self.config.print_command_pattern:
            try:
                commandstr = self.config.print_command_pattern % print_args
                self.modulefp.write('<span class="command">%s</span>\n'
                                    % escape(commandstr))
            except TypeError, e:
                raise FatalError('\'print_command_pattern\' %s' % e)
            except KeyError, e:
                raise FatalError(_('%(configuration_variable)s invalid key'
                                   ' %(key)s' % \
                                   {'configuration_variable' :
                                        '\'print_command_pattern\'',
                                    'key' : e}))

        kws['stdin'] = subprocess.PIPE
        kws['stdout'] = subprocess.PIPE
        kws['stderr'] = subprocess.PIPE
        if hint == 'cvs':
            def format_line(line, error_output, fp=self.modulefp):
                if line[-1] == '\n': line = line[:-1]
                if line.startswith('C '):
                    fp.write('<span class="conflict">%s</span>\n'
                                        % escape(line))
                else:
                    fp.write('%s\n' % escape(line))
            kws['stderr'] = subprocess.STDOUT
        else:
            def format_line(line, error_output, fp=self.modulefp):
                if line[-1] == '\n': line = line[:-1]
                if error_output:
                    fp.write('<span class="error">%s</span>\n'
                                        % escape(line))
                else:
                    fp.write('%s\n' % escape(line))

        if cwd is not None:
            kws['cwd'] = cwd

        if extra_env is not None:
            kws['env'] = os.environ.copy()
            kws['env'].update(extra_env)

        command = self._prepare_execute(command)

        try:
            p = subprocess.Popen(command, **kws)
        except OSError, e:
            self.modulefp.write('<span class="error">Error: %s</span>\n'
                                % escape(str(e)))
            raise CommandError(str(e))
        cmds.pprint_output(p, format_line)
        self.modulefp.write('</pre>\n')
        self.modulefp.flush()
        if p.returncode != 0:
            raise CommandError('Error running %s' % print_args['command'],
                               p.returncode)

    def start_build(self):
        assert self.outputdir

        # close stdin
        sys.stdin.close()

        info = []
        import socket
        un = os.uname()

        info.append(('Build Host', socket.gethostname()))
        info.append(('Architecture', '%s %s (%s)' % (un[0], un[2], un[4])))

        distro = get_distro()
        if distro:
            info.append(('Distribution', distro))

        info.append(('Module Set', self.config.moduleset))
        info.append(('Start Time', self.timestamp()))

        buildplatform = '<table>\n'
        for (key, val) in info:
            buildplatform += '<tr><th align="left">%s</th><td>%s</td></tr>\n' \
                             % (key, val)
        buildplatform += '</table>\n'
        
        self.indexfp = codecs.open(os.path.join(self.outputdir, 'index.html'),
                'w', encoding=self.charset, errors='xmlcharrefreplace')

        self.indexfp.write(index_header % { 'buildplatform': buildplatform,
                                            'charset': self.charset })
        self.indexfp.flush()

    def end_build(self, failures):
        self.indexfp.write('<tr>'
                           '<td>%s</td>'
                           '<td>finish</td>'
                           '</tr>\n' % self.timestamp())
        if failures:
            info = '<p>The following modules failed to build</p>\n'
            info += '<blockquote>\n'
            info += ', '.join(failures)
            info += '</blockquote>\n'
        else:
            info = ''
        self.indexfp.write(index_footer % { 'failures': info })
        self.indexfp.close()
        self.indexfp = None

    def start_module(self, module):
        self.modulefilename='%s.html' % module.replace('/','_')
        self.indexfp.write('<tr>'
                           '<td>%s</td>'
                           '<td><a href="%s">%s</a></td>'
                           '<td>\n' % (self.timestamp(), self.modulefilename,
                                       module))
        self.modulefp = codecs.open(
                os.path.join(self.outputdir, self.modulefilename), 'w',
                encoding=self.charset, errors='xmlcharrefreplace')

        for handle in logging.getLogger().handlers:
            if isinstance(handle, logging.StreamHandler):
                handle.stream = self.modulefp

        self.modulefp.write(buildlog_header % { 'module': module,
                                                'charset': self.charset })
    def end_module(self, module, failed):
        if failed:
            self.message('Failed')
        else:
            self.message('Succeeded')
        self.modulefp.write(buildlog_footer)
        self.modulefp.close()
        self.modulefp = None
        self.indexfp.write('</td>\n')
        if failed:
            self.indexfp.write('<td class="failure">failed '
                               '<a href="%s%s">'
                               '(help)</a></td>\n' % (self.help_url, module))
        else:
            self.indexfp.write('<td class="success">ok</td>\n')
        self.indexfp.write('</tr>\n\n')
        self.indexfp.flush()

    def start_phase(self, module, phase):
        self.modulefp.write('<a name="%s"></a>\n' % phase)
    def end_phase(self, module, phase, error):
        if error:
            self.indexfp.write('<a class="failure" title="%s" href="%s#%s">%s</a>\n'
                               % (error, self.modulefilename, phase, phase))
        else:
            self.indexfp.write('<a class="success" href="%s#%s">%s</a>\n'
                               % (self.modulefilename, phase, phase))
        self.indexfp.flush()

    def handle_error(self, module, phase, nextphase, error, altphases):
        '''handle error during build'''
        self.message('error during stage %s of %s: %s' % (phase, module.name,
                                                          error))
        if self.config.trycheckout:
            if self.triedcheckout is None and altphases.count('configure'):
                self.triedcheckout = 'configure'
                self.message(_('automatically retrying configure'))
                return 'configure'
            elif self.triedcheckout == 'configure' and \
            altphases.count('force_checkout'):
                self.triedcheckout = 'done'
                self.message(_('automatically forcing a fresh checkout'))
                return 'force_checkout'
        self.triedcheckout = None

        if self.modulefp:
            self.modulefp.write('<div class="note">The Gnome Live! website may'
                                ' have suggestions on how to resolve some'
                                ' build errors. Visit'
                                ' <a href="%s%s">%s%s</a>'
                                ' for more information.</div>'
                                % (self.help_url, module.name,
                                   self.help_url, module.name))
        return 'fail'

BUILD_SCRIPT = TinderboxBuildScript
