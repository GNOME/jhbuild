# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2004  James Henstridge
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
import fcntl
import select
import popen2

try:
    import pty
except ImportError:
    pty = None

def get_output(cmd):
    '''Return the output (stdout and stderr) from the command.
    Raises an exception if the command has a non-zero return value.'''
    fp = os.popen('{ %s; } 2>&1' % cmd, 'r')
    data = fp.read()
    status = fp.close()
    if status and (not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0):
        raise RuntimeError('program exited abnormally')
    return data

if pty:
    # modified version of pty.spawn, that returns the child's status
    def _spawn(argv, master_read=pty._read, stdin_read=pty._read):
        """Create a spawned process."""
        if type(argv) == type(''):
            argv = (argv,)
        status = -1
        pid, master_fd = pty.fork()
        if pid == pty.CHILD:
            os.execlp(argv[0], *argv)
        try:
            mode = pty.tty.tcgetattr(pty.STDIN_FILENO)
            pty.tty.setraw(pty.STDIN_FILENO)
            restore = True
        except pty.tty.error:    # This is the same as termios.error
            restore = False
        fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NDELAY |
                    fcntl.fcntl(master_fd, fcntl.F_GETFL))
        try:
            pty._copy(master_fd, master_read, stdin_read)
        except (IOError, OSError):
            if restore:
                pty.tty.tcsetattr(pty.STDIN_FILENO, pty.tty.TCSAFLUSH, mode)
        pid, status = os.waitpid(pid, 0)
        os.close(master_fd)
        return status

def execute_pprint(cmd, format_line):
    '''Run the given program in a pty, and pass all its output to the
    format_line function before printing to the screen.  This allows for
    simple pretty-printed output of programs.
    This uses the pty.spawn() standard library function.  If it is not
    not available, then we fall back to os.system().'''
    if pty:
        argv = [ '/bin/sh', '-c', cmd ]
        def master_read(fd, format_line=format_line):
            data = os.read(fd, 1024)
            ret = []
            for line in data.splitlines(True):
                ret.append(format_line(line))
            return ''.join(ret)
        status = _spawn(argv, master_read)
    else:
        status = os.system(cmd)

    if not os.WIFEXITED(status):
        return -1
    else:
        return os.WEXITSTATUS(status)
