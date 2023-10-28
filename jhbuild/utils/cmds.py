# jhbuild - a tool to ease building collections of source packages
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
import re
import select
import subprocess
import sys
from signal import SIGINT
from jhbuild.errors import CommandError
from jhbuild.utils import _, udecode

def get_output(cmd, cwd=None, extra_env=None, get_stderr = True):
    '''Return the output (stdout and stderr) from the command.

    If the extra_env dictionary is not empty, then it is used to
    update the environment in the child process.

    If the get_stderr parameter is set to False, then stderr output is ignored.
    
    Raises CommandError if the command exited abnormally or had a non-zero
    error code.
    '''
    if cmd is None:
        raise CommandError(_('Call to undefined command'))

    kws = {}
    if isinstance(cmd, str):
        kws['shell'] = True
    if cwd is not None:
        kws['cwd'] = cwd
    if extra_env is not None:
        kws['env'] = os.environ.copy()
        kws['env'].update(extra_env)

    if get_stderr:
        stderr_output = subprocess.STDOUT
    else:
        stderr_output = subprocess.PIPE
    try:
        p = subprocess.Popen(cmd,
                             close_fds=True,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=stderr_output,
                             **kws)
    except OSError as e:
        raise CommandError(str(e))
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        raise CommandError(_('Error running %s') % cmd, p.returncode)
    return udecode(stdout)

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
            more_commands = index + 1 < len(commands)

            if more_commands:
                c2cread, c2cwrite = os.pipe()
            else:
                c2cwrite = stdout

            self.children.append(
                subprocess.Popen(cmd, shell=isinstance(cmd, str),
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
        p = subprocess.Popen(command, shell=isinstance(command, str),
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
    if not getattr(sys.stdin, "closed", True):
        read_set.append(sys.stdin)

    def format_line_text(data, *args):
        return format_line(udecode(data), *args)

    out_data = err_data = b''
    try:
        while read_set:
            rlist, wlist, xlist = select.select(read_set, [], [])

            if pipe.stdout in rlist:
                out_chunk = os.read(pipe.stdout.fileno(), 10000)
                if out_chunk == b'':
                    pipe.stdout.close()
                    read_set.remove(pipe.stdout)
                    if sys.stdin in read_set:
                        read_set.remove(sys.stdin)
                out_data += out_chunk
                while b'\n' in out_data:
                    pos = out_data.find(b'\n')
                    format_line_text(out_data[:pos+1], False)
                    out_data = out_data[pos+1:]

            if pipe.stderr in rlist:
                err_chunk = os.read(pipe.stderr.fileno(), 10000)
                if err_chunk == b'':
                    pipe.stderr.close()
                    read_set.remove(pipe.stderr)
                err_data += err_chunk
                while b'\n' in err_data:
                    pos = err_data.find(b'\n')
                    format_line_text(err_data[:pos+1], True)
                    err_data = err_data[pos+1:]

            # safeguard against tinderbox that close stdin
            if sys.stdin in rlist and sys.stdin.isatty():
                in_chunk = os.read(sys.stdin.fileno(), 10000)
                if pipe.stdin:
                    os.write(pipe.stdin.fileno(), in_chunk)

        # flush the remainder of stdout/stderr data lacking newlines
        if out_data:
            format_line_text(out_data, False)
        if err_data:
            format_line_text(err_data, True)

    except KeyboardInterrupt:
        # interrupt received.  Send SIGINT to child process.
        try:
            os.kill(pipe.pid, SIGINT)
        except OSError:
            # process might already be dead.
            pass

    return pipe.wait()

def has_command(cmd):
    for path in os.environ['PATH'].split(os.pathsep):
        prog = os.path.abspath(os.path.join(path, cmd))
        if os.path.exists(prog):
            return True

        # also check for cmd.exe on Windows
        if sys.platform.startswith('win') and os.path.exists(prog + ".exe"):
            return True
    return False

def compare_version(version, minver):
    version = version.split('.')
    for i, ver in enumerate(version):
        part = re.sub(r'^[^\d]*(\d*).*$', r'\1', ver)
        if not part:
            version[i] = float("-inf")
        else:
            version[i] = int(part)
    minver = minver.split('.')
    for i, ver in enumerate(minver):
        part = re.sub(r'^[^\d]*(\d*).*$', r'\1', ver)
        if not part:
            minver[i] = float("-inf")
        else:
            minver[i] = int(part)
    return version >= minver

def check_version(cmd, regexp, minver, extra_env=None):
    try:
        data = get_output(cmd, extra_env=extra_env)
    except CommandError:
        return False
    match = re.match(regexp, data, re.MULTILINE)
    if not match:
        return False
    version = match.group(1)
    return compare_version(version, minver)
