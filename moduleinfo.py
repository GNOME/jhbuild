from module import Module, MetaModule, ModuleSet

def sfcvsroot(project):
    return ':pserver:anonymous@cvs.%s.sourceforge.net:/cvsroot/%s' % \
           (project, project)

thinice_cvsroot     = sfcvsroot('thinice')
gstreamer_cvsroot   = sfcvsroot('gstreamer')
codefactory_cvsroot = ':pserver:anoncvs@cvs.codefactory.se:/cvs'

# gnome 2.0 support
gnome2 = ModuleSet()

head = gnome2 # for compat.

gnome2.addmod('intltool')
gnome2.addmod('gnome-common')
gnome2.addmod('gtk-doc')
gnome2.addmod('glib', revision='glib-2-0', dependencies=['gtk-doc'])
gnome2.addmod('pango', revision='pango-1-0', dependencies=['glib'])
gnome2.addmod('atk', dependencies=['glib'])
gnome2.addmod('gtk+', revision='gtk-2-0', dependencies=['pango', 'atk'])
gnome2.addmod('gail', dependencies=['gtk+', 'atk', 'libgnomecanvas'])
gnome2.addmod('gtkhtml2', dependencies=['gtk+', 'gnome-xml', 'gail'])
gnome2.addmod('gnome-xml', checkoutdir='libxml2')
gnome2.addmod('libxslt', dependencies=['gnome-xml'])
gnome2.addmod('linc', dependencies=['glib'])
gnome2.addmod('libIDL', dependencies=['glib'])
gnome2.addmod('ORBit2', dependencies=['linc', 'libIDL'])
gnome2.addmod('bonobo-activation',
              dependencies=['intltool', 'gnome-common', 'ORBit2', 'gnome-xml'])
gnome2.addmod('gconf', dependencies=['ORBit2', 'gnome-xml', 'gtk+'])
gnome2.addmod('libbonobo', dependencies=['ORBit2', 'bonobo-activation'])
gnome2.addmod('gnome-mime-data', dependencies=['gnome-common'])
gnome2.addmod('gnome-vfs',
              dependencies=['libbonobo','gconf', 'gnome-mime-data'])
gnome2.addmod('libart_lgpl')
gnome2.addmod('libgnome',
              dependencies=['gnome-xml', 'libxslt', 'libbonobo', 'gnome-vfs',
                            'gconf'])
gnome2.addmod('libgnomecanvas',
              dependencies=['gtk+', 'libart_lgpl', 'libglade', 'gnome-common'])
gnome2.addmod('libbonoboui',
              dependencies=['libgnome', 'libbonobo', 'libgnomecanvas',
                            'libglade'])
gnome2.addmod('libgnomeui', dependencies=['libbonoboui', 'libglade'])

gnome2.addmod('libzvt', dependencies=['libart_lgpl', 'gtk+', 'gnome-common'])
gnome2.addmod('libglade', dependencies=['gtk+', 'gnome-xml'])
gnome2.addmod('gnome-python/pygtk', dependencies=['gtk+', 'libglade'])
gnome2.addmod('orbit-python', dependencies=['libIDL', 'ORBit2'])
gnome2.addmod('gnome-python/gnome-python',
              dependencies=['gnome-python/pygtk', 'libgnomecanvas',
                            'libgnomeui'])
gnome2.addmod('bug-buddy', dependencies=['libgnomeui'])
gnome2.addmod('libwnck', dependencies=['gtk+'])

gnome2.addmod('gnome-panel', dependencies=['libgnomeui','gnome-desktop'])
gnome2.addmod('gnome-desktop', dependencies=['libgnomeui', 'libwnck'])
gnome2.addmod('gnome-session', dependencies=['libgnomeui', 'libwnck'])

gnome2.addmod('gnome-applets', dependencies=['gnome-panel','libgtop', 'gail'])
gnome2.addmod('gnome-games', dependencies=['libgnomeui'])
gnome2.addmod('eel', dependencies=['librsvg','libgnomeui','gail'])
gnome2.addmod('librsvg',
              dependencies=['gnome-xml','gtk+', 'libart_lgpl', 'gnome-common'])
gnome2.addmod('nautilus',
              dependencies=['esound', 'eel', 'librsvg', 'libgnomeui',
                            'gnome-desktop'])
gnome2.addmod('nautilus-gtkhtml', dependencies=['nautilus', 'gtkhtml2'])
gnome2.addmod('metacity', dependencies=['gtk+','gconf'])
gnome2.addmod('metatheme', dependencies=['libgnomeui'])
gnome2.addmod('libgtop', revision='libgtop-GNOME-2-0-port',
              dependencies=['glib'])
gnome2.addmod('procman', dependencies=['libgnomeui','libwnck','libgtop'])
gnome2.addmod('gnome-control-center',
              dependencies=['libgnomeui', 'esound', 'gnome-desktop'])
gnome2.addmod('yelp', dependencies=['libgnomeui', 'gtkhtml2', 'gnome-vfs'])
gnome2.addmod('gnome-utils', dependencies=['libgnomeui', 'gnome-panel'])
gnome2.addmod('gconf-editor', dependencies=['gconf'])
gnome2.addmod('esound')
gnome2.addmod('gnome-media', dependencies=['libgnomeui', 'esound', 'gail'])
gnome2.addmod('gdm2', dependencies=['librsvg'])
gnome2.addmod('profterm', dependencies=['libglade', 'libgnomeui', 'libzvt'])
gnome2.addmod('gtk-engines', dependencies=['gtk+'])
gnome2.addmod('gedit', dependencies=['libgnomeui', 'libgnomeprintui'])
gnome2.addmod('libgnomeprintui', dependencies=['libgnomeprint'])
gnome2.addmod('libgnomeprint', dependencies=['libbonobo', 'libart_lgpl'])
gnome2.addmod('memprof', dependencies=['libgnomeui'])
gnome2.addmod('eog', dependencies=['libgnomeui', 'libgnomeprint'])
gnome2.addmod('gal', revision='gal-2', dependencies=['libgnomeui'])
gnome2.addmod('libole2', dependencies=['glib'])
gnome2.addmod('gnumeric', dependencies=['libole2', 'gal'])

gnome2.addmod('gimp',dependencies=['gtk+', 'libart_lgpl'])

gnome2.addmod('glade', revision='glade-gnome2-branch',
              dependencies=['gtk+', 'gnome-xml', 'libgnomeui',
                            'libgnomeprintui'])
gnome2.addmod('glade2c', dependencies=['gtk+', 'gnome-xml', 'libgnomeui'])
gnome2.addmod('gtkglarea', dependencies=['gtk+'])

gnome2.addmod('sawfish', revision='gnome-2', dependencies=['rep-gtk'])
gnome2.addmod('rep-gtk', dependencies=['librep', 'gtk+'])
gnome2.addmod('librep')
gnome2.addmod('monkey-sound', dependencies=['libgnomeui', 'gstreamer'])
gnome2.addmod('rhythmbox-new', dependencies=['monkey-sound', 'gnome-panel'])

gnome2.addmod('thinice2', cvsroot=thinice_cvsroot, dependencies=['gtk+'])
gnome2.addmod('gstreamer', cvsroot=gstreamer_cvsroot,
              dependencies=['glib', 'gnome-xml'], 
	      autogenargs='-- --disable-plugin-builddir --disable-tests')
gnome2.addmod('gst-plugins', cvsroot=gstreamer_cvsroot,
              dependencies=['gstreamer', 'gnome-vfs', 'gtk+'],
	      autogenargs='-- --disable-plugin-builddir --disable-tests')
gnome2.addmod('gst-player', cvsroot=gstreamer_cvsroot,
              dependencies=['gstreamer', 'libgnomeui'])
gnome2.addmod('libmrproject', cvsroot=codefactory_cvsroot,
              dependencies=['glib', 'gnome-xml'])
gnome2.addmod('mrproject', cvsroot=codefactory_cvsroot,
              dependencies=['libmrproject', 'libgnomeui'])

gnome2.addmod('gtkmm-1.3', dependencies=['gtk+'])
gnome2.addmod('gnomemm/libgnomemm', dependencies=['libgnome', 'gtkmm-1.3'])
gnome2.addmod('gnomemm/libbonobomm', dependencies=['libbonobo'])
gnome2.addmod('gnomemm/libbonobouimm',
              dependencies=['libbonoboui', 'gnomemm/libbonobomm'])
gnome2.addmod('gnomemm/libgnomecanvasmm',
              dependencies=['libgnomecanvas', 'gtkmm-1.3'])
gnome2.addmod('gnomemm/gconfmm', dependencies=['gconf', 'gtkmm-1.3'])
gnome2.addmod('gnomemm/libgnomeuimm',
              dependencies=['gtkmm-1.3', 'libgnomeui', 'gnomemm/libgnomemm',
                            'gnomemm/gconfmm'])

# some simple tasks to make using jhbuild a bit easier
gnome2.add(MetaModule('meta-gnome-devel-platform',
                      modules=['libgnome', 'libbonobo', 'libbonoboui',
                               'libgnomeui']))
gnome2.add(MetaModule('meta-gnome-core',
                      modules=['gnome-desktop', 'gnome-panel', 'gnome-session',
                               'profterm', 'gnome-applets']))
gnome2.add(MetaModule('meta-nautilus',
                      modules=['nautilus', 'nautilus-gtkhtml']))
gnome2.add(MetaModule('meta-gnome-desktop',
                      modules=['meta-gnome-core', 'gnome-control-center',
                               'meta-nautilus', 'yelp', 'bug-buddy',
                               'gtk-engines']))
gnome2.add(MetaModule('meta-gnome-devel-tools',
                      modules=['glade', 'memprof', 'gconf-editor']))
gnome2.add(MetaModule('meta-gnome-python',
                      modules=['gnome-python/pygtk', 'orbit-python',
                               'gnome-python/gnome-python']))
gnome2.add(MetaModule('meta-gnome-c++',
                      modules=['gtkmm-1.3', 'gnomemm/libgnomeuimm']))


# gnome 1.x support
gnome1 = ModuleSet()
gnome1.addmod('intltool')
gnome1.addmod('gnome-common')
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
