# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2002  James Henstridge
#
#   moduleinfo.py: rules for building various GNOME modules.
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

from module import Module, MetaModule, ModuleSet

def sfcvsroot(project):
    return ':pserver:anonymous@cvs.%s.sourceforge.net:/cvsroot/%s' % \
           (project, project)

thinice_cvsroot     = sfcvsroot('thinice')
gstreamer_cvsroot   = sfcvsroot('gstreamer')
fileroller_cvsroot   = sfcvsroot('fileroller')
gael_cvsroot        = sfcvsroot('gael')
codefactory_cvsroot = ':pserver:anoncvs@cvs.codefactory.se:/cvs'

# gnome 2.0 support
gnome20 = ModuleSet()

gnome2 = gnome20

gnome20.addmod('intltool')
gnome20.addmod('gnome-common', revision='gnome-2-0',)
gnome20.addmod('gtk-doc', dependencies=['libxslt'])
gnome20.addmod('glib', revision='glib-2-0', dependencies=['gtk-doc'])
gnome20.addmod('pango', revision='pango-1-0', dependencies=['glib'])
gnome20.addmod('atk', dependencies=['glib'])
gnome20.addmod('gtk+', revision='gtk-2-0', dependencies=['pango', 'atk'],
               autogenargs='--with-qt=no')
gnome20.addmod('gail', revision='gnome-2-0',
               dependencies=['gtk+', 'atk', 'libgnomecanvas'])
gnome20.addmod('gtkhtml2', revision='gnome-2-0',
               dependencies=['gtk+', 'gnome-xml', 'gail'])
gnome20.addmod('gnome-xml',  checkoutdir='libxml2')
gnome20.addmod('libxslt', dependencies=['gnome-xml'])
gnome20.addmod('linc', dependencies=['glib'])
gnome20.addmod('libIDL', dependencies=['glib'])
gnome20.addmod('ORBit2', dependencies=['linc', 'libIDL'])
gnome20.addmod('bonobo-activation',
               dependencies=['intltool', 'gnome-common', 'ORBit2',
                             'gnome-xml'])
gnome20.addmod('gconf', dependencies=['ORBit2', 'gnome-xml', 'gtk+'],
               revision='gconf-1-2')
gnome20.addmod('libbonobo', dependencies=['ORBit2', 'bonobo-activation'])
gnome20.addmod('gnome-mime-data', dependencies=['gnome-common'])
gnome20.addmod('gnome-vfs', revision='gnome-2-0',
               dependencies=['libbonobo','gconf', 'gnome-mime-data'])
gnome20.addmod('libart_lgpl')
gnome20.addmod('libgnome', revision='gnome-2-0',
               dependencies=['gnome-xml', 'libxslt', 'libbonobo', 'gnome-vfs',
                             'gconf'])
gnome20.addmod('libgnomecanvas', revision='gnome-2-0',
               dependencies=['gtk+', 'libart_lgpl', 'libglade', 'gnome-common'])
gnome20.addmod('libbonoboui',
               dependencies=['libgnome', 'libbonobo', 'libgnomecanvas',
                             'libglade'])
gnome20.addmod('libgnomeui', revision='gnome-2-0',
               dependencies=['libbonoboui', 'libglade'])

gnome20.addmod('libzvt', dependencies=['libart_lgpl', 'gtk+', 'gnome-common'])
gnome20.addmod('libglade', revision='gnome-2-0',
               dependencies=['gtk+', 'gnome-xml'])
gnome20.addmod('gnome-python/pygtk', dependencies=['gtk+', 'libglade'])
gnome20.addmod('orbit-python', dependencies=['libIDL', 'ORBit2'])
gnome20.addmod('gnome-python/gnome-python',
               dependencies=['gnome-python/pygtk', 'libgnomecanvas',
                             'libgnomeui'])
gnome20.addmod('bug-buddy', dependencies=['libgnomeui'])
gnome20.addmod('libwnck', dependencies=['gtk+'], revision='gnome-2-0')

gnome20.addmod('gnome-panel', revision='gnome-2-0',
               dependencies=['libgnomeui','gnome-desktop'])
gnome20.addmod('gnome-desktop', revision='gnome-2-0',
               dependencies=['libgnomeui', 'libwnck'])
gnome20.addmod('gnome-session', revision='gnome-2-0',
               dependencies=['libgnomeui', 'libwnck'])

gnome20.addmod('gnome-applets', revision='gnome-2-0',
               dependencies=['gnome-panel','libgtop', 'gail'])
gnome20.addmod('gnome-games', revision='gnome-2-0',
               dependencies=['libgnomeui'])
gnome20.addmod('eel', revision='gnome-2-0',
               dependencies=['librsvg','libgnomeui','gail'])
gnome20.addmod('librsvg', revision='gnome-2-0',
               dependencies=['gnome-xml','gtk+', 'libart_lgpl',
                             'gnome-common'])
gnome20.addmod('nautilus', revision='gnome-2-0',
               dependencies=['esound', 'eel', 'librsvg', 'libgnomeui',
                             'gnome-desktop'])
gnome20.addmod('nautilus-gtkhtml', dependencies=['nautilus', 'gtkhtml2'])
gnome20.addmod('metacity', dependencies=['gtk+','gconf','intltool','libglade'])
gnome20.addmod('metatheme', dependencies=['libgnomeui'])
gnome20.addmod('libgtop', revision='libgtop-GNOME-2-0-port',
               dependencies=['glib'])
gnome20.addmod('procman', dependencies=['libgnomeui','libwnck','libgtop'])
gnome20.addmod('gnome-control-center', revision='gnome-2-0',
               dependencies=['libgnomeui', 'esound', 'gnome-desktop'])
gnome20.addmod('yelp', revision='gnome-2-0',
               dependencies=['libgnomeui', 'gtkhtml2', 'gnome-vfs'])
gnome20.addmod('devhelp',
               dependencies=['libgnomeui', 'gtkhtml2', 'gnome-vfs'])
gnome20.addmod('gnome-utils', revision='gnome-2-0',
               dependencies=['libgnomeui', 'gnome-panel'])
gnome20.addmod('gconf-editor', dependencies=['gconf'])
gnome20.addmod('esound')
gnome20.addmod('gnome-media', dependencies=['libgnomeui', 'esound', 'gail'])
gnome20.addmod('gdm2', dependencies=['librsvg'])
gnome20.addmod('gnome-terminal', revision='gnome-2-0',
               dependencies=['libglade', 'libgnomeui', 'libzvt'])
gnome20.addmod('gtk-engines', dependencies=['gtk+'])
gnome20.addmod('gedit', dependencies=['libgnomeui', 'libgnomeprintui'])
gnome20.addmod('libgnomeprint', revision='gnome-2-0',
               dependencies=['libbonobo', 'libart_lgpl'])
gnome20.addmod('libgnomeprintui', revision='gnome-2-0',
               dependencies=['libgnomeprint'])
gnome20.addmod('memprof', dependencies=['libgnomeui'])
gnome20.addmod('eog', dependencies=['libgnomeui', 'libgnomeprint'])
gnome20.addmod('gal', revision='gal-2', dependencies=['libgnomeui'])
gnome20.addmod('libole2', dependencies=['glib','gnome-xml'])
gnome20.addmod('libgsf', dependencies=['glib'])
gnome20.addmod('gnumeric', dependencies=['libole2', 'libgsf', 'gal'])

gnome20.addmod('gimp',dependencies=['gtk+', 'libart_lgpl'],
               autogenargs='--disable-print')
gnome20.addmod('gimp-freetype', dependencies=['gimp'])

gnome20.addmod('glade', revision='glade-gnome2-branch',
               dependencies=['gtk+', 'gnome-xml', 'libgnomeui',
                             'libgnomeprintui'])
gnome20.addmod('glade2c', dependencies=['gtk+', 'gnome-xml', 'libgnomeui'])
gnome20.addmod('gtkglarea', dependencies=['gtk+'])

gnome20.addmod('sawfish', revision='gnome-2', dependencies=['rep-gtk'])
gnome20.addmod('rep-gtk', dependencies=['librep', 'gtk+'])
gnome20.addmod('librep')
gnome20.addmod('monkey-media', dependencies=['libgnomeui', 'gstreamer'])
gnome20.addmod('rhythmbox', dependencies=['monkey-media', 'gnome-panel',
                                          'gst-plugins'])

gnome20.addmod('thinice2', cvsroot=thinice_cvsroot, dependencies=['gtk+'])
gnome20.addmod('gstreamer', cvsroot=gstreamer_cvsroot,
               dependencies=['glib', 'gnome-xml'],
               # gstreamer requires a '-- ' for configure args to be
               # passed in.  This means that args like
               # --enable-maintainer-mode aren't passed through.
               autogenargs='-- --disable-plugin-builddir --disable-tests')
gnome20.addmod('gst-plugins', cvsroot=gstreamer_cvsroot,
               dependencies=['gstreamer', 'gnome-vfs', 'gtk+'],
               autogenargs='--disable-plugin-builddir --disable-tests')
gnome20.addmod('gst-player', cvsroot=gstreamer_cvsroot,
               dependencies=['gstreamer', 'libgnomeui'])
gnome20.addmod('libmrproject',
               dependencies=['glib', 'gnome-xml', 'libgsf'])
gnome20.addmod('mrproject',
               dependencies=['libmrproject', 'libgnomeui'])
gnome20.addmod('dia-newcanvas',
               dependencies=['gtk+', 'libglade'])
gnome20.addmod('gael2', cvsroot=gael_cvsroot,
               dependencies=['dia-newcanvas', 'libglade', 'libgnomeui','gnome-xml'])

gnome20.addmod('balsa', revision='BALSA_2',
               dependencies=['libgnomeui'])
gnome20.addmod('pan',
               dependencies=['libgnomeui'])
gnome20.addmod('fileroller', cvsroot=fileroller_cvsroot,
               dependencies=['nautilus'])
gnome20.addmod('ggv', dependencies=['libgnomeui'])

gnome20.addmod('gtksourceview', dependencies=['gtk+'])
gnome20.addmod('glimmer', dependencies=['gtksourceview'])
gnome20.addmod('gdl', dependencies=['libgnomeui', 'librsvg'])
gnome20.addmod('gnome-build', dependencies=['gdl', 'gnome-vfs', 'gtkhtml2'])
gnome20.addmod('anjuta2', dependencies=['libgnomeui', 'gnome-build', 'libzvt'])

gnome20.addmod('libsigc++-1.2')
gnome20.addmod('gtkmm-1.3', dependencies=['gtk+', 'libsigc++-1.2'])
gnome20.addmod('gnomemm/libgnomemm', dependencies=['libgnome', 'gtkmm-1.3'])
gnome20.addmod('gnomemm/libbonobomm', dependencies=['libbonobo', 'gtkmm-1.3'])
gnome20.addmod('gnomemm/libbonobouimm',
               dependencies=['libbonoboui', 'gnomemm/libbonobomm'])
gnome20.addmod('gnomemm/libgnomecanvasmm',
               dependencies=['libgnomecanvas', 'gtkmm-1.3'])
gnome20.addmod('gnomemm/gconfmm', dependencies=['gconf', 'gtkmm-1.3'])
gnome20.addmod('gnomemm/libgnomeuimm',
               dependencies=['gtkmm-1.3', 'libgnomeui', 'gnomemm/libgnomemm',
                             'gnomemm/gconfmm'])

gnome20.addmod('gnet',dependencies=['glib'],autogenargs='--enable-glib2')
gnome20.addmod('gnomeicu',dependencies=['libgnomeui','gnet'])

# some simple tasks to make using jhbuild a bit easier
gnome20.add(MetaModule('meta-gnome-devel-platform',
                       modules=['libgnome', 'libbonobo', 'libbonoboui',
                                'libgnomeui']))
gnome20.add(MetaModule('meta-gnome-core',
                       modules=['gnome-desktop', 'gnome-panel',
                                'gnome-session', 'gnome-terminal',
                                'gnome-applets']))
gnome20.add(MetaModule('meta-nautilus',
                       modules=['nautilus', 'nautilus-gtkhtml']))
gnome20.add(MetaModule('meta-gnome-desktop',
                       modules=['meta-gnome-core', 'gnome-control-center',
                                'meta-nautilus', 'yelp', 'bug-buddy',
                                'gtk-engines']))
gnome20.add(MetaModule('meta-gnome-devel-tools',
                       modules=['glade', 'memprof', 'gconf-editor',
                                'devhelp']))
gnome20.add(MetaModule('meta-gnome-python',
                       modules=['gnome-python/pygtk', 'orbit-python',
                                'gnome-python/gnome-python']))
gnome20.add(MetaModule('meta-gnome-c++',
                       modules=['gtkmm-1.3', 'gnomemm/libgnomeuimm']))


# gnome 2.2 branch
gnome22 = ModuleSet(gnome20)
gnome22.addmod('gnome-common');
gnome22.addmod('glib', dependencies=['gtk-doc'])
gnome22.addmod('pango', dependencies=['glib'])
gnome22.addmod('gtk+', dependencies=['pango', 'atk'],
               autogenargs='--with-qt=no')
gnome22.addmod('gconf', dependencies=['ORBit2', 'gnome-xml', 'gtk+'])
gnome22.addmod('gnome-terminal',
               dependencies=['libglade', 'libgnomeui', 'libzvt'])
gnome22.addmod('gnome-control-center',
               dependencies=['libgnomeui', 'esound', 'gnome-desktop'])
gnome22.addmod('gnome-panel', dependencies=['libgnomeui','gnome-desktop'])
gnome22.addmod('gnome-desktop', dependencies=['libgnomeui', 'libwnck'])
gnome22.addmod('gnome-session', dependencies=['libgnomeui', 'libwnck'])
gnome22.addmod('gnome-applets', dependencies=['gnome-panel','libgtop', 'gail'])
gnome22.addmod('yelp', dependencies=['libgnomeui', 'gtkhtml2', 'gnome-vfs'])
gnome22.addmod('gail', dependencies=['gtk+', 'atk', 'libgnomecanvas'])
gnome22.addmod('gtkhtml2', dependencies=['gtk+', 'gnome-xml', 'gail'])
gnome22.addmod('libglade', dependencies=['gtk+', 'gnome-xml'])
gnome22.addmod('libwnck', dependencies=['gtk+'])
gnome22.addmod('libgnome',
               dependencies=['gnome-xml', 'libxslt', 'libbonobo', 'gnome-vfs',
                             'gconf'])
gnome22.addmod('libgnomecanvas',
               dependencies=['gtk+', 'libart_lgpl', 'libglade','gnome-common'])
gnome22.addmod('libgnomeui', dependencies=['libbonoboui', 'libglade'])
gnome22.addmod('librsvg',
               dependencies=['gnome-xml','gtk+', 'libart_lgpl',
                             'gnome-common'])
gnome22.addmod('eel', dependencies=['librsvg','libgnomeui','gail'])
gnome22.addmod('nautilus',
               dependencies=['esound', 'eel', 'librsvg', 'libgnomeui',
                             'gnome-desktop'])


# gnome 1.x support
gnome1 = ModuleSet()
gnome1.addmod('intltool')
gnome1.addmod('gnome-common', revision='gnome-2-0')
gnome1.addmod('esound')
gnome1.addmod('gtk-doc')
gnome1.addmod('glib', revision='glib-1-2', dependencies=['gtk-doc'])
gnome1.addmod('gtk+', revision='gtk-1-2',dependencies=['gtk-doc', 'glib'])
gnome1.addmod('ORBit', revision='orbit-stable-0-5', dependencies=['glib'])
gnome1.addmod('gnome-xml', checkoutdir='libxml', revision='LIB_XML_1_BRANCH')
gnome1.addmod('imlib', dependencies=['gtk+'])
gnome1.addmod('gnome-libs', revision='gnome-libs-1-0',
              dependencies=['ORBit', 'imlib', 'esound'])
gnome1.addmod('libglade', revision='libglade-1-0',
              dependencies=['gtk+', 'gnome-libs', 'gnome-xml'])
gnome1.addmod('gdk-pixbuf', dependencies=['gtk+', 'gnome-libs'])
gnome1.addmod('oaf', dependencies=['intltool', 'ORBit', 'gnome-xml'])
gnome1.addmod('gconf', revision='gconf-1-0',
              dependencies=['ORBit', 'gnome-xml', 'gtk+'])
gnome1.addmod('gnome-print', revision='gnome-1-4-branch',
              dependencies=['gnome-libs', 'gnome-xml', 'gdk-pixbuf'])
gnome1.addmod('gnome-mime-data', dependencies=['gnome-common'])
gnome1.addmod('gnome-vfs', revision='gnome-vfs-1',
              dependencies=['oaf', 'ORBit', 'gconf', 'gnome-xml',
                            'gnome-mime-data'])
gnome1.addmod('bonobo', dependencies=['gnome-libs', 'oaf', 'gnome-print'])
gnome1.addmod('control-center', revision='control-center-1-0',
              dependencies=['gnome-libs', 'gnome-vfs'])
gnome1.addmod('gnome-core', revision='gnome-core-1-4',
              dependencies=['gnome-libs', 'gdk-pixbuf', 'control-center',
                            'libglade'])
gnome1.addmod('libgtop', revision='LIBGTOP_STABLE_1_0',
              dependencies=['glib'])
gnome1.addmod('gnome-http', checkoutdir='libghttp')
gnome1.addmod('gnome-applets', revision='gnome-applets-1-4',
              dependencies=['gnome-core', 'libgtop', 'gnome-http'])
gnome1.addmod('medusa', dependencies=['gnome-vfs', 'gtk+'])
gnome1.addmod('librsvg', revision='librsvg-1-0',
              dependencies=['gtk+', 'gnome-xml', 'gdk-pixbuf'])
gnome1.addmod('eel', revision='eel-1-0',
              dependencies=['gnome-libs', 'librsvg', 'gnome-vfs'])
gnome1.addmod('nautilus', revision='nautilus-gnome-1',
              dependencies=['gnome-libs', 'eel', 'bonobo', 'control-center'])
