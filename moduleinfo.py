from module import Module, ModuleSet

head = ModuleSet()
head.add(Module(name='xml-i18n-tools'))
head.add(Module(name='gnome-common'))
head.add(Module(name='gtk-doc'))
head.add(Module(name='glib',
                dependencies=['gtk-doc']))
head.add(Module(name='pango', dependencies=['glib']))
head.add(Module(name='atk', dependencies=['glib']))
head.add(Module(name='gtk+',
                dependencies=['pango', 'atk']))
head.add(Module(name='gnome-xml', checkoutdir='libxml2'))
head.add(Module(name='linc', dependencies=['glib']))
head.add(Module(name='libIDL', dependencies=['glib']))
head.add(Module(name='ORBit2', dependencies=['linc', 'libIDL']))
head.add(Module(name='bonobo-activation',
         dependencies=['xml-i18n-tools', 'gnome-common','ORBit2','gnome-xml']))
head.add(Module(name='gconf', dependencies=['ORBit2','gnome-xml','gtk+']))
head.add(Module(name='libbonobo', dependencies=['ORBit2','bonobo-activation']))
head.add(Module(name='gnome-vfs', dependencies=['libbonobo','gconf']))
head.add(Module(name='libart_lgpl'))
head.add(Module(name='bonobo-config',
                dependencies=['libbonobo', 'xml-i18n-tools']))
head.add(Module(name='libgnome',
                dependencies=['libbonobo','gnome-vfs','gconf']))
head.add(Module(name='libgnomecanvas', dependencies=['gtk+', 'libart_lgpl']))
head.add(Module(name='libbonoboui',
                dependencies=['libgnome', 'libbonobo', 'libgnomecanvas']))
head.add(Module(name='libgnomeui', dependencies=['libbonoboui']))

head.add(Module(name='libglade',
         dependencies=['gtk+', 'gnome-xml', 'libbonoboui', 'libgnomeui']))
head.add(Module(name='gnome-python/pygtk',
         dependencies=['gtk+', 'libglade']))
head.add(Module(name='gnome-python/gnome-python',
         dependencies=['gnome-python/pygtk', 'libgnomecanvas']))

