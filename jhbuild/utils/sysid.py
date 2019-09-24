# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2014 Canonical Limited
#
#  sysid.py: identify the system that we are running on
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the licence, or
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
import subprocess
import ast

from . import udecode

sys_id = None
sys_name = None
default_conditions = None

def read_os_release():
    global default_conditions
    global sys_name
    global sys_id

    release_file = None

    try:
        release_file = open('/etc/os-release')
    except EnvironmentError:
        try:
            release_file = open('/usr/lib/os-release')
        except EnvironmentError:
            return False

    fields = {}
    for line in release_file:
        line = line.strip()

        if not line or line.startswith('#'):
            continue

        if '=' not in line:
            continue

        field, _, value = line.partition('=')

        if value.startswith("'") or value.startswith('"'):
            try:
                value = ast.literal_eval(value)
            except Exception:
                continue

        fields[field] = value
    release_file.close()

    if 'ID' not in fields or 'VERSION_ID' not in fields:
        return False

    sys_id = fields['ID'] + '-' + fields['VERSION_ID']

    if 'NAME' in fields and 'VERSION' in fields:
        sys_name = fields['NAME'] + ' ' + fields['VERSION']
    else:
        # fall back
        sys_name = fields['ID'] + ' ' + fields['VERSION_ID']

    default_conditions.add(fields['ID'])

    if 'ID_LIKE' in fields:
        default_conditions.update(fields['ID_LIKE'].split(' '))

    return True

def get_macos_info():
    global sys_name
    global sys_id

    try:
        ver = udecode(subprocess.check_output('sw_vers -productVersion'))

        sys_name = 'Mac OS X ' + ver
        sys_id = 'macos-' + ver

        return True

    except (EnvironmentError, subprocess.CalledProcessError):
        return False

def get_freebsd_info():
    global sys_name
    global sys_id

    try:
        ver = udecode(subprocess.check_output('freebsd-version')).strip()

        sys_name = 'FreeBSD ' + ver
        return True
    except (EnvironmentError, subprocess.CalledProcessError):
        pass

    try:
        ver = udecode(subprocess.check_output(['uname', '-r'])).strip()

        sys_name = 'FreeBSD ' + ver
        return True
    except (EnvironmentError, subprocess.CalledProcessError):
        return False

def ensure_loaded():
    global default_conditions
    global sys_name
    global sys_id

    if sys_id is not None:
        return

    # the default conditions set.  We determine which set to used based on
    # the first item in the list which is a prefix of 'sys.platform', which
    # is a name like 'linux2', 'darwin', 'freebsd10', etc.
    #
    # if we watch to match (eg 'freebsd10' more closely than other versions
    # of 'freebsd') then we just need to make sure the more-specific one
    # comes first in the list
    conditions_sets = [
            ('linux', ['linux', 'wayland', 'udev', 'udev-hwdb', 'evdev', 'x11',
             'systemd', 'gnu-elf']),
            ('freebsd', ['freebsd', 'wayland', 'udev', 'x11', 'bsd', 'gnu-elf',
             'gmake']),
            ('darwin', ['darwin', 'macos', 'quartz']),

            # this must be left here so that at least one will be found
            ('', ['x11'])
    ]

    for prefix, flags in conditions_sets:
        if sys.platform.startswith(prefix):
            default_conditions = set(flags)
            break

    # our first choice is to use os-release info
    if read_os_release():
        return

    # but failing that, fall back to using sys.platform
    sys_id = sys.platform

    if sys_id.startswith('linux'):
        sys_name = "Unknown Linux Distribution (no 'os-release' file)"

    elif sys_id.startswith('freebsd'):
        if not get_freebsd_info():
            sys_name = 'FreeBSD (%s)' % (sys_id)

    elif sys_id.startswith('macos'):
        if not get_macos_info():
            sys_name = 'Mac OS X (unknown version)'

    else:
        sys_id = sys.platform
        sys_name = sys.platform

def get_id():
    ensure_loaded()

    return sys_id

def get_pretty_name():
    ensure_loaded()

    return sys_name

def get_default_conditions():
    ensure_loaded()

    return default_conditions
