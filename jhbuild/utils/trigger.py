# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2011  Red Hat, Inc.
#
#   trigger.py - Run scripts after packages are installed
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

from jhbuild.utils import cmds, _

class Trigger(object):
    SUFFIX = '.trigger'
    def __init__(self, filepath):
        assert filepath.endswith(self.SUFFIX)
        self._rematches = []
        self._literal_matches = []
        self._executable = None
        self._file = filepath
        self.name = os.path.basename(filepath)[:-len(self.SUFFIX)]

        f = open(self._file)
        for line in f:
            key = '# IfExecutable: '
            if line.startswith(key):
                text = line[len(key):].strip()
                self._executable = text
                continue
            key = '# REMatch: '
            if line.startswith(key):
                text = line[len(key):].strip()
                r = re.compile(text)
                self._rematches.append(r)
                continue
            key = '# LiteralMatch: '
            if line.startswith(key):
                text = line[len(key):].strip()
                self._literal_matches.append(text)
                continue
        f.close()
        if len(self._rematches) == 0 and len(self._literal_matches) == 0:
            raise ValueError(_("No keys specified in trigger script %r") % (filepath, ))
        
    def matches(self, files_list):
        """@files_list should be a list of absolute file paths.  Return True if this trigger script
        should be run."""
        if self._executable is not None:
            if not cmds.has_command(self._executable):
                return False
        for path in files_list:
            for r in self._rematches:
                match = r.search(path)
                if match:
                    return True
            for literal in self._literal_matches:
                if path.find(literal) >= 0:
                    return True
        return False

    def command(self):
        """Returns the command required to execute the trigger script."""
        return ['/bin/sh', self._file]

def load_all(dirpath):
    if not os.path.isdir(dirpath):
        return []
    result = []
    for filename in os.listdir(dirpath):
        if not filename.endswith(Trigger.SUFFIX):
            continue
        filepath = os.path.join(dirpath, filename)
        p = Trigger(filepath)
        result.append(p)
    return result
        
