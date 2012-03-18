# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008  Frederic Peters
#
#   build.py: custom builder pages
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

from buildbot.status.web.builder import BuildersResource, StatusResourceBuilder
from buildbot.status.web.base import make_row, make_force_build_form, \
             path_to_slave, path_to_builder

from build import JhBuildsResource

class JhStatusResourceBuilder(StatusResourceBuilder):
    def getTitle(self, request):
        buildbot_service = request.site.buildbot_service
        builder_name = self.builder_status.getName()
        for slave in buildbot_service.slaves:
            if builder_name.endswith(slave):
                slave_name = slave
                module_name = builder_name[:-len(slave)-1]
                break
        else:
            slave_name = None
            module_name = None
        status = self.getStatus(request)
        p = status.getProjectName()
        if slave_name:
            return '%s - %s @ %s' % (
                    p, module_name, slave_name)
        return '%s - %s' % (p, builder_name)

    def body(self, req):
        b = self.builder_status
        control = self.builder_control
        status = self.getStatus(req)

        slaves = b.getSlaves()
        connected_slaves = [s for s in slaves if s.isConnected()]

        projectName = status.getProjectName()

        data = ''

        # the first section shows builds which are currently running, if any.
        current = b.getCurrentBuilds()
        if current:
            data += "<h2>Currently Building:</h2>\n"
            data += "<ul>\n"
            for build in current:
                data += " <li>" + self.build_line(build, req) + "</li>\n"
            data += "</ul>\n"
        else:
            data += "<h2>No current builds</h2>\n"

        # Then a section with the last 5 builds, with the most recent build
        # distinguished from the rest.

        data += "<h2>Recent Builds</h2>\n"
        data += "<ul>\n"
        numbuilds = int(req.args.get('numbuilds', ['5'])[0])
        for i,build in enumerate(b.generateFinishedBuilds(num_builds=int(numbuilds))):
            data += " <li>" + self.make_line(req, build, False) + "</li>\n"
            if i == 0:
                data += "<br />\n" # separator
                # TODO: or empty list?
        data += "</ul>\n"

        data += "<h2>Buildslaves:</h2>\n"
        data += "<ol>\n"
        for slave in slaves:
            slaveurl = path_to_slave(req, slave)
            data += "<li><b><a href=\"%s\">%s</a></b>: " % (html.escape(slaveurl), html.escape(slave.getName()))
            if slave.isConnected():
                data += "CONNECTED\n"
                if slave.getAdmin():
                    data += make_row("Admin:", html.escape(slave.getAdmin()))
                if slave.getHost():
                    data += "<span class='label'>Host info:</span>\n"
                    data += html.PRE(html.escape(slave.getHost()))
            else:
                data += ("NOT CONNECTED\n")
            data += "</li>\n"
        data += "</ol>\n"

        if control is not None and connected_slaves:
            forceURL = path_to_builder(req, b) + '/force'
            data += make_force_build_form(forceURL, self.isUsingUserPasswd(req))
        elif control is not None:
            data += """
            <p>All buildslaves appear to be offline, so it's not possible
            to force this build to execute at this time.</p>
            """

        if control is not None:
            pingURL = path_to_builder(req, b) + '/ping'
            data += """
            <form method="post" action="%s" class='command pingbuilder'>
            <p>To ping the buildslave(s), push the 'Ping' button</p>

            <input type="submit" value="Ping Builder" />
            </form>
            """ % pingURL

        return data


    def getChild(self, path, req):
        if path == 'builds':
            return JhBuildsResource(self.builder_status, self.builder_control)
        return StatusResourceBuilder.getChild(self, path, req)


class JhBuildersResource(BuildersResource):
    def getChild(self, path, req):
        if path == '':
            return Redirect('..')
        s = self.getStatus(req)
        if path in s.getBuilderNames():
            builder_status = s.getBuilder(path)
            builder_control = None
            c = self.getControl(req)
            if c:
                builder_control = c.getBuilder(path)
            return JhStatusResourceBuilder(builder_status, builder_control)
        return BuildersResource.getChild(self, path, req)
