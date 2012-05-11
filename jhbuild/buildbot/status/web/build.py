# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008  Frederic Peters
#
#   build.py: custom build pages
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

from buildbot.status.web.build import BuildsResource, StatusResourceBuild
from buildbot.status.web.base import HtmlResource, make_row, make_stop_form, \
     css_classes, make_name_user_passwd_form

from step import JhStepsResource


class JhStatusResourceBuild(StatusResourceBuild):
    def getTitle(self, request):
        buildbot_service = request.site.buildbot_service
        builder_name = self.build_status.getBuilder().getName()
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
            return '%s - %s - build #%s @ %s' % (
                    p, module_name, self.build_status.getNumber(), slave_name)
        return '%s - %s' % (p, builder_name)

    def body(self, req):
        b = self.build_status
        status = self.getStatus(req)
        projectURL = status.getProjectURL()
        projectName = status.getProjectName()
        data = ''

        if not b.isFinished():
            data += '<h2>Build In Progress</h2>'
            when = b.getETA()
            if when is not None:
                when_time = time.strftime('%H:%M:%S',
                                          time.localtime(time.time() + when))
                data += '<div>ETA %ds (%s)</div>\n' % (when, when_time)

            if self.build_control is not None:
                stopURL = urllib.quote(req.childLink("stop"))
                data += make_stop_form(stopURL, self.isUsingUserPasswd(req))

        if b.isFinished():
            results = b.getResults()
            data += "<h2>Results: "
            text = " ".join(b.getText())
            data += '<span class="%s">%s</span>' % (css_classes[results], text)
            data += '</h2>\n'
            if b.getTestResults():
                url = req.childLink("tests")
                data += "<h3><a href=\"%s\">test results</a></h3>\n" % url

        data += '<ul>\n'
        ss = b.getSourceStamp()
        data += " <li>SourceStamp: "
        data += " <ul>\n"
        if ss.branch:
            data += "  <li>Branch: %s</li>\n" % html.escape(ss.branch)
        if ss.revision:
            data += "  <li>Revision: %s</li>\n" % html.escape(str(ss.revision))
        if ss.patch:
            data += "  <li>Patch: YES</li>\n" # TODO: provide link to .diff
        if ss.changes:
            data += "  <li>Changes: see below</li>\n"
        if (ss.branch is None and ss.revision is None and ss.patch is None
            and not ss.changes):
            data += "  <li>build of most recent revision</li>\n"
        got_revision = None
        try:
            got_revision = b.getProperty("got_revision")
        except KeyError:
            pass
        if got_revision:
            got_revision = str(got_revision)
            if len(got_revision) > 40:
                got_revision = "[revision string too long]"
            data += "  <li>Got Revision: %s</li>\n" % got_revision
        data += " </ul>\n"

        data += "<li>Buildslave: %s</li>\n" % html.escape(b.getSlavename())
        data += "<li>Reason: %s</li>\n" % html.escape(b.getReason())

        if b.getLogs():
            data += "<li>Steps and Logfiles:\n"
            data += "<ol>\n"
            for s in b.getSteps():
                name = s.getName()
                data += (" <li><a href=\"%s\">%s</a> [%s]\n"
                         % (req.childLink("steps/%s" % urllib.quote(name)),
                            name,
                            " ".join(s.getText())))
                if s.getLogs():
                    data += "  <ul>\n"
                    for logfile in s.getLogs():
                        logname = logfile.getName()
                        logurl = req.childLink("steps/%s/logs/%s" %
                                               (urllib.quote(name),
                                                urllib.quote(logname)))
                        data += ("   <li><a href=\"%s\">%s</a></li>\n" %
                                 (logurl, logfile.getName()))
                    data += "  </ul>\n"
                data += " </li>\n"
            data += "</ol>\n"
            data += "</li>\n"

        data += "<li>Blamelist: "
        if list(b.getResponsibleUsers()):
            data += " <ol>\n"
            for who in b.getResponsibleUsers():
                data += "  <li>%s</li>\n" % html.escape(who)
            data += " </ol>\n"
        else:
            data += "no responsible users\n"
        data += '</li>'

        if ss.changes:
            data += "<li>All changes\n"
            data += "<ol>\n"
            for c in ss.changes:
                data += '<li class="changeset">' + c.asHTML() + '</li>\n'
            data += "</ol></li>\n"

        data += '</ul>'

        if b.isFinished() and self.builder_control is not None:
            data += "<h3>Resubmit Build:</h3>\n"
            # can we rebuild it exactly?
            exactly = (ss.revision is not None) or b.getChanges()
            if exactly:
                data += ("<p>This tree was built from a specific set of \n"
                         "source files, and can be rebuilt exactly</p>\n")
            else:
                data += ("<p>This tree was built from the most recent "
                         "revision")
                if ss.branch:
                    data += " (along some branch)"
                data += (" and thus it might not be possible to rebuild it \n"
                         "exactly. Any changes that have been committed \n"
                         "after this build was started <b>will</b> be \n"
                         "included in a rebuild.</p>\n")
            rebuildURL = urllib.quote(req.childLink("rebuild"))
            data += ('<form method="post" action="%s" class="command rebuild">\n'
                     % rebuildURL)
            data += make_name_user_passwd_form(self.isUsingUserPasswd(req))
            data += make_row("Reason for re-running build:",
                             "<input type='text' name='comments' />")
            data += '<input type="submit" value="Rebuild" />\n'
            data += '</form>\n'

        data += '</div>\n'

        return data

    def getChild(self, path, req):
        if path == 'steps':
            return JhStepsResource(self.build_status)
        return StatusResourceBuild.getChild(self, path, req)


class JhBuildsResource(BuildsResource):
    def getChild(self, path, req):
        if path == '':
            return Redirect('..')
        try:
            num = int(path)
        except ValueError:
            num = None
        if num is not None:
            build_status = self.builder_status.getBuild(num)
            if build_status:
                if self.builder_control:
                    build_control = self.builder_control.getBuild(num)
                else:
                    build_control = None
                return JhStatusResourceBuild(build_status, build_control,
                                           self.builder_control)

        return HtmlResource.getChild(self, path, req)

