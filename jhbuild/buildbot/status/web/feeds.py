# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright Lieven Gobaerts
# Copyright (C)  2008 Igalia S.L., John Carr, Frederic Peters
#
#   feeds.py: RSS/Atom feeds
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

# Minor changes made by API (apinheiro@igalia.com) in order to fit with our
# configuration and last buildbot changes

import time, re

from twisted.web.resource import Resource
from twisted.web import html as twhtml

from buildbot.status.builder import FAILURE, SUCCESS, WARNINGS

class XmlResource(Resource):
    contentType = "text/xml; charset=UTF-8"
    def render(self, request):
        data = self.content(request)
        request.setHeader("content-type", self.contentType)
        if request.method == "HEAD":
            request.setHeader("content-length", len(data))
            return ''
        return data
    docType = ''
    def header (self, request):
        data = ('<?xml version="1.0"?>\n')
        return data
    def footer(self, request):
        data = ''
        return data
    def content(self, request):
        data = self.docType
        data += self.header(request)
        data += self.body(request)
        data += self.footer(request)
        return data
    def body(self, request):
        return ''
    def getStatus(self, request):
        return request.site.buildbot_service.getStatus()
    def getControl(self, request):
        return request.site.buildbot_service.getControl()
    def getChangemaster(self, request):
        return request.site.buildbot_service.parent.change_svc

class FeedResource(XmlResource):
    title = 'Dummy (please reload)'
    link = 'http://dummylink'
    language = 'en'
    description = 'Dummy (please reload)'
    status = None

    def __init__(self, categories):
        self.categories = categories

    def getBuilds(self):
        builds = []
        builderNames = self.status.getBuilderNames(categories=self.categories)
        builders = map(lambda name: self.status.getBuilder(name), builderNames)
        maxFeeds = 5

        # Copy all failed builds in a new list.
        # This could clearly be implemented much better if we had access to a global list
        # of builds.
        for b in builders:
            lastbuild = b.getLastFinishedBuild()
            if lastbuild is None:
                continue

#           if b.category != "prod":
#                continue
            lastnr = lastbuild.getNumber()

            totalbuilds = 0
            i = lastnr
            while i >= 0:
                build = b.getBuild(i)
                i -= 1
                if not build:
                    continue

                results = build.getResults()

                # only add entries for failed builds!
                if results == FAILURE:
                    totalbuilds += 1
                    builds.append(build)

                # stop for this builder when our total nr. of feeds is reached
                if totalbuilds >= maxFeeds:
                    break

        # Sort build list by date, youngest first.
#        builds.sort(key=lambda build: build.getTimes(), reverse=True)

        # If you need compatibility with python < 2.4, use this for sorting instead:
          # We apply Decorate-Sort-Undecorate
        deco = [(build.getTimes(), build) for build in builds]
        deco.sort()
        deco.reverse()
        builds = [build for (b1, build) in deco]

        if builds:
            builds = builds[:min(len(builds), maxFeeds)]
        return builds

    def body (self, request):
        data = ''
        self.status = self.getStatus(request)
        self.link = str(self.status.getBuildbotURL())
        projectName = str(self.categories[0])
        self.title = 'Build status of %s' % projectName
        self.description = 'List of FAILed %s builds' % projectName

        builds = self.getBuilds()

        for build in builds:
            start, finished = build.getTimes()
            strFinished = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.localtime(int(finished)))
            link = str(self.status.getURLForThing(build))

            # title: trunk r22191 (plus patch) failed on 'i686-debian-sarge1 shared gcc-3.3.5'
            ss = build.getSourceStamp()
            if ss is None:
                source = "[src unknown]"
            else:
                branch, revision, patch = ss.branch, ss.revision, ss.patch
                source = ""
                if branch:
                    source += "Branch %s " % branch
                if revision:
                    source += "r%s " % str(revision)
                else:
                    source += "trunk"
                if patch is not None:
                    source += " (plus patch)"
            builder_name = build.getBuilder().getName()[len(projectName)+1:]
            title = projectName + ' ' + source + " failed on '" + builder_name + "'"

            # get name of the failed step and the last 30 lines of its log.
            lastlog = ''
            laststep = None
            if build.getLogs():
                log = build.getLogs()[-1]
                laststep = log.getStep().getName()
                try:
                    lastlog = log.getText()
                except IOError:
                    # Probably the log file has been removed
                    lastlog='<b>log file not available</b>'

            lines = re.split('\n', lastlog)
            for logline in lines[max(0, len(lines)-30):]:
                lastlog = lastlog + logline

            description = '<dl>\n'
            description += '<dt>Date</dt><dd>%s</dd>\n' % strFinished
            description += '<dt>Build summary</dt><dd><a href="' + self.link + projectName + '">' + self.link + projectName + '</a></dd>\n'
            description += '<dt>Build details</dt><dd><a href="%s">%s</a></dd>' % (link, link)
            if build.getResponsibleUsers():
                description += '<dt>Author list</dt><dd>' + ', '.join(build.getResponsibleUsers()) + '</dd>\n'
            if laststep:
                description += '<dt>Failed step</dt><dd><b>%s</b></dd>\n' % laststep
            description += '</dl>\n'
            description += '<p>Last lines of the build log:</p>\n'
            description += '<pre>%s</pre>' % twhtml.escape(lastlog)

            data += self.item(title,
                              description = description,
                              link=link,pubDate=strFinished)

        if type(data) is unicode:
            data = data.encode('utf-8', 'ignore')
        return data

    def item(self, title='', link='', description='', pubDate=''):
        """Generates xml for one item in the feed"""

class Rss20StatusResource(FeedResource):
    def __init__(self, categories):
        FeedResource.__init__(self, categories)
        self.contentType = 'application/rss+xml'

    def header(self, request):
        data = FeedResource.header(self, request)
        data += '<rss version="2.0">\n'
        data += '<channel>'
        if self.title is not None:
            data += '<title>'+self.title+'</title>'
        if self.link is not None:
            data += '<link>'+self.link+'</link>'
        if self.language is not None:
            data += '<language>'+self.language+'</language>'
        if self.description is not None:
            data += '<description><![CDATA[%s]]></description>' % self.description
        return data

    def item(self, title='', link='', description='', pubDate=''):
        data = '<item>'
        data += '<title>'+title+'</title>'
        if link is not None:
            data += '<link>'+link+'</link>'
        if description is not None:
            data += '<description><![CDATA[%s]]></description>' % description
        if pubDate is not None:
            data += '<pubDate>'+pubDate+'</pubDate>'
        data += '</item>'
        return data

    def footer(self, request):
        data = ('</channel>'
                '</rss>')
        return data

class Atom10StatusResource(FeedResource):
    def __init__(self, categories):
        FeedResource.__init__(self, categories)
        self.contentType = 'application/atom+xml'

    def header(self, request):
        data = FeedResource.header(self, request)
        data += '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        if self.title is not None:
            data += '<title>'+self.title+'</title>\n'
        if self.link is not None:
            data += '<link href="'+self.link+'"/>\n'
        # if self.language is not None:
            # data += '<language>'+self.language+'</language>'
        if self.description is not None:
            data += '<subtitle>'+self.description+'</subtitle>\n'
        return data

    def item(self, title='', link='', description='', pubDate=''):
        data = '<entry>\n'
        data += '<id>%s</id>\n' % link
        data += '<title>%s</title>\n' % title
        if link is not None:
            data += '<link href="%s"/>\n' % link
        if description is not None:
            data += '<content type="html">%s</content>\n' % twhtml.escape(description)
        if pubDate is not None:
            data += '<updated>%s</updated>\n' % pubDate
        data += '</entry>\n'
        return data

    def footer(self, request):
        data = ('</feed>')
        return data

