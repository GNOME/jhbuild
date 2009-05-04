#! /bin/sh

xsltproc --nodtdattr scripts/create-master-tracking-moduleset.xsl \
	modulesets/gnome-suites-2.28.modules > \
	modulesets/gnome-suites-trunk.modules

xsltproc --nodtdattr scripts/create-master-tracking-moduleset.xsl \
	modulesets/gnome-2.28.modules > \
	modulesets/gnome-trunk.modules

sed -i -e 's/gnome-suites-2.28.modules/gnome-suites-trunk.modules/' modulesets/gnome-trunk.modules
