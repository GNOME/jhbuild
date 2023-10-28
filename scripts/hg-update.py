#! /usr/bin/env python3
#
# hg-update - pull and update a mercurial repository
#
# Copyright (C) 2007  Marco Barisione <marco@barisione.org>
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
import sys
import re

from subprocess import Popen, call, PIPE, STDOUT

def get_parent():
    hg = Popen(['hg', 'parents', '--template', '{rev}'], stdout=PIPE, universal_newlines=True)
    try:
        return hg.stdout.read().split()[0]
    except IndexError:
        # handle parentless revisions
        return ''

def pull():
    ret = call(['hg', 'pull'])
    return ret == 0

def update():
    env = dict(os.environ)
    env['HGMERGE'] = '/bin/false'
    env['LANG'] = 'C'
    hg = Popen(['hg', 'update', '--noninteractive'], stdout=PIPE,
               stderr=STDOUT, env=env, universal_newlines=True)
    out = hg.communicate()[0]
    if hg.returncode != 0:
        # Use CVS-like format for conflicts.
        out = re.sub('merging (.*) failed!', r'C \1', out)
        index = out.find('You can redo the full merge using:')
        # Remove the instructions to redo the full merge as we are
        # going to revert the update.
        if index != -1:
            out = out[:index]
    print(out)
    return hg.returncode == 0

def undo_update(parent):
    print('Update failed, updating to parent revision')
    env = dict(os.environ)
    env['HGMERGE'] = 'false'
    call(['hg', 'update', '--noninteractive', '-q', parent], env=env)

def pull_and_update():
    parent = get_parent()
    if not pull():
        return False
    if update():
        return True
    else:
        undo_update(parent)
        return False

if __name__ == '__main__':
    ret = False
    try:
        ret = pull_and_update()
    except OSError as e:
        print('%s: %s' % (sys.argv[0], e))

    if ret:
        exit_code = 0
    else:
        exit_code = 1
    sys.exit(exit_code)

