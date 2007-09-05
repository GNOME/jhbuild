AC_INIT([jhbuild], [0.1], [james@jamesh.id.au])
AC_CONFIG_SRCDIR(jhbuild/main.py)
AM_INIT_AUTOMAKE
GNOME_COMMON_INIT
AM_MAINTAINER_MODE

AC_PROG_CC
PKG_PROG_PKG_CONFIG

# Documentation
AC_ARG_ENABLE(
	doc_installation,
	AS_HELP_STRING([--enable-doc-installation=@<:@no/yes@:>@], [install the documentation files]),
	[enable_doc_installation=$enableval],
	[enable_doc_installation=no])
AM_CONDITIONAL([DOC_INSTALLATION_ENABLED],[test "x$enable_doc_installation" = "xyes"])
# pkg-config check below is disabled since documentation is optional
# PKG_CHECK_MODULES(gnome-doc-utils, gnome-doc-utils)
GNOME_DOC_INIT

AC_CONFIG_FILES([
	Makefile
	doc/Makefile
])
AC_OUTPUT
