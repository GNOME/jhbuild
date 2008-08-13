
from twisted.trial import unittest
from twisted.python import util

from jhbuildbot import changes

class TestGnomeMaildirSource(unittest.TestCase):

    def get(self, msg):
        msg = util.sibpath(__file__, msg)
        s = changes.GnomeMaildirSource(None)
        return s.parse_file(open(msg, "r"))

    def read(self, path):
        path = util.sibpath(__file__, path)
        return open(path).read().rstrip()

    def testMsg1(self):
        c = self.get("mail/svn-commits-list.1")
        self.assertEqual(c.who, "lapo")
        self.assertEqual(c.files, ['trunk/22x22/actions/zoom-fit-best.svg', 'trunk/22x22/actions/zoom-in.svg', 
                                   'trunk/22x22/actions/zoom-original.svg', 'trunk/22x22/actions/zoom-out.svg', 
                                   'trunk/22x22/actions/zoom-fit-best.xcf.bz2', 'trunk/22x22/actions/zoom-in.xcf.bz2', 
				   'trunk/22x22/actions/zoom-original.xcf.bz2', 'trunk/22x22/actions/zoom-out.xcf.bz2', 
				   'trunk/22x22/actions/zoom-fit-best.png', 'trunk/22x22/actions/zoom-in.png', 
				   'trunk/22x22/actions/zoom-original.png', 'trunk/22x22/actions/zoom-out.png', 
				   'trunk/24x24/actions/zoom-fit-best.png', 'trunk/24x24/actions/zoom-in.png', 
				   'trunk/24x24/actions/zoom-original.png', 'trunk/24x24/actions/zoom-out.png', 'trunk/ChangeLog'])
        self.assertEqual(c.comments, 'redid 22x22 zoom actions in svg.')
        self.assertEqual(c.isdir, 0)
        self.assertEqual(c.revision, '1820')
        self.assertEqual(c.links, ['http://svn.gnome.org/viewvc/gnome-icon-theme?rev=1820&view=rev'])

    def testMsg2(self):
        c = self.get("mail/svn-commits-list.2")
        self.assertEqual(c.who, "timj")
        self.assertEqual(c.files, ['trunk/gtk/gtkcontainer.h'])
        self.assertEqual(c.comments, '* gtk/gtkcontainer.h: seal members.')
        self.assertEqual(c.revision, '20514')
        self.assertEqual(c.links, ['http://svn.gnome.org/viewvc/gtk+?rev=20514&view=rev'])

    def testMsg3(self):
        c = self.get("mail/svn-commits-list.3")
        self.assertEqual(c.who, "pohly")
        self.assertEqual(c.files, ['branches/gnome-2-22/calendar/libecal/e-cal-check-timezones.c', 
	                           'branches/gnome-2-22/calendar/libecal/e-cal-check-timezones.h', 
				   'branches/gnome-2-22/calendar/libecal/Makefile.am', 
				   'branches/gnome-2-22/configure.in'])
        self.assertEqual(c.comments, self.read('mail/svn-commits-list.3.comments'))
        self.assertEqual(c.revision, '9023')
        self.assertEqual(c.links, ['http://svn.gnome.org/viewvc/evolution-data-server?rev=9023&view=rev'])

    def testMsg4(self):
        c = self.get("mail/svn-commits-list.4")
        self.assertEqual(c.who, "kmaraas")
        self.assertEqual(c.files, [])
        self.assertEqual(c.comments, '')
        self.assertEqual(c.revision, None)
        self.assertEqual(c.links, [])

    def testMsg5(self):
        c = self.get("mail/svn-commits-list.5")
        self.assertEqual(c.who, "jstowers")
        self.assertEqual(c.files, ['trunk/   (props changed)', 'trunk/conduit/modules/NetworkModule/Peers.py'])
        self.assertEqual(c.comments, 'Send and check the protocol version over the network module. This will require the maemo packages to be updated')
        self.assertEqual(c.revision, '1559')
        self.assertEqual(c.links, ['http://svn.gnome.org/viewvc/conduit?rev=1559&view=rev'])

