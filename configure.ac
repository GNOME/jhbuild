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
AM_GNU_GETTEXT_VERSION([0.18])

GETTEXT_PACKAGE=AC_PACKAGE_TARNAME
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE], "$GETTEXT_PACKAGE", [Gettext package])

# Documentation
have_doc_tools=no
AC_ARG_ENABLE(
	[doc_installation],
	[AS_HELP_STRING([--enable-doc-installation=@<:@no/yes@:>@],
	                [Enable build of documentation files])],
	[enable_doc_installation=$enableval],
	[enable_doc_installation=check])
AS_IF([test "x$enable_doc_installation" != "xno"],
      [m4_ifdef([YELP_HELP_INIT],
                [YELP_HELP_INIT
                 have_doc_tools=yes])
      ])
AS_IF([test "x$enable_doc_installation" = "xyes"],
      [AS_IF([test "x$have_doc_tools" = "xno"],
             [AC_MSG_ERROR([--enable-doc-installation was given, but yelp-tools were not found])])
      ])
AM_CONDITIONAL([DOC_INSTALLATION_ENABLED],[test "x$have_doc_tools" = "xyes"])

AC_CONFIG_FILES([
	Makefile
	doc/Makefile
	po/Makefile.in
	examples/Makefile
	scripts/Makefile
	triggers/Makefile
	jhbuild.desktop
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
