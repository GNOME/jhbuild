# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
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

import buildscript

index_header = '''<html>
  <head>
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

class TinderboxBuildScript(buildscript.BuildScript):
    def __init__(self, config, module_list):
        buildscript.BuildScript.__init__(self, config, module_list)
        self.indexfp = None
        self.modulefp = None

        self.outputdir = os.path.abspath(config.tinderbox_outputdir)
        if not os.path.exists(self.outputdir):
            os.makedirs(self.outputdir)

    def timestamp(self):
        tm = time.time()
        s = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tm))
        msecs = max(int((tm - int(tm)) * 1000), 0)
        return '%s.%03d' % (s, msecs)

    def message(self, msg, module_num=-1):
        '''Display a message to the user'''
        if self.modulefp:
            self.modulefp.write('\n\n')
            self.modulefp.write(('*' * 60) + '\n')
            self.modulefp.write('%s | %s\n' % (self.timestamp(), msg))
            self.modulefp.write(('*' * 60) + '\n')
        else:
            # do something with messages outside of builds of module builds
            pass

    def set_action(self, action, module, module_num=-1, action_target=None):
        if module_num == -1:
            module_num = self.module_num
        if not action_target:
            action_target = module.name
        self.message('%s %s' % (action, action_target), module_num)

    def execute(self, command, hint=None):
        '''executes a command, and returns the error code'''
        assert self.modulefp, 'not currently building a module'

        self.modulefp.write('%s\n' % command)
        fp = os.popen('{ %s; } 2>&1' % command, 'r')
        data = fp.read(4096)
        while data:
            self.modulefp.write(data)
            data = fp.read(4096)
        status = fp.close()
        if not status:
            return 0
        elif not os.WIFEXITED(status):
            return -1
        else:
            return os.WEXITSTATUS(status)

    def start_build(self):
        assert self.outputdir

        # close stdin
        os.close(0)

        info = []
        import socket
        un = os.uname()

        info.append(('Build Host', socket.gethostname()))
        info.append(('Architecture', '%s %s (%s)' % (un[0], un[2], un[4])))

        release_files = ['/etc/redhat-release', '/etc/debian_version' ]
        release_files += [ os.path.join('/etc', fname)
                           for fname in os.listdir('/etc')
                           if fname.endswith('release') \
                              and fname != 'lsb-release' ]
        for filename in release_files:
            if os.path.exists(filename):
                info.append(('Distribution',
                             open(filename, 'r').readline().strip()))
                break

        info.append(('Module Set', self.config.moduleset))
        info.append(('Start Time', self.timestamp()))

        buildplatform = '<table>\n'
        for (key, val) in info:
            buildplatform += '<tr><th align="left">%s</th><td>%s</td></tr>\n' \
                             % (key, val)
        buildplatform += '</table>\n'
        
        self.indexfp = open(os.path.join(self.outputdir, 'index.html'), 'w')

        self.indexfp.write(index_header % { 'buildplatform': buildplatform })
        self.indexfp.flush()

    def end_build(self, failures):
        self.indexfp.write('<tr>'
                           '<td>%s</td>'
                           '<td>finish</td>'
                           '</tr>\n' % self.timestamp())
        if failures:
            info = '<p>The following modules failed to build</p>\n'
            info += '<blockquote>\n%s\n</blockquote>\n' \
                    ', '.join(failures)
        else:
            info = ''
        self.indexfp.write(index_footer % { 'failures': info })
        self.indexfp.close()
        self.indexfp = None

    def start_module(self, module):
        self.indexfp.write('<tr>'
                           '<td>%s</td>'
                           '<td><a href="%s.txt">%s</a></td>'
                           '<td>\n' % (self.timestamp(), module, module))
        self.modulefp = open(os.path.join(self.outputdir,
                                          '%s.txt' % module), 'w')
    def end_module(self, module, failed):
        self.modulefp.close()
        self.modulefp = None
        self.indexfp.write('</td>\n')
        if failed:
            self.indexfp.write('<td class="failure">failed</td>\n')
        else:
            self.indexfp.write('<td class="success">ok</td>\n')
        self.indexfp.write('</tr>\n\n')
        self.indexfp.flush()

    def end_phase(self, module, state, error):
        if error:
            self.indexfp.write('<span class="failure" title="%s">%s</span>\n'
                               % (error, state))
        else:
            self.indexfp.write('<span class="success">%s</span>\n' % state)
        self.indexfp.flush()

    def handle_error(self, module, state, nextstate, error, altstates):
        '''handle error during build'''
        self.message('error during stage %s of %s: %s' % (state, module.name,
                                                          error))
        return 'fail'

BUILD_SCRIPT = TinderboxBuildScript
