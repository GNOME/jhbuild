# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2008  apinheiro@igalia.com, John Carr, Frederic Peters
#
#   changes.py: parsing of svn-commits-list messages
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

from buildbot import util
from buildbot.changes.mail import MaildirSource
from buildbot.changes import changes

from email.Utils import parseaddr
from email.Iterators import body_line_iterator

import base64

class GnomeMaildirSource(MaildirSource):

    name = "Gnome svn-commits-list"

    def parse(self, m, prefix=None):
        if m is None:
            # not a mail at all
            return None

        # From is svnuser@svn.gnome.org
        name, domain = m["from"].split("@")

        # Subject is project revision - etc.
        project = m['subject'].split(' ', 1)[0]

        # If this e-mail is valid, it will come from an svn.gnome.org email
        if domain != "svn.gnome.org":
            return None

        # we take the time of receipt as the time of checkin. Not correct, but it
        # avoids the out-of-order-changes issue. See the comment in parseSyncmail
        # about using the 'Date:' header
        when = util.now()

        revision = None
        files = []
        comments = ""
        isdir = 0
        lines = list(body_line_iterator(m, m['Content-Transfer-Encoding']))
        changeType = ''
        links = []
        while lines:
            line = lines.pop(0)

            if line.startswith('New Revision: '):
                revision = line.split(':', 1)[1].strip()

            if line.startswith('URL: '):
                links.append(line.split(':', 1)[1].strip())

            if line[:-1] == 'Log:':
                while not (lines[0].startswith('Added:') or 
                        lines[0].startswith('Modified:') or 
                        lines[0].startswith('Removed:')):
                    comments += lines.pop(0)
                comments = comments.rstrip()

            if line[:-1] in ("Added:", "Modified:", "Removed:"):
                while not (lines[0] == "\n" or lines[0].startswith('______')):
                    l = lines.pop(0)
                    if l[:-1] not in ("Added:", "Modified:", "Removed:"):
                        files.append(l[3:-1])

        comments = unicode(comments, m.get_content_charset() or 'ascii', 'ignore')
        c = changes.Change(name, files, comments, isdir, revision=revision, links=links, when=when)
        c.project = project # custom attribute
        return c

