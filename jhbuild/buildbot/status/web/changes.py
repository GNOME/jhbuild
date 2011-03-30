# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2008  Frederic Peters
#
#   changes.py: custom changes pages
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

import time

from buildbot.status.web.base import HtmlResource
from twisted.web.util import Redirect
from twisted.web.error import NoResource

class ChangesResource(HtmlResource):
    def getChild(self, path, req):
        if path == '':
            return Redirect('..')
        num = int(path)
        c = self.getStatus(req).getChange(num)
        if not c:
            return NoResource("No change number '%d'" % num)
        return ChangeResource(c)


class ChangeResource(HtmlResource):
    def __init__(self, change):
        self.change = change

    def getTitle(self, request):
        status = self.getStatus(request)
        p = status.getProjectName()
        if len(self.change.revision) == 40:
            return '%s - %s - commit %s' % (p, self.change.project, self.change.revision[:8])
        else:
            return '%s - %s - revision #%s' % (p, self.change.project, int(self.change.revision))

    def body(self, request):
        data = '<div class="changeset">\n'
        data += '<ul>'
        if self.change.project:
            data += '<li>Project: <a href="../%s">%s</a></li>\n' % (
                    self.change.project, self.change.project)
        if self.change.who:
            data += '<li>Author: <strong class="author">%s</strong></li>\n' % self.change.who
        if self.change.when:
            data += '<li>Date: <strong class="date">%s</strong></li>\n' % time.strftime(
                    '%a %d %b %Y %H:%M:%S', time.localtime(self.change.when))
        if self.change.files:
            data += '<li>Files:<ul>\n'
            for f in self.change.files:
                data += '<li><tt>%s</tt></li>\n' % f
            data += '</ul></li>\n'
        data += '</ul>\n'
        if self.change.comments:
            data += '<pre>'
            data += self.change.comments
            data += '</pre>\n'

        if self.change.revision:
            if len(self.change.revision) == 40:
                # git commit
                if hasattr(self.change, 'git_module_name'):
                    git_module_name = self.change.git_module_name
                else:
                    git_module_name = self.change.project
                link = 'http://git.gnome.org/browse/%s/commit/?id=%s' % (
                        git_module_name, self.change.revision)
                data += '<p>View in GNOME cgit: <a href="%s">%s commit %s</a></dd>\n' % (
                        link, git_module_name, self.change.revision[:8])
            else:
                link = 'http://svn.gnome.org/viewvc/%s?view=revision&revision=%s' % (
                        self.change.project, self.change.revision)
                data += '<p>View in GNOME ViewVC: <a href="%s">%s r%s</a></dd>\n' % (
                        link, self.change.project, self.change.revision)

        data += '</div>'
        return data

