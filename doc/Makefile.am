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
	sphinx-build-3 $(srcdir) $(builddir)/build index.rst
