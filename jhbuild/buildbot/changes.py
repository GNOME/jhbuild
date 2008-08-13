from buildbot import util
from buildbot.changes.mail import MaildirSource
from buildbot.changes import changes

from email.Utils import parseaddr
from email.Iterators import body_line_iterator

class GnomeMaildirSource(MaildirSource):

    name = "Gnome svn-commits-list"

    def parse(self, m, prefix=None):
        # From is svnuser@svn.gnome.org
        name, domain = m["from"].split("@")

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
        lines = list(body_line_iterator(m))
        changeType = ''
        links = []
        while lines:
            line = lines.pop(0)

            if line[:14] == "New Revision: ":
                revision = line[14:-1]

            if line[:5] == "URL: ":
                links.append(line[5:-1])

            if line[:-1] == "Log:":
                while not (lines[0].startswith("Added:") or lines[0].startswith("Modified:") or lines[0].startswith("Removed:")):
                    comments += lines.pop(0)
                comments = comments.rstrip()

            if line[:-1] in ("Added:", "Modified:", "Removed:"):
                while not (lines[0] == "\n"):
                    l = lines.pop(0)
                    if l[:-1] not in ("Added:", "Modified:", "Removed:"):
                        files.append(l[3:-1])

        return changes.Change(name, files, comments, isdir, revision=revision, links=links, when=when)

