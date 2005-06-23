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
import os
import fcntl
import select
import subprocess

def get_output(cmd):
    '''Return the output (stdout and stderr) from the command.
    Raises an exception if the command has a non-zero return value.'''
    if isinstance(cmd, str):
        useshell = True
    else:
        useshell = False
    p = subprocess.Popen(cmd, shell=useshell,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    stdout, stderr = p.communicate()
    if p.returncode and (not os.WIFEXITED(p.returncode) or
                         os.WEXITSTATUS(p.returncode) != 0):
        raise RuntimeError('program exited abnormally')
    return stdout

def execute_pprint(cmd, format_line, split_stderr=False):
    '''Run the given program and pass lines to the format_line function
    for formatting.  If split_stderr is True, then the second argument
    to the format_line function will be true for error output.'''
    if isinstance(cmd, str):
        useshell = True
    else:
        useshell = False
    if split_stderr:
        stderr = subprocess.PIPE
    else:
        stderr = subprocess.STDOUT
    p = subprocess.Popen(cmd, shell=useshell,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=stderr)
    p.stdin.close()
    read_set = [p.stdout]
    fcntl.fcntl(p.stdout.fileno(), fcntl.F_SETFL,
                fcntl.fcntl(p.stdout.fileno(), fcntl.F_GETFL)|os.O_NDELAY)

    if split_stderr:
        read_set.append(p.stderr)
        fcntl.fcntl(p.stderr.fileno(), fcntl.F_SETFL,
                    fcntl.fcntl(p.stderr.fileno(), fcntl.F_GETFL)|os.O_NDELAY)

    out_data = err_data = ''
    try:
        while read_set:
            rlist, wlist, xlist = select.select(read_set, [], [])

            if p.stdout in rlist:
                out_chunk = p.stdout.read()
                if out_chunk == '':
                    p.stdout.close()
                    read_set.remove(p.stdout)
                out_data += out_chunk
                while '\n' in out_data:
                    pos = out_data.find('\n')
                    format_line(out_data[:pos+1], False)
                    out_data = out_data[pos+1:]
        
            if p.stderr in rlist:
                err_chunk = p.stderr.read()
                if err_chunk == '':
                    p.stderr.close()
                    read_set.remove(p.stderr)
                err_data += err_chunk
                while '\n' in err_data:
                    pos = err_data.find('\n')
                    format_line(err_data[:pos+1], True)
                    err_data = err_data[pos+1:]
        
            select.select([],[],[],.1) # give a little time for buffers to fill
    except KeyboardInterrupt:
        pass
            
    p.wait()
    return p.returncode
