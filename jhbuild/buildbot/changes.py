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

from jhbuild.versioncontrol.git import GitBranch

class GnomeMaildirSource(MaildirSource):
    name = "GNOME commits-list"

    def __init__(self, mailbox, modules, prefix):
        MaildirSource.__init__(self, mailbox, prefix=prefix)
        self.modules = modules

    def parse(self, m, prefix=None):
        if m is None:
            # not a mail at all
            return None

        from_header = m['from']
        if '<' in from_header:
            from_email = m['from'].split('<')[1][:-1]
        else:
            from_email = m['from']

        # From is account@src.gnome.org
        name, domain = from_email.split("@")

        # If this e-mail is valid, it will come from an svn/src.gnome.org email
        if domain != 'src.gnome.org':
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

        if not subject.startswith('['):
            # not a git message, abort
            return None

        # git message
        revision = m.get('X-Git-Newrev')
        if not revision:
            # not a new git revision, may be a new tag, a new branch, etc.
            return None

        if revision == '0000000000000000000000000000000000000000':
            # probably a deleted branch, ignore
            return None

        if m.get('X-Git-Refname', '').startswith('refs/tags/'):
            # ignore tags
            return None

        try:
            project = subject[1:subject.index(']')]
        except ValueError:
            return None # old git commit message format; ignored

        if '/' in project:
            # remove the branch part (ex: [anjal/inline-composer-quotes])
            project = project.split('/')[0]

        if ':' in project:
            # remove the patch number part (ex: [anjal: 3/3])
            project = project.split(':')[0]

        if 'Created branch' in subject:
            # new branches don't have to trigger rebuilds
            return None

        if 'Merge branch' in subject:
            comments = subject[subject.index('Merge branch'):]
        elif 'Merge commit' in subject:
            comments = subject[subject.index('Merge commit'):]
        else:
            lines = list(body_line_iterator(m, m['Content-Transfer-Encoding']))
            after_date = False
            in_files = False
            while lines:
                line = lines.pop(0)
                if line.startswith('Date:'):
                    after_date = True
                    continue
                if not after_date:
                    continue
                if len(line) > 3 and line[0] == ' ' and line[1] != ' ' and '|' in line:
                    in_files = True
                if line.startswith('---'):
                    break
                if in_files:
                    if not '|' in line:
                        break
                    files.append(line.split()[0])
                else:
                    comments += line[4:] + '\n'

            comments = unicode(comments.strip(), m.get_content_charset() or 'ascii', 'ignore')

        c = changes.Change(name, files, comments, isdir, revision=revision, links=links, when=when)
        c.project = project
        c.git_module_name = project

        # some modules may have alternate checkouts under different names, look
        # for those, and create appropriate Change objects
        for module in self.modules:
            if hasattr(module, 'branch') and isinstance(module.branch, GitBranch):
                git_module_name = module.branch.module.rsplit('/', 1)[-1]
                if module.name != project and git_module_name == project:
                    change = changes.Change(name, files, comments, isdir,
                                    revision=revision, links=links, when=when)
                    change.project = module.name
                    change.git_module_name = git_module_name
                    self.parent.addChange(change)

        return c
