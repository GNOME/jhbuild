noinst_DATA = jhbuild.desktop

jhbuild.desktop: jhbuild.desktop.in
	$(AM_V_GEN) $(MSGFMT) --desktop --template $< -d $(top_srcdir)/po -o $@

CLEANFILES = $(desktop_DATA)

EXTRA_DIST = jhbuild.desktop.in

DISTCLEANFILES = jhbuild.desktop
