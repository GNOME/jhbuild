# This file is part of the Buildbot configuration for the Subversion project.
# The original file was created by Lieven Gobaerts
# Minor changes made by API (apinheiro@igalia.com) in order to fit with our
# configuration and last buildbot changes

import urllib, time, re

from twisted.web.resource import Resource
from twisted.application import strports
from twisted.web import server, distrib
from twisted.web import html as twhtml

from buildbot import interfaces
from buildbot.status.builder import FAILURE, SUCCESS, WARNINGS
from buildbot.status.web.waterfall import WaterfallStatusResource

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
    title = 'Dummy'
    link = 'http://dummylink'
    language = 'en'
    description = 'Dummy rss'
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

#	    if b.category != "prod":
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
        self.title = 'Build status of %s' % self.status.getProjectName()
        self.description = 'List of FAILed builds'

        builds = self.getBuilds()

        for build in builds:
            start, finished = build.getTimes()
            strFinished = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.localtime(int(finished)))
            projectName = str(self.status.getProjectName())
            link = str(self.status.getURLForThing(build))

            # title: trunk r22191 (plus patch) failed on 'i686-debian-sarge1 shared gcc-3.3.5'
            ss = build.getSourceStamp()
            if ss is None:
                source = "[src unknown]"
            else:
                branch, revision, patch = ss.branch, ss.revision, ss.patch
                if build.getChanges():
                    revision = max([int(c.revision) for c in build.getChanges()])
                source = ""
                if branch:
                    source += "Branch %s " % branch
                if revision:
                    source += "r%s " % str(revision)
                else:
                    source += "HEAD"
                if patch is not None:
                    source += " (plus patch)"
            title = source + " failed on '" + build.getBuilder().getName() + "'"

            # get name of the failed step and the last 30 lines of its log.
            if build.getLogs():
                log = build.getLogs()[-1]
                laststep = log.getStep().getName()
                try:
                    lastlog = log.getText()
                except IOError:
                    # Probably the log file has been removed
                    lastlog='<b>log file not available</b>'

            lines = re.split('\n', lastlog)
            lastlog = ''
            for logline in lines[max(0, len(lines)-30):]:
                lastlog = lastlog + logline + '<br/>'

            description = '<![CDATA['
            description += 'Date: ' + strFinished + '<br/><br/>'
            description += 'Full details are available at: <br/>'
            description += 'Build summary: <a href="' + self.link + projectName + '">' + self.link + projectName + '</a><br/><br/>'
            description += 'Build details: <a href="' + link + '">' + self.link + link[1:] + '</a><br/><br/>'
            description += 'Author list: <b>' + ",".join(build.getResponsibleUsers()) + '</b><br/><br/>'
            description += 'Failed step: <b>' + laststep + '</b><br/><br/>'
            description += 'Last lines of the build log:<br/>'
            description += lastlog.replace('\n', '<br/>')
            description += ']]>'

            data += self.item(title,
                              description = description,
                              link=link,pubDate=strFinished)

        return data

    def item(self, title='', link='', description='', pubDate=''):
        """Generates xml for one item in the feed"""

class Rss20StatusResource(FeedResource):
    def __init__(self, categories):
        FeedResource.__init__(self, categories)
        contentType = 'application/rss+xml'

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
            data += '<description>'+self.description+'</description>'
        return data

    def item(self, title='', link='', description='', pubDate=''):
        data = '<item>'
        data += '<title>'+title+'</title>'
        if link is not None:
            data += '<link>'+link+'</link>'
        if description is not None:
            data += '<description>'+ description + '</description>'
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
        contentType = 'application/atom+xml'

    def header(self, request):
        data = FeedResource.header(self, request)
        data += '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        if self.title is not None:
            data += '<title>'+self.title+'</title>'
        if self.link is not None:
            data += '<link href="'+self.link+'"/>'
        # if self.language is not None:
            # data += '<language>'+self.language+'</language>'
        if self.description is not None:
            data += '<subtitle>'+self.description+'</subtitle>'
        return data

    def item(self, title='', link='', description='', pubDate=''):
        data = '<entry>'
        data += '<title>'+title+'</title>'
        if link is not None:
            data += '<link href="'+link+'"/>'
        if description is not None:
            data += '<summary type="xhtml">'+ description + '</summary>'
        if pubDate is not None:
            data += '<updated>'+pubDate+'</updated>'
        data += '</entry>'
        return data

    def footer(self, request):
        data = ('</feed>')
        return data

class WaterfallWithFeeds(WaterfallStatusResource):
    """ Override the standard Waterfall class to add RSS and Atom feeds """

    def __init__(self, *args, **kwargs):
        WaterfallStatusResource.__init__(self, *args, **kwargs)

        rss = Rss20StatusResource(self.categories)
        self.putChild("rss", rss)
        atom = Atom10StatusResource(self.categories)
        self.putChild("atom", atom)
