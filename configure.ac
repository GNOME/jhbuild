AC_INIT([jhbuild],
        [3.15.92],
        [http://bugzilla.gnome.org/enter_bug.cgi?product=jhbuild],
        [jhbuild])

AC_CONFIG_SRCDIR(jhbuild/main.py)
AC_PREFIX_DEFAULT([~/.local/])
AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_AUX_DIR([build-aux])

AM_INIT_AUTOMAKE([1.11 -Wno-portability foreign no-define tar-ustar no-dist-gzip dist-xz])
AM_MAINTAINER_MODE([enable])

# Check for programs
AC_PROG_CC
AM_PATH_PYTHON
PKG_PROG_PKG_CONFIG

# i18n
AM_GNU_GETTEXT([external])
AM_GNU_GETTEXT_VERSION([0.19])

GETTEXT_PACKAGE=AC_PACKAGE_TARNAME
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE], "$GETTEXT_PACKAGE", [Gettext package])

# Documentation
AC_ARG_ENABLE(
	doc_installation,
	AS_HELP_STRING([--enable-doc-installation=@<:@no/yes@:>@], [install the documentation files]),
	[enable_doc_installation=$enableval],
	[enable_doc_installation=no])
AM_CONDITIONAL([DOC_INSTALLATION_ENABLED],[test "x$enable_doc_installation" = "xyes"])

# GUI
AC_ARG_ENABLE(
	gui,
	AS_HELP_STRING([--enable-gui=@<:@no/yes@:>@], [install the graphical user interface (default: no)]),
	[enable_gui=$enableval],
	[enable_gui=no])
AM_CONDITIONAL([GUI_ENABLED],[test "x$enable_gui" == "xyes"])

YELP_HELP_INIT

AC_CONFIG_FILES([
	Makefile
	doc/Makefile
	po/Makefile.in
	examples/Makefile
	scripts/Makefile
	triggers/Makefile
	jhbuild.desktop.in
	jhbuild/Makefile
	jhbuild/buildbot/Makefile
	jhbuild/buildbot/status/web/Makefile
	jhbuild/buildbot/status/Makefile
	jhbuild/commands/Makefile
	jhbuild/frontends/Makefile
	jhbuild/modtypes/Makefile
	jhbuild/utils/Makefile
	jhbuild/versioncontrol/Makefile
	buildbot/Makefile
])
AC_OUTPUT
