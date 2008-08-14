# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2008  apinheiro@igalia.com, John Carr, Frederic Peters
#
#   __init__.py: custom buildbot web pages
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
from twisted.web import server, static, resource
from buildbot.status.web.base import HtmlResource, ITopBox, build_get_class

def content(self, request):
    """
    We want to give /all/ HTMLResource objects this replacement content method
    Monkey patch :)
    """
    s = request.site.buildbot_service
    data = s.template
    data = data.replace('@@GNOME_BUILDBOT_TITLE@@', self.getTitle(request))
    data = data.replace('@@GNOME_BUILDBOT_BODY@@', self.body(request))
    return data
HtmlResource.content = content

from buildbot.status.web.baseweb import WebStatus
from feeder import WaterfallWithFeeds

class ProjectsSummary(HtmlResource):

    MAX_PROJECT_NAME = 25

    def getTitle(self, request):
        return "BuildBot"

    def body(self, request):
        parent = request.site.buildbot_service
        status = self.getStatus(request)

        result = ''
        result += '<table class="ProjectSummary" border="0">\n'

        # Headers
        result += '<thead><tr><td class="empty">&nbsp;</td><td class="empty">&nbsp;</td><th>'+parent.moduleset+'</td>'
        for name in parent.slaves:
                if len(name) > 25:
                    name = name[:25] + "(...)"
                result += '<td colspan="2" class="LeftBorder TopBorder header" align="center"><b>' + name + '</b></td>\n'
        result += '</tr>\n'
        result += '<tr><th></th><th></th><th><b>Project</b></td>\n'
        for i in range(len(parent.slaves)):
                result += '<td class="BottomBorder LeftBorder header" align="center">Last-Build</td>\n'
                result += '<td class="BottomBorder header" align="center">State</td>\n'
        result += '</tr></thead>\n'

        # Contents
	result += '<tbody>'
        for module in parent.modules:
            result += '<tr>'
            result += '<td class="Atom" align="center"><a href="'+module+'/atom">'
            result += '<image src="/feed-atom.png" border="0" alt="Atom"></a></td>'
            result += '<td class="RSS" align="center"><a href="'+module+'/rss">'
            result += '<image src="/feed.png" border="0" alt="RSS"></a></td>\n'
            result += '<th class="BottomBorder LeftBorder ProjectSummaryBuilder"><a href="'+module+'">'+module+'</a></td>'

            for slave in parent.slaves:
                builder = status.getBuilder("%s-%s" % (module, slave))
                box = ITopBox(builder).getBox(request)
                lastbuild = ''
                for bt in box.text:
                    if bt == "successful" or bt == "failed":
                        lastbuild = bt
                if lastbuild == "successful" or lastbuild == "failed":
                    class_ = build_get_class(builder.getLastFinishedBuild())
                else:
                    class_ = ''
                result += '<td align="center" class="BottomBorder LeftBorder '+class_+'">'+lastbuild+'</td>'
                state, builds = builder.getState()
                result += '<td align="center" class="BottomBorder '+state+'">'+state+'</td>'
            result += '</tr>\n'
	result += '</tbody>'
        result += '</table>'

        return result

class JHBuildWebStatus(WebStatus):

    def __init__(self, moduleset, modules, slaves, *args, **kwargs):
        WebStatus.__init__(self, *args, **kwargs)
	self.moduleset = moduleset
	self.modules = modules
	self.slaves = slaves

        # set up the per-module waterfalls
        for module in self.modules:
            self.putChild(module, feeder.WaterfallWithFeeds(categories=[module]))

        # set the summary homepage
        self.putChild("", ProjectsSummary())

    def setupSite(self):
        WebStatus.setupSite(self)

        # load the template into memory
        self.template = open(os.path.join(self.parent.basedir, "template.html")).read()
