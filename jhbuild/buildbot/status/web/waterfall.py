# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2008  apinheiro@igalia.com, John Carr, Frederic Peters
#
#   waterfall.py: custom waterfall display
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

from buildbot.changes.changes import Change
from buildbot import interfaces, util
from buildbot.status import builder
from buildbot.status.web.waterfall import WaterfallStatusResource, insertGaps

from buildbot.status.web.base import Box, HtmlResource, IBox, ICurrentBox, \
     ITopBox, td, build_get_class, path_to_build, path_to_step, map_branches

from feeds import Rss20StatusResource, Atom10StatusResource


class JhWaterfallStatusResource(WaterfallStatusResource):
    """ Override the standard Waterfall class to add RSS and Atom feeds """

    def __init__(self, *args, **kwargs):
        WaterfallStatusResource.__init__(self, *args, **kwargs)

        rss = Rss20StatusResource(self.categories)
        self.putChild("rss", rss)
        atom = Atom10StatusResource(self.categories)
        self.putChild("atom", atom)

 
    def buildGrid(self, request, builders):
        debug = False
        # TODO: see if we can use a cached copy

        showEvents = False
        if request.args.get("show_events", ["true"])[0].lower() == "true":
            showEvents = True
        filterBranches = [b for b in request.args.get("branch", []) if b]
        filterBranches = map_branches(filterBranches)
        maxTime = int(request.args.get("last_time", [util.now()])[0])
        if "show_time" in request.args:
            minTime = maxTime - int(request.args["show_time"][0])
        elif "first_time" in request.args:
            minTime = int(request.args["first_time"][0])
        else:
            minTime = None
        spanLength = 10  # ten-second chunks
        maxPageLen = int(request.args.get("num_events", [200])[0])

        # first step is to walk backwards in time, asking each column
        # (commit, all builders) if they have any events there. Build up the
        # array of events, and stop when we have a reasonable number.
            
        commit_source = self.getChangemaster(request)

        lastEventTime = util.now()
        sources = [commit_source] + builders
        changeNames = ["changes"]
        builderNames = map(lambda builder: builder.getName(), builders)
        sourceNames = changeNames + builderNames
        sourceEvents = []
        sourceGenerators = []
        projectName = str(self.categories[0])

        def get_event_from(g):
            try:
                while True:
                    e = g.next()
                    # e might be builder.BuildStepStatus,
                    # builder.BuildStatus, builder.Event,
                    # waterfall.Spacer(builder.Event), or changes.Change .
                    # The showEvents=False flag means we should hide
                    # builder.Event .
                    if not showEvents and isinstance(e, builder.Event):
                        continue
                    if isinstance(e, Change) and hasattr(e, 'project') and \
                            e.project != projectName:
                        continue
                    break
                event = interfaces.IStatusEvent(e)
                if debug:
                    log.msg("gen %s gave1 %s" % (g, event.getText()))
            except StopIteration:
                event = None
            return event

        for s in sources:
            gen = insertGaps(s.eventGenerator(filterBranches), lastEventTime)
            sourceGenerators.append(gen)
            # get the first event
            sourceEvents.append(get_event_from(gen))
        eventGrid = []
        timestamps = []

        lastEventTime = 0
        for e in sourceEvents:
            if e and e.getTimes()[0] > lastEventTime:
                lastEventTime = e.getTimes()[0]
        if lastEventTime == 0:
            lastEventTime = util.now()

        spanStart = lastEventTime - spanLength
        debugGather = 0

        while 1:
            if debugGather: log.msg("checking (%s,]" % spanStart)
            # the tableau of potential events is in sourceEvents[]. The
            # window crawls backwards, and we examine one source at a time.
            # If the source's top-most event is in the window, is it pushed
            # onto the events[] array and the tableau is refilled. This
            # continues until the tableau event is not in the window (or is
            # missing).

            spanEvents = [] # for all sources, in this span. row of eventGrid
            firstTimestamp = None # timestamp of first event in the span
            lastTimestamp = None # last pre-span event, for next span

            for c in range(len(sourceGenerators)):
                events = [] # for this source, in this span. cell of eventGrid
                event = sourceEvents[c]
                while event and spanStart < event.getTimes()[0]:
                    # to look at windows that don't end with the present,
                    # condition the .append on event.time <= spanFinish
                    if not IBox(event, None):
                        log.msg("BAD EVENT", event, event.getText())
                        assert 0
                    if debug:
                        log.msg("pushing", event.getText(), event)
                    events.append(event)
                    starts, finishes = event.getTimes()
                    firstTimestamp = util.earlier(firstTimestamp, starts)
                    event = get_event_from(sourceGenerators[c])
                if debug:
                    log.msg("finished span")

                if event:
                    # this is the last pre-span event for this source
                    lastTimestamp = util.later(lastTimestamp,
                                               event.getTimes()[0])
                if debugGather:
                    log.msg(" got %s from %s" % (events, sourceNames[c]))
                sourceEvents[c] = event # refill the tableau
                spanEvents.append(events)

            # only show events older than maxTime. This makes it possible to
            # visit a page that shows what it would be like to scroll off the
            # bottom of this one.
            if firstTimestamp is not None and firstTimestamp <= maxTime:
                eventGrid.append(spanEvents)
                timestamps.append(firstTimestamp)

            if lastTimestamp:
                spanStart = lastTimestamp - spanLength
            else:
                # no more events
                break
            if minTime is not None and lastTimestamp < minTime:
                break

            if len(timestamps) > maxPageLen:
                break
            
            
            # now loop
            
        # loop is finished. now we have eventGrid[] and timestamps[]
        if debugGather: log.msg("finished loop")
        assert(len(timestamps) == len(eventGrid))
        return (changeNames, builderNames, timestamps, eventGrid, sourceEvents)

