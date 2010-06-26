AC_INIT([jhbuild], [2.31.4],
		[http://bugzilla.gnome.org/enter_bug.cgi?product=jhbuild])
AC_CONFIG_SRCDIR(jhbuild/main.py)
AM_INIT_AUTOMAKE
GNOME_COMMON_INIT
AM_MAINTAINER_MODE
AC_PREFIX_DEFAULT(~/.local/)

AM_PATH_PYTHON

# i18n
GETTEXT_PACKAGE="jhbuild"
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE], "$GETTEXT_PACKAGE", [Gettext package])
AM_GLIB_GNU_GETTEXT
IT_PROG_INTLTOOL([0.35.0])

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
	po/Makefile.in
	scripts/Makefile
	jhbuild/Makefile
	jhbuild/buildbot/Makefile
	jhbuild/buildbot/status/web/Makefile
	jhbuild/buildbot/status/Makefile
	jhbuild/commands/Makefile
	jhbuild/cut_n_paste/Makefile
	jhbuild/frontends/Makefile
	jhbuild/modtypes/Makefile
	jhbuild/utils/Makefile
	jhbuild/versioncontrol/Makefile
	buildbot/Makefile
])
AC_OUTPUT([
	jhbuild.desktop.in
])
