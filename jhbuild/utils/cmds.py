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

def get_output(cmd):
    '''Return the output (stdout and stderr) from the command.
    Raises an exception if the command has a non-zero return value.'''
    fp = os.popen('{ %s; } 2>&1' % cmd, 'r')
    data = fp.read()
    status = fp.close()
    if status and (not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0):
        raise RuntimeError('program exited abnormally')
    return data

def execute_pprint(cmd, format_line, split_stderr=False):
    '''Run the given program and pass lines to the format_line function
    for formatting.  If split_stderr is True, then the second argument
    to the format_line function will be true for error output.'''
    if split_stderr:
        child = popen2.Popen3(cmd, capturestderr=True)
    else:
        child = popen2.Popen4(cmd)
    # don't talk to child
    child.tochild.close()
    out_fp = child.fromchild
    out_fd = out_fp.fileno()
    out_eof = False
    fcntl.fcntl(out_fd, fcntl.F_SETFL,
                fcntl.fcntl(out_fd, fcntl.F_GETFL) | os.O_NDELAY)
    err_fp = child.childerr
    err_fd = -1
    err_eof = True
    read_fds = [ out_fd ]
    if err_fp:
        err_fd = err_fp.fileno()
        err_eof = False
        fcntl.fcntl(err_fd, fcntl.F_SETFL,
                    fcntl.fcntl(err_fd, fcntl.F_GETFL) | os.O_NDELAY)
        read_fds.append(err_fd)
    out_data = err_data = ''
    try:
        while True:
            rfds, wfds, xdfs = select.select(read_fds, [], [])
            if out_fd in rfds:
                out_chunk = out_fp.read()
                if out_chunk == '': out_eof = True
                out_data += out_chunk
                while '\n' in out_data:
                    pos = out_data.find('\n')
                    format_line(out_data[:pos+1], False)
                    out_data = out_data[pos+1:]
            if err_fd in rfds:
                err_chunk = err_fp.read()
                if err_chunk == '': err_eof = True
                err_data += err_chunk
                while '\n' in err_data:
                    pos = err_data.find('\n')
                    format_line(err_data[:pos+1], True)
                    err_data = err_data[pos+1:]
            if out_eof and err_eof: break
    except KeyboardInterrupt:
        pass
    status = child.wait()
    return status
