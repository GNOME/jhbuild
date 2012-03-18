# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008  Frederic Peters
#
#   step.py: custom step pages
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

import urllib

from twisted.web.util import Redirect
from twisted.web import html

from buildbot.status.web.base import HtmlResource
from buildbot.status.web.step import StepsResource, StatusResourceBuildStep
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION

from logs import JhLogsResource

class JhStatusResourceBuildStep(StatusResourceBuildStep):
    def getTitle(self, request):
        buildbot_service = request.site.buildbot_service
        s = self.step_status
        b = s.getBuild()
        builder_name = b.getBuilder().getName()
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
            return '%s - %s - build #%s @ %s' % (p, module_name, b.getNumber(), slave_name)
        return '%s - %s' % (p, builder_name)

    def body(self, req):
        s = self.step_status
        step_name = s.getName().split(' ')[-1]

        data = ''
        if not s.isFinished():
            data += ('<h2>Not Finished</h2>\n'
                     '<p>ETA %s seconds</p>\n' % s.getETA())
        else:
            r = s.getResults()
            if r[0] in (SUCCESS, WARNINGS):
                data += '<h2 class="success">Finished %s successfully</h2\n' % step_name
            elif r[0] == FAILURE:
                data += '<h2 class="failure">Finished %s unsuccessfully</h2\n' % step_name
            elif r[0] == EXCEPTION:
                data += '<h2 class="exception">Finished %s on an exception</h2\n' % step_name

            if step_name == 'check' and len(s.getText()) > 1 and \
                    s.getResults()[0] in (SUCCESS, WARNINGS):
                data += '<ul>'
                for x in s.getText()[1:]:
                    data += '<li>%s</li>' % x
                data += '</ul>'
            else:
                if len(s.getText()) > 1:
                    data += '<p>%s</p>\n' % ' '.join(s.getText()[1:])

        logs = s.getLogs()
        if logs:
            data += ("<h2>Logs</h2>\n"
                     "<ul>\n")
            for logfile in logs:
                if logfile.hasContents():
                    # FIXME: If the step name has a / in it, this is broken
                    # either way.  If we quote it but say '/'s are safe,
                    # it chops up the step name.  If we quote it and '/'s
                    # are not safe, it escapes the / that separates the
                    # step name from the log number.
                    logname = logfile.getName()
                    logurl = req.childLink("logs/%s" % urllib.quote(logname))
                    data += ('<li><a href="%s">%s</a></li>\n' % 
                             (logurl, html.escape(logname)))
                else:
                    logname = logfile.getName()
                    data += '<li>%s</li>\n' % html.escape(logname)
            data += "</ul>\n"

        return data


    def getChild(self, path, req):
        if path == 'logs':
            return JhLogsResource(self.step_status)
        return HtmlResource.getChild(self, path, req)


class JhStepsResource(StepsResource):
    def getChild(self, path, req):
        if path == '':
            return Redirect('..')
        for s in self.build_status.getSteps():
            if s.getName() == path:
                return JhStatusResourceBuildStep(self.build_status, s)
        return HtmlResource.getChild(self, path, req)

