# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2008  Igalia S.L., John Carr, Frederic Peters
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

        from_header = m['from']
        if '<' in from_header:
            from_email = m['from'].split('<')[1][:-1]
        else:
            from_email = m['from']

        # From is svnuser@svn.gnome.org
        name, domain = from_email.split("@")

        # If this e-mail is valid, it will come from an svn/src.gnome.org email
        if domain not in ('svn.gnome.org', 'src.gnome.org'):
            return None

        # we take the time of receipt as the time of checkin. Not correct, but it
        # avoids the out-of-order-changes issue. See the comment in parseSyncmail
        # about using the 'Date:' header
        when = util.now()

        revision = None
        files = []
        comments = ""
        isdir = 0
        links = []

        subject = m['subject']

        if subject.startswith('['):
            # git message
            revision = m.get('X-Git-Newrev')
            if not revision:
                # not a new git revision, may be a new tag, a new branch, etc.
                return None

            if m.get('X-Git-Refname', '').startswith('refs/tags/'):
                # ignore tags
                return None

            try:
                project = subject[1:subject.index(']')]
            except ValueError:
                return None # old git commit message; ignored

            if '/' in project:
                # remove the branch part (ex: [anjal/inline-composer-quotes])
                project = project.split('/')[0]

            if ':' in project:
                # remove the patch number part (ex: [anjal: 3/3])
                project = project.split(':')[0]

            if 'Merge branch' in subject:
                comments = subject[subject.index('Merge branch'):]
            elif 'Created branch' in subject:
                comments = subject[subject.index('Created branch'):]
            else:
                lines = list(body_line_iterator(m, m['Content-Transfer-Encoding']))
                after_date = False
                while lines:
                    line = lines.pop(0)
                    if line.startswith('Date:'):
                        after_date = True
                        continue
                    if not after_date:
                        continue
                    if line.startswith('---'):
                        after_date = False
                        break
                    comments += line[4:] + '\n'
                comments = comments.strip()

                comments = unicode(comments, m.get_content_charset() or 'ascii', 'ignore')

                lines = list(body_line_iterator(m, m['Content-Transfer-Encoding']))
                after_dash = False
                while lines:
                    line = lines.pop(0)
                    if line.startswith('---'):
                        after_dash = True
                        continue
                    if not after_dash:
                        continue
                    if not '|' in line:
                        break
                    files.append(line.split()[0])

        else:
            # Subject is project revision - etc.
            project = m['subject'].split(' ', 1)[0]

            lines = list(body_line_iterator(m, m['Content-Transfer-Encoding']))
            changeType = ''
            while lines:
                line = lines.pop(0)

                if line.startswith('New Revision: '):
                    revision = line.split(':', 1)[1].strip()

                if line.startswith('URL: '):
                    links.append(line.split(':', 1)[1].strip())

                if line[:-1] == 'Log:':
                    while lines and not (lines[0].startswith('Added:') or 
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

