# jhbuild - a tool to ease building collections of source packages
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
from buildbot import interfaces, util
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.status.web.baseweb import WebStatus

from waterfall import JhWaterfallStatusResource
from changes import  ChangesResource
from builder import JhBuildersResource
from bot import JhBuildbotsResource


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


class ListOfModules(resource.Resource):
    def render(self, request):
        data = self.content(request)
        request.setHeader('content-type', 'text/plain')
        if request.method == 'HEAD':
            request.setHeader('content-length', len(data))
            return ''
        return str(data)

    def content(self, request):
        parent = request.site.buildbot_service
        return '\n'.join(parent.modules)


class ProjectsSummary(HtmlResource):

    MAX_PROJECT_NAME = 25

    def getTitle(self, request):
        status = self.getStatus(request)
        p = status.getProjectName()
        return p

    def body(self, request):
        parent = request.site.buildbot_service
        status = self.getStatus(request)

        result = ''
        result += '<table class="ProjectSummary">\n'

        # Headers
        slave_status = {}
        for slave in parent.slaves:
            for module in parent.modules:
                builder = status.getBuilder("%s-%s" % (module, slave))
                state, builds = builder.getState()
                if state == 'offline':
                    slave_status[slave] = ('offline', [])
                    break
                elif state == 'building':
                    if slave in slave_status:
                        modules = slave_status[slave][1] or []
                        slave_status[slave] = (state, modules + [module])
                    else:
                        slave_status[slave] = (state, [module])
            else:
                if not slave in slave_status:
                    slave_status[slave] = ('idle', None)

        if type(parent.moduleset) is list:
            moduleset = ', '.join(parent.moduleset)
        else:
            moduleset = parent.moduleset
        result += '<thead><tr><td>&nbsp;</td><th>' + moduleset + '</td>'
        for name in parent.slaves:
            if len(name) > 25:
                name = name[:25] + '(...)'
            klass, modules = slave_status.get(name)
            if klass == 'building':
                title = 'Building %s' % ', '.join(modules)
            else:
                title = klass
            result += '<th class="%s" title="%s"><a href="bots/%s">%s</a></th>' % (
                    klass, title, name, name)
        result += '</tr>'
        thead = result
        # stop it here as a row with totals will be added here once every rows
        # have been handled

        # Contents
        result = '<tbody>'

        slave_results = {}
        for slave in parent.slaves:
            slave_results[slave] = [0, 0, 0]

        for module in parent.modules:
            result += '<tr>'
            result += '<td class="feed"><a href="%s/atom">' % module
            result += '<img src="/feed.png" alt="Atom"></a></td>\n'
            result += '<th><a href="%s">%s</a></td>' % (module, module)

            for slave in parent.slaves:
                builder = status.getBuilder("%s-%s" % (module, slave))
                box = ITopBox(builder).getBox(request)
                lastbuild = ''
                for bt in box.text:
                    if bt == 'successful' or bt == 'failed':
                        lastbuild = bt

                if lastbuild == 'successful':
                    last_build = builder.getLastFinishedBuild()
                    if last_build:
                        class_ = build_get_class(last_build)
                    else:
                        class_ = 'success'
                    lastbuild_label = 'Success'
                    if last_build and class_:
                        # use a different class/label if make check failed
                        steps = last_build.getSteps()
                        for step in reversed(steps):
                            if step.name.split()[-1] == 'check':
                                if step.results == WARNINGS:
                                    # make check failed
                                    class_ = 'failedchecks'
                                    lastbuild_label = 'Failed Checks'
                                break
                elif lastbuild == 'failed':
                    lastbuild_label = 'Failed'
                    last_build = builder.getLastFinishedBuild()
                    if last_build:
                        class_ = build_get_class(last_build)
                    else:
                        class_ = 'failure'
                else:
                    class_ = ''
                    lastbuild_label = lastbuild
                state, builds = builder.getState()
                if state == 'building':
                    result += '<td class="%s">%s</td>' % (state, state)
                else:
                    result += '<td class="%s">%s</td>' % (class_, lastbuild_label)
                
                if lastbuild in ('failed', 'successful'):
                    slave_results[slave][2] += 1
                    if class_ == 'failedchecks':
                        slave_results[slave][1] += 1
                    elif lastbuild == 'successful':
                        slave_results[slave][0] += 1
                        slave_results[slave][1] += 1

            result += '</tr>\n'
        result += '</tbody>\n'
        result += '<tfoot><tr class="totals"><td colspan="2"></td>'
        thead += '<tr class="totals"><td colspan="2"></td>'
        for slave in parent.slaves:
            td = '<td><span title="Successful builds">%s</span> '\
                      '<span title="(ignoring test suites failures)">(%s)</span> / '\
                      '<span title="Total">%s</span></td>' % tuple(slave_results[slave])
            thead += td
            result += td
        thead += '</tr>\n</thead>\n'
        result += '</tr></tfoot>\n'
        result += '</table>'

        return thead+result

class JHBuildWebStatus(WebStatus):

    def __init__(self, moduleset, modules, slaves, *args, **kwargs):
        WebStatus.__init__(self, *args, **kwargs)
        self.moduleset = moduleset
        self.modules = modules
        self.slaves = slaves

        # set up the per-module waterfalls
        for module in self.modules:
            self.putChild(module, JhWaterfallStatusResource(categories=[module]))

        # set the summary homepage
        self.putChild("", ProjectsSummary())

        # set custom changes pages
        self.putChild('changes', ChangesResource())
        self.putChild('builders', JhBuildersResource())
        self.putChild('bots', JhBuildbotsResource())

        # and more pages
        self.putChild('modules.txt', ListOfModules())

    def setupSite(self):
        WebStatus.setupSite(self)

        # load the template into memory
        self.template = open(os.path.join(self.parent.basedir, "template.html")).read()
