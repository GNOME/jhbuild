AC_INIT(jhbuild, 0.1, james@jamesh.id.au)
AC_CONFIG_SRCDIR(jhbuild/main.py)

AM_INIT_AUTOMAKE
GNOME_COMMON_INIT
AM_MAINTAINER_MODE

AC_PROG_CC

# gnome-doc-utils
PKG_PROG_PKG_CONFIG
GNOME_DOC_INIT

AC_OUTPUT([
Makefile
doc/Makefile
])

cat << _EOF_

Note that autotools are only used to build documentation
Type make -f Makefile.plain to build or install JHBuild

_EOF_


