##############
JHBuild Manual
##############

Introduction
============

JHBuild is a tool designed to ease building collections of source
packages, called “modules”. JHBuild uses “module set” files to describe
the modules available to build. The “module set” files include
dependency information that allows JHBuild to discover what modules need
to be built and in what order.

JHBuild was originally written for building
`GNOME <http://www.gnome.org>`__, but has since been extended to be
usable with other projects. A “module set” file can be hosted on a web
server, allowing for build rules independent of the JHBuild project.

JHBuild can build modules from a variety of sources, including
`CVS <http://www.cvshome.org/>`__,
`Subversion <http://subversion.tigris.org/>`__,
`Bazaar <http://www.bazaar-vcs.org/>`__, `Darcs <http://darcs.net/>`__,
`Git <http://git.or.cz/>`__ and
`Mercurial <http://www.selenic.com/mercurial/>`__ repositories, as well
as Tar and Zip archives hosted on web or FTP sites. JHBuild can build
modules using a variety of build systems, including Autotools, CMake,
Meson, WAF, Python Distutils and Perl Makefiles.

JHBuild is not intended as a replacement for the distribution's package
management system. Instead, it makes it easy to build software into a
separate install prefix without interfering with the rest of the system.

.. toctree::
   :maxdepth: 2

   getting-started
   jhbuild-and-gnome
   command-reference
   config-reference
   moduleset-syntax
