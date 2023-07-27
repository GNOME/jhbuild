documentation_files = \
	index.rst \
	configuration.rst \
	commands.rst \
	gnome.rst \
	modulesets.rst \
	getting_started.rst

EXTRA_DIST = \
	conf.py \
	$(documentation_files)


docs: conf.py $(documentation_files)
	sphinx-build-3 $(srcdir) $(builddir)/build index.rst
