# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2009  Codethink Ltd.
#
#   ldtp.py: Helper methods for running LDTP/gnome-desktop-testing tests
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
#
#  Authors:
#    John Carr <john.carr@unrouted.co.uk>

__all__ = [
    'get_ldtp_helper',
]


class LDTPHelper(object):
    """
    Helper object for running gnome-destop-testing tests
    """

    def __init__(self, application=None):
        self.application = application

    def execute(self, buildscript):
        testargs = ['desktop-testing']

        if self.application:
            testargs.extend(['-a', self.application])

        buildscript.execute(testargs)



