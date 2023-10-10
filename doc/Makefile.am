documentation_files = \
	index.rst \
	config-reference.rst \
	command-reference.rst \
	jhbuild-and-gnome.rst \
	moduleset-syntax.rst \
	getting-started.rst

EXTRA_DIST = \
	conf.py \
	$(documentation_files)

docs: conf.py $(documentation_files)
	sphinx-build-3 $(srcdir) $(builddir)/build $(documentation_files)

docs-pot: conf.py $(documentation_files)
	sphinx-build-3 -b gettext $(srcdir) $(builddir)/pot

docs-po: docs-pot
	sphinx-intl-3 update -p $(builddir)/pot

docs-mo: docs-po
	sphinx-intl-3 build
