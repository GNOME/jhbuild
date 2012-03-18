# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2009 Frederic Peters
#
#   bot.py: pages with info on slaves
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

import urllib, time

from twisted.web import html
from twisted.web.util import Redirect

from buildbot.status.web.base import HtmlResource

class JhBuildbotResource(HtmlResource):
    def __init__(self, slavename, req):
        HtmlResource.__init__(self)
        self.slavename = slavename
        botmaster = self.getStatus(req).botmaster
        self.slave = botmaster.slaves[slavename]

    def getTitle(self, request):
        return 'Buildbot: %s' % self.slave.slavename

    def body(self, req):
        data = ''
        data += '<dl>\n'
        data += '  <dt>Contact</dt>\n'
        data += '  <dd><ul>'
        if self.slave.contact_name:
            data += '<li>%s</li>\n' % self.slave.contact_name
        if self.slave.url:
            data += '<li><a href="%s">%s</a></li>\n' % (self.slave.url, self.slave.url)
        data += '  </ul></dd>'
        data += '  <dt>Running</dt>'
        data += '  <dd><ul>'
        if self.slave.distribution:
            data += '<li>%s</li>\n' % self.slave.distribution
        if self.slave.version:
            data += '<li>%s</li>\n' % self.slave.version
        if self.slave.architecture:
            data += '<li>%s</li>\n' % self.slave.architecture
        data += '  </ul></dd>'
        data += '</dl>'
        return data


class JhBuildbotsResource(HtmlResource):
    def getChild(self, path, req):
        if path == '':
            return Redirect('..')
        parent = req.site.buildbot_service
        if path in parent.slaves:
            return JhBuildbotResource(path, req)
        return HtmlResource.getChild(self, path, req)
