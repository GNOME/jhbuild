# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008  Frederic Peters
#
#   build.py: custom logs pages
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

try:
    import html5lib
except ImportError:
    html5lib = None

try:
    import elementtree.ElementTree as ET
except ImportError:
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        ET = None

from buildbot.status.web.logs import LogsResource, HtmlResource, NoResource, IHTMLLog

from zope.interface import implements
from twisted.python import components


from twisted.web.resource import Resource
from twisted.web.error import NoResource

from buildbot import interfaces
from buildbot.status import builder
from buildbot.status.web.base import IHTMLLog, HtmlResource
from twisted.web.util import Redirect


class HTMLLog(HtmlResource):
    implements(IHTMLLog)

    def __init__(self, original):
        Resource.__init__(self)
        self.original = original

        parser = html5lib.HTMLParser()
        c = parser.parse(self.original.html)
        if c.childNodes[0].type == 3: # doctype
            c = c.childNodes[1]
        if c.attributes.get('xmlns'):
            del c.attributes['xmlns']
        self.x = ET.fromstring(c.toxml())

    def getTitle(self, request):
        status = self.getStatus(request)
        p = status.getProjectName()
        title = self.x.find('head/title')
        if title is not None:
            return '%s: %s' % (p, title.text)
        return p

    def body(self, request):
        return '\n'.join([ET.tostring(x) for x in self.x.find('body').getchildren()])


class JhLogsResource(LogsResource):
    def getChild(self, path, req):
        if path == '':
            return Redirect('..')
        for log in self.step_status.getLogs():
            if path == log.getName():
                if log.hasContents():
                    if html5lib and ET and hasattr(log, 'html'):
                        return HTMLLog(log)
                    return IHTMLLog(interfaces.IStatusLog(log))
                return NoResource("Empty Log '%s'" % path)
        return HtmlResource.getChild(self, path, req)

