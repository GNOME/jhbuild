
all:
	@echo 'Run "make install" to install.'

update:
	cvs -z3 -q update -Pd .

install:
	@echo "Creating $(HOME)/bin/jhbuild"
	@mkdir -p $(HOME)/bin
	@echo '#!/bin/sh' > $(HOME)/bin/jhbuild
	@echo 'python '`pwd`'/jhbuild.py "$$@"' >> $(HOME)/bin/jhbuild
	@chmod a+x $(HOME)/bin/jhbuild
	@[ -f $(HOME)/.jhbuildrc ]||echo "Don't forget to create ~/.jhbuildrc"

.PHONY: all update install
