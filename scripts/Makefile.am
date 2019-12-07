EXTRA_DIST = hg-update.py jhbuild.in

bin_SCRIPTS = jhbuild
CLEANFILES = jhbuild

pkgdata_SCRIPTS = hg-update.py

jhbuild: jhbuild.in
	sed						\
		-e s!\@srcdir\@!$(abs_top_srcdir)!	\
		-e s!\@prefix\@!$(prefix)!		\
		-e s!\@datadir\@!$(datadir)!		\
		-e s!\@pkgdatadir\@!$(pkgdatadir)!	\
		-e s!\@libexecdir\@!$(libexecdir)!	\
		-e s!\@libdir\@!$(libdir)!		\
		-e s!\@pythondir\@!$(pythondir)!	\
		-e s!\@python\@!$(PYTHON_BASENAME)!	\
		-e s!\@PACKAGE\@!$(PACKAGE)!		\
		-e s!\@VERSION\@!$(VERSION)!		\
		< $< > $@
	chmod +x $@

jhbuild: Makefile

all-local: jhbuild

