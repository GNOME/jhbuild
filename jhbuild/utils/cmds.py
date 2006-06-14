# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   cmds.py: utilities for running commands and examining their output
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
import select
import subprocess
from signal import SIGINT
from jhbuild.errors import CommandError

def get_output(cmd, cwd=None, extra_env=None):
    '''Return the output (stdout and stderr) from the command.

    If the extra_env dictionary is not empty, then it is used to
    update the environment in the child process.
    
    Raises CommandError if the command exited abnormally or had a non-zero
    error code.
    '''
    kws = {}
    if isinstance(cmd, (str, unicode)):
        kws['shell'] = True
    if cwd is not None:
        kws['cwd'] = cwd
    if extra_env is not None:
        kws['env'] = os.environ.copy()
        kws['env'].update(extra_env)
    try:
        p = subprocess.Popen(cmd,
                             close_fds=True,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             **kws)
    except OSError, e:
        raise CommandError(str(e))
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        raise CommandError('Error running %s' % cmd, p.returncode)
    return stdout

class Pipeline(subprocess.Popen):
    '''A class that wraps a sequence of subprocess.Popen() objects
    connected together in a pipeline.

    Note that if stderr=subprocess.STDOUT, the stderr of intermediate
    children is not passed to the stdin of the next child.  Instead,
    it is mixed in with the stdout of the final child.
    '''
    def __init__(self, commands, bufsize=0,
                 stdin=None, stdout=None, stderr=None,
                 cwd=None, env=None, universal_newlines=False):
        '''Commands is a list of argument lists to invoke'''
        self.universal_newlines = universal_newlines
        if universal_newlines:
            readmode = 'rU'
        else:
            readmode = 'rb'
        c2pwrite = None
        errwrite = None
        self.stdin = None
        self.stdout = None
        self.stderr = None
        if stdout == subprocess.PIPE:
            c2pread, c2pwrite = os.pipe()
            stdout = c2pwrite
            self.stdout = os.fdopen(c2pread, readmode, bufsize)
        if stderr == subprocess.PIPE:
            errread, errwrite = os.pipe()
            stderr = errwrite
            self.stderr = os.fdopen(errread, readmode, bufsize)
        elif stderr == subprocess.STDOUT:
            stderr = stdout
        
        self.children = []
        close_stdin = False
        for index, cmd in enumerate(commands):
            first_command = (index == 0)
            more_commands = index + 1 < len(commands)

            if more_commands:
                c2cread, c2cwrite = os.pipe()
            else:
                c2cwrite = stdout

            self.children.append(
                subprocess.Popen(cmd, shell=isinstance(cmd, (str, unicode)),
                                 bufsize=bufsize, close_fds=True,
                                 cwd=cwd, env=env,
                                 stdin=stdin,
                                 stdout=c2cwrite,
                                 stderr=stderr,
                                 universal_newlines=universal_newlines)
                )
            if close_stdin:
                os.close(stdin)
                close_stdin = False
            if more_commands:
                os.close(c2cwrite)
                stdin = c2cread
                close_stdin = True
        if close_stdin:
            os.close(stdin)
        if c2pwrite:
            os.close(c2pwrite)
        if errwrite:
            os.close(errwrite)

        self.stdin = self.children[0].stdin
        self.returncode = None

    def poll(self):
        for child in self.children:
            returncode = child.poll()
            if returncode is None:
                break
        else:
            self.returncode = returncode
        return self.returncode

    def wait(self):
        for child in self.children:
            returncode = child.wait()
        self.returncode = returncode
        return self.returncode

def spawn_child(command, use_pipe=False,
                cwd=None, env=None,
                stdin=None, stdout=None, stderr=None):
    if use_pipe:
        p = Pipeline(command, cwd=cwd, env=env,
                     stdin=stdin, stdout=stdout, stderr=stderr)
    else:
        p = subprocess.Popen(command, shell=isinstance(command, (str,unicode)),
                             close_fds=True, cwd=cwd, env=env,
                             stdin=stdin, stdout=stdout, stderr=stderr)
    return p

def pprint_output(pipe, format_line):
    '''Process the output of the subprocess and pass lines to the
    format_line function for formatting.  The first argument passed to
    the format_line function is the line of text.  The second argument
    is True if the line was read from the stderr stream.'''
    read_set = []
    if pipe.stdout:
        read_set.append(pipe.stdout)
    if pipe.stderr:
        read_set.append(pipe.stderr)

    out_data = err_data = ''
    try:
        while read_set:
            rlist, wlist, xlist = select.select(read_set, [], [])

            if pipe.stdout in rlist:
                out_chunk = os.read(pipe.stdout.fileno(), 1024)
                if out_chunk == '':
                    pipe.stdout.close()
                    read_set.remove(pipe.stdout)
                out_data += out_chunk
                while '\n' in out_data:
                    pos = out_data.find('\n')
                    format_line(out_data[:pos+1], False)
                    out_data = out_data[pos+1:]
        
            if pipe.stderr in rlist:
                err_chunk = os.read(pipe.stderr.fileno(), 1024)
                if err_chunk == '':
                    pipe.stderr.close()
                    read_set.remove(pipe.stderr)
                err_data += err_chunk
                while '\n' in err_data:
                    pos = err_data.find('\n')
                    format_line(err_data[:pos+1], True)
                    err_data = err_data[pos+1:]
        
            select.select([],[],[],.1) # give a little time for buffers to fill
    except KeyboardInterrupt:
        # interrupt received.  Send SIGINT to child process.
        try:
            os.kill(pipe.pid, SIGINT)
        except OSError:
            # process might already be dead.
            pass

    return pipe.wait()
