noinst_DATA = jhbuild.desktop jhbuild-systemd.desktop

jhbuild.desktop: jhbuild.desktop.in
	$(AM_V_GEN) $(MSGFMT) --desktop --template $< -d $(top_srcdir)/po -o $@

jhbuild-systemd.desktop: jhbuild-systemd.desktop.in
	$(AM_V_GEN) $(MSGFMT) --desktop --template $< -d $(top_srcdir)/po -o $@

CLEANFILES = $(desktop_DATA)

EXTRA_DIST = jhbuild.desktop.in jhbuild-systemd.desktop.in

DISTCLEANFILES = jhbuild.desktop jhbuild-systemd.desktop
