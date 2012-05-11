# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008  Igalia S.L., John Carr, Frederic Peters
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
#
# heavily based on buildbot code,
#   Copyright (C) Brian Warner <warner-buildbot@lothar.com>

import time, urllib

from buildbot import version
from buildbot.changes.changes import Change
from buildbot import interfaces, util
from buildbot.status import builder
from buildbot.status.web.waterfall import WaterfallStatusResource, Spacer

from buildbot.status.web.base import Box, HtmlResource, IBox, ICurrentBox, \
     ITopBox, td, build_get_class, path_to_build, path_to_step, map_branches

from feeds import Rss20StatusResource, Atom10StatusResource

def insertGaps(g, lastEventTime, idleGap=2, showEvents=False):
    # summary of changes between this function and the one from buildbot:
    #  - do not insert time gaps for events that are not shown
    debug = False

    e = g.next()
    starts, finishes = e.getTimes()
    if debug: log.msg("E0", starts, finishes)
    if finishes == 0:
        finishes = starts
    if debug: log.msg("E1 finishes=%s, gap=%s, lET=%s" % \
                      (finishes, idleGap, lastEventTime))
    if finishes is not None and finishes + idleGap < lastEventTime:
        if debug: log.msg(" spacer0")
        yield Spacer(finishes, lastEventTime)

    followingEventStarts = starts
    if debug: log.msg(" fES0", starts)
    yield e

    while 1:
        e = g.next()
        if isinstance(e, builder.Event) and not showEvents:
            continue
        starts, finishes = e.getTimes()
        if debug: log.msg("E2", starts, finishes)
        if finishes == 0:
            finishes = starts
        if finishes is not None and finishes + idleGap < followingEventStarts:
            # there is a gap between the end of this event and the beginning
            # of the next one. Insert an idle event so the waterfall display
            # shows a gap here.
            if debug:
                log.msg(" finishes=%s, gap=%s, fES=%s" % \
                        (finishes, idleGap, followingEventStarts))
            yield Spacer(finishes, followingEventStarts)
        yield e
        followingEventStarts = starts
        if debug: log.msg(" fES1", starts)


class JhWaterfallStatusResource(WaterfallStatusResource):
    """ Override the standard Waterfall class to add RSS and Atom feeds """

    def __init__(self, *args, **kwargs):
        WaterfallStatusResource.__init__(self, *args, **kwargs)

        rss = Rss20StatusResource(self.categories)
        self.putChild("rss", rss)
        atom = Atom10StatusResource(self.categories)
        self.putChild("atom", atom)

        self.module_name = self.categories[0]

    def getTitle(self, request):
        status = self.getStatus(request)
        p = status.getProjectName()
        if p:
            return '%s: %s' % (p, self.module_name)
        else:
            return "BuildBot"

 
    def buildGrid(self, request, builders):
        # summary of changes between this method and the overriden one:
        #  - don't show events (master started...) by default
        #  - only display changes related to the current module
        debug = False
        # TODO: see if we can use a cached copy

        showEvents = False
        if request.args.get("show_events", ["false"])[0].lower() == "true":
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
            gen = insertGaps(s.eventGenerator(filterBranches), lastEventTime, showEvents)
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

                    # Fixing event text (removing module name at the start)
                    t = event.getText()
                    if t and t[0].startswith(self.module_name):
                        text = t[0][len(self.module_name)+1:]
                        if text == 'updated':
                            text = 'update'
                        event.setText([text] + t[1:])

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


    def body(self, request):
        # summary of changes between this method and the overriden one:
        #  - more structural markup and CSS
        #  - removal of the phase stuff, only keep one
        "This method builds the main waterfall display."

        status = self.getStatus(request)
        data = ''

        projectName = status.getProjectName()
        projectURL = status.getProjectURL()

        # we start with all Builders available to this Waterfall: this is
        # limited by the config-file -time categories= argument, and defaults
        # to all defined Builders.
        allBuilderNames = status.getBuilderNames(categories=self.categories)
        builders = [status.getBuilder(name) for name in allBuilderNames]

        # but if the URL has one or more builder= arguments (or the old show=
        # argument, which is still accepted for backwards compatibility), we
        # use that set of builders instead. We still don't show anything
        # outside the config-file time set limited by categories=.
        showBuilders = request.args.get("show", [])
        showBuilders.extend(request.args.get("builder", []))
        if showBuilders:
            builders = [b for b in builders if b.name in showBuilders]

        # now, if the URL has one or category= arguments, use them as a
        # filter: only show those builders which belong to one of the given
        # categories.
        showCategories = request.args.get("category", [])
        if showCategories:
            builders = [b for b in builders if b.category in showCategories]

        builderNames = [b.name for b in builders]

        (changeNames, builderNames, timestamps, eventGrid, sourceEvents) = \
                      self.buildGrid(request, builders)

        # start the table: top-header material
        data += '<table class="waterfall">\n'
        data += '<thead>\n'
        data += '<tr>\n'
        data += '<td colspan="2"></td>'
        for b in builders:
            state, builds = b.getState()
            builder_name = b.name[len(self.module_name)+1:]
            data += '<th class="%s" title="%s"><a href="%s">%s</a></th>' % (
                    state, state,
                    request.childLink('../builders/%s' % urllib.quote(b.name, safe='')),
                    builder_name)
        data += '</tr>\n'

        data += '<tr>'
        data += '<th>time<br/>(%s)</th>' % time.tzname[time.localtime()[-1]]
        data += '<th class="Change">changes</th>'

        for b in builders:
            box = ITopBox(b).getBox(request)
            data += box.td(align="center")
        data += '</tr>'

        data += '</thead>'

        data += '<tbody>'

        data += self.phase2(request, changeNames + builderNames, timestamps, eventGrid,
                  sourceEvents)

        data += '</tbody>\n'

        data += '<tfoot>\n'

        def with_args(req, remove_args=[], new_args=[], new_path=None):
            # sigh, nevow makes this sort of manipulation easier
            newargs = req.args.copy()
            for argname in remove_args:
                newargs[argname] = []
            if "branch" in newargs:
                newargs["branch"] = [b for b in newargs["branch"] if b]
            for k,v in new_args:
                if k in newargs:
                    newargs[k].append(v)
                else:
                    newargs[k] = [v]
            newquery = "&".join(["%s=%s" % (k, v)
                                 for k in newargs
                                 for v in newargs[k]
                                 ])
            if new_path:
                new_url = new_path
            elif req.prepath:
                new_url = req.prepath[-1]
            else:
                new_url = ''
            if newquery:
                new_url += "?" + newquery
            return new_url

        if timestamps:
            data += '<tr>'
            bottom = timestamps[-1]
            nextpage = with_args(request, ["last_time"],
                                 [("last_time", str(int(bottom)))])
            data += '<td class="Time"><a href="%s">next page</a></td>\n' % nextpage
            data += '</tr>'

        data += '</tfoot>\n'
        data += "</table>\n"

        return data


 
    def phase2(self, request, sourceNames, timestamps, eventGrid,
               sourceEvents):
        data = ""
        if not timestamps:
            return data
        # first pass: figure out the height of the chunks, populate grid
        grid = []
        for i in range(1+len(sourceNames)):
            grid.append([])
        # grid is a list of columns, one for the timestamps, and one per
        # event source. Each column is exactly the same height. Each element
        # of the list is a single <td> box.
        lastDate = time.strftime("<b>%Y-%m-%d</b>",
                                 time.localtime(util.now()))
        for r in range(0, len(timestamps)):
            chunkstrip = eventGrid[r]
            # chunkstrip is a horizontal strip of event blocks. Each block
            # is a vertical list of events, all for the same source.
            assert(len(chunkstrip) == len(sourceNames))
            maxRows = reduce(lambda x,y: max(x,y),
                             map(lambda x: len(x), chunkstrip))
            for i in range(maxRows):
                if i != maxRows-1:
                    grid[0].append(None)
                else:
                    # timestamp goes at the bottom of the chunk
                    stuff = []
                    # add the date at the beginning (if it is not the same as
                    # today's date), and each time it changes
                    today = time.strftime("<b>%Y-%m-%d</b>",
                                          time.localtime(timestamps[r]))
                    if today != lastDate:
                        stuff.append(today)
                        lastDate = today
                    stuff.append(
                        time.strftime("%H:%M:%S",
                                      time.localtime(timestamps[r])))
                    grid[0].append(Box(text=stuff, class_="Time",
                                       valign="bottom", align="center"))

            # at this point the timestamp column has been populated with
            # maxRows boxes, most None but the last one has the time string
            for c in range(0, len(chunkstrip)):
                block = chunkstrip[c]
                assert(block != None) # should be [] instead
                for i in range(maxRows - len(block)):
                    # fill top of chunk with blank space
                    grid[c+1].append(None)
                for i in range(len(block)):
                    # so the events are bottom-justified
                    b = IBox(block[i]).getBox(request)
                    b.parms['valign'] = "top"
                    b.parms['align'] = "center"
                    grid[c+1].append(b)
            # now all the other columns have maxRows new boxes too
        # populate the last row, if empty
        gridlen = len(grid[0])
        for i in range(len(grid)):
            strip = grid[i]
            assert(len(strip) == gridlen)
            if strip[-1] == None:
                if sourceEvents[i-1]:
                    filler = IBox(sourceEvents[i-1]).getBox(request)
                else:
                    # this can happen if you delete part of the build history
                    filler = Box(text=["?"], align="center")
                strip[-1] = filler
            strip[-1].parms['rowspan'] = 1
        # second pass: bubble the events upwards to un-occupied locations
        # Every square of the grid that has a None in it needs to have
        # something else take its place.
        noBubble = request.args.get("nobubble",['0'])
        noBubble = int(noBubble[0])
        if not noBubble:
            for col in range(len(grid)):
                strip = grid[col]
                if col == 1: # changes are handled differently
                    for i in range(2, len(strip)+1):
                        # only merge empty boxes. Don't bubble commit boxes.
                        if strip[-i] == None:
                            next = strip[-i+1]
                            assert(next)
                            if next:
                                #if not next.event:
                                if next.spacer:
                                    # bubble the empty box up
                                    strip[-i] = next
                                    strip[-i].parms['rowspan'] += 1
                                    strip[-i+1] = None
                                else:
                                    # we are above a commit box. Leave it
                                    # be, and turn the current box into an
                                    # empty one
                                    strip[-i] = Box([], rowspan=1,
                                                    comment="commit bubble")
                                    strip[-i].spacer = True
                            else:
                                # we are above another empty box, which
                                # somehow wasn't already converted.
                                # Shouldn't happen
                                pass
                else:
                    for i in range(2, len(strip)+1):
                        # strip[-i] will go from next-to-last back to first
                        if strip[-i] == None:
                            # bubble previous item up
                            assert(strip[-i+1] != None)
                            strip[-i] = strip[-i+1]
                            strip[-i].parms['rowspan'] += 1
                            strip[-i+1] = None
                        else:
                            strip[-i].parms['rowspan'] = 1
        # third pass: render the HTML table
        for i in range(gridlen):
            data += " <tr>\n";
            for strip in grid:
                b = strip[i]
                if b:
                    data += b.td()
                else:
                    if noBubble:
                        data += td([])
                # Nones are left empty, rowspan should make it all fit
            data += " </tr>\n"
        return data

