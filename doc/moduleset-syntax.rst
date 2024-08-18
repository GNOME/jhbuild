Module Set File Syntax
======================

JHBuild uses XML files to describe the dependencies between modules. A
RELAX-NG schema and Document Type Definition are included with JHBuild
in the ``modulesets/`` directory. The RELAX-NG schema can be used to
edit module set files using ``nxml-mode`` in Emacs.

The top-level element in a module set file is ``moduleset`` element. No XML
namespace is used. The elements below the top-level come in three types:
module sources, include statements and module definitions.

Content in the moduleset file can be conditionally included by use of
the ``<if>`` tag to surround the conditional content. It is currently only
possible to predicate the inclusion on whether a particular condition
flag is set or not, using ``<if condition-set='cond'>`` or ``<if
condition-unset='cond'>``. Conditions are set by default on a per-OS basis
but can be influenced by way of the ``conditions`` variable in jhbuildrc
or the ``--conditions=`` commandline argument.

Module Sources
--------------

Rather than listing the full location of every module, a number of
"module sources" are listed in the module set, and then referenced by
name in the module definitions. As well as reducing the amount of
redundant information in the module set, it makes it easy for a user to
specify an alternative source for those modules (for CVS and Subversion,
it is common for developers and users to use different repository access
methods).

The ``repository`` element is used to describe all types of repository. The
``branch`` element is used inside module definition to specify additional
settings.

::

   <repository name="name"
     type="type"
     [ default="default" ]
     [ password="password" ]
     [ cvsroot="cvsroot" ]
     [ archive="archive" ]
     [ href="href" ]
     [ server="server" ]
     [ database="database" ]
     [ defbranch="defbranch" ]
     [ trunk-template="trunk-template" ]
     [ branches-template="branches-template" ]
     [ tags-template="tags-template" ]
     [ developer-href-example="developer-href-example" ] />

The ``name`` attribute is a unique identifier for the repository.

The ``default`` attribute specifies whether this repository is the default
source for this module set.

The ``type`` attribute specifies the type of repository. It can be one of:
``bzr``, ``cvs``, ``darcs``, ``fossil``, ``git``, ``hg``, ``mnt``,
``svn``, ``tarball``. Other attributes depend on the type, as well as
the branch used inside module definitions. Those are described below in
the repository type sub-sections.

The ``developer-href-example`` attribute is used to specify the format of
the URL for the repository used by developers. This is informational
only.

The ``branch`` element is used inside module definitions.

::

   <branch
     [ repo="repository" ]
     [ module="module name" ]
     [ checkoutdir="checkoutdir" ]
     [ revision="revision" ]
     [ tag="tag" ]
     [ update-new-dirs="update-new-dirs" ]
     [ override-checkoutdir="override-checkoutdir" ]
     [ subdir="subdir" ]
     [ branch="branch" ]
     [ version="version" ]
     [ size="size" ]
     [ source-subdir="source-subdir" ]
     [ hash="hash" ]/>

All attributes have sensible defaults and depend on the module and
repository definitions. Common attributes are described here.

The ``repo`` attribute is used to specify non-default repository name.

The ``module`` attribute is used to specify module name to checkout from the
repository. Defaults to module id.

The ``checkoutdir`` attribute is used to specify the checkout directory
name. Defaults to module id.

Other attributes are described below

Bazaar
~~~~~~

This repository type is used to define a Bazaar repository. It is
recommended to have Bazaar 1.16 or higher.

::

   <repository type="bzr" name="launchpad.net"
         href="lp:"/>


Additional attributes are: ``trunk-template`` (defaults to ``"%(module)s"``)
and ``branches-template`` (defaults to ``"%(module)s/%(branch)s"``). These
attributes are used to specify templates for constructing URL. A ``branch``
element in the module definitions can specify branch and user
attributes. These values will be substituted in the templates. If either
of those are defined branches-template is used, otherwise trunk-template
is used. This way you can override repository to build modules from your
personal branch or build many modules from a repository with
non-standard layout.

An addition ``branch`` element accepts ``revspec`` attribute to anchor on a
particular revision. Any valid ``bzr revspec`` is accepted, for example
``date:yesterday, -5, tag:0.1`` to get first revision since yesterday, 5
commits behind the tip or tag "0.1". See ``bzr help revisionspec`` for
all possible values.

For example repository with template attributes defined:

::

   <repository type="bzr" name="launchpad.net"
         href="lp:"
         trunk-template="~bzr-pqm/%(module)s/bzr.dev"
         branches-template="~bzr-pqm/%(module)s/%(branch)s"/>


Example ``branch`` elements for the above repository:

::

   <branch repo="launchpad.net"
         module="bzr"
         checkoutdir="bzr-next"/>


::

   <branch repo="launchpad.net"
         module="bzr"
         branch="2.2"
         checkoutdir="bzr-beta"/>


CVS
~~~

This repository type is used to define a CVS repository.

The ``password`` attribute is used to specify the password to the
repository.

The ``cvsroot`` attribute is used to specify the root of the repository.

::

   <repository type="cvs" name="tango.freedesktop.org"
       cvsroot=":pserver:anoncvs@anoncvs.freedesktop.org:/cvs/tango"
       password=""/>


Additional attributes are: ``revision``, ``update-new-dirs`` and
``override-checkoutdir``.

Darcs
~~~~~

This repository type is used to define a Darcs repository.

::

   <repository type="darcs" name="telepathy.freedesktop.org"
         href="http://projects.collabora.co.uk/darcs/telepathy/"/>

Git
~~~

This repository type is used to define a Git repository.

::

   <repository type="git" name="git.freedesktop.org"
       href="git://anongit.freedesktop.org/git/"/>


It allows the following attributes on the ``branch`` element:

The ``revision`` attribute is used to specify a local or remote-tracking
branch to switch to in the update phase. It defaults to 'master'. It is
possible to override this attribute with the ``branches`` configuration
variable. The switch will only be performed, if the current branch is
tracking a remote branch, to not disturb your own work.

The ``tag`` attribute is used to specify a revision to unconditionally check
out in the update phase. It overrides the ``revision`` attribute.

::

   <branch repo="git.freedesktop.org" module="swfdec/swfdec"
           checkoutdir="swfdec"
           revision="local-or-remote-branch"
           tag="tree-ish"/>


Mercurial
~~~~~~~~~

This repository type is used to define a Mercurial repository.

::

   <repository type="hg" name="hg.gtk-vnc"
       href="http://gtk-vnc.codemonkey.ws/hg/" />

::

   <branch repo="hg.gtk-vnc" module="outgoing.hg" checkoutdir="gtk-vnc"/>

Monotone
~~~~~~~~

This repository type is used to define a Monotone repository.

The ``server`` attribute is used to specify the repository server.

The ``database`` attribute is used to specify the database to use for the
repository.

The ``defbranch`` attribute is used specify the branch of the repository to
use.

::

   <repository type="mtn" name="pidgin.im"
       server="pidgin.im" database="pidgin.im.mtn"
       defbranch="im.pidgin.pidgin"/>

Subversion
~~~~~~~~~~

This repository type is used to define a Subversion repository.

::

   <repository type="svn" name="svn.gnome.org" default="yes"
       href="http://svn.gnome.org/svn/"/>


It allows a revision on the ``branch`` element. This attribute defines the
branch to checkout or, if it is a number, a specific revision to
checkout.

::

   <branch revision="gnome-2-20"/>


It is possible to specify custom ``svn`` layout using trunk-template
(defaults to "%(module)s/trunk"), branches-template (defaults to
"%(module)s/branches/%(branch)s") and tags-template (defaults to
"%(module)s/tags/%(tag)s")

System
~~~~~~

This repository type is used to define a fake system repository. A
system repository is required to create any :ref:`systemmodule`.

::

   <repository type="system" name="system"/>

Tarballs
~~~~~~~~

This repository type is used to define a tarball repository.

::

   <repository type="tarball" name="dbus/dbus-python"
       href="http://dbus.freedesktop.org/releases/dbus-python/"/>

It allows the following attributes on the ``branch`` element:

The ``module`` attribute specifies the file to download and compile, the
``version`` attribute specifies the module version.

The size and hash, as well as the obsolete md5sum, attributes are
optional. If these attributes are present, they are used to check that
the source package was downloaded correctly.

The ``rename-tarball`` can be used to rename the tarball file when
downloading, in case the original name conflicts with another module.

Any number of ``patch`` elements may be nested inside the ``branch`` element.
These patches are applied, in order, to the source tree after unpacking.
The ``file`` attribute gives the patch filename, and the ``strip`` attribute
says how many levels of directories to prune when applying the patch.

For module sets shipped with JHBuild, the patch files are looked up in
the ``jhbuild/patches/`` directory; for module sets referred by URI, the
patch files are looked for in the same directory as the moduleset file,
or in its ``patches/`` subdirectory. It is also possible for the file
attribute to specify a URI, in which case it will be downloaded from
that location.

::

   <branch module="dbus-python-0.80.2.tar.gz" version="0.80.2"
       repo="dbus/dbus-python"
       hash="md5:2807bc85215c995bd595e01edd9d2077" size="453499">
     <patch file="dbus-glib-build.patch" strip="1" />
   </branch>

A tarball ``branch`` element may also contain quilt elements which specify
nested branch to import.

Including Other Module Sets
---------------------------

JHBuild allows one module set to include the contents of another by
reference using the ``include`` element.

::

   <include href="uri"/>

The href is a URI reference to the module set to be included, relative
to the file containing the ``include`` element.

Only module definitions are imported from the referenced module set -
module sources are not. Multiple levels of includes are allowed, but
include loops are not (there isn't any code to handle loops at the
moment).

Module Definitions
------------------

There are various types of module definitions that can be used in a
module set file, and the list can easily be extended. Only the most
common ones will be mentioned here.

They are all basically composed of a ``branch`` element describing how to
get the module and ``dependencies``, ``suggests`` and ``after`` elements to declare
the dependencies of the module.

Any modules listed in the ``dependencies`` element will be added to the
module list for ``jhbuild build`` if it isn't already included, and make
sure the dependent modules are built first.

After generating the modules list, the modules listed in the suggests
element will be used to further sort the modules list (although it will
not pull any additional modules). This is intended for cases where a
module has an optional dependency on another module.

Command argument attributes (eg. ``makeargs``, ``mesonargs`` etc) support
automatic expansion of the variables ``${prefix}`` and ``${libdir}`` to
their corresponding values. Eg.``mesonargs="-Dlog-dir=${prefix}/var/log/gdm"``

.. _autotools:

autotools
~~~~~~~~~

The ``autotools`` element is used to define a module which is compiled using
the GNU Autotools build system.

::

   <autotools id="id"
             [ autogenargs="autogenargs" ]
             [ makeargs="makeargs" ]
             [ makeinstallargs="makeinstallargs" ]
             [ autogen-sh="autogen-sh" ]
             [ makefile="makefile" ]
             [ skip-autogen="skip-autogen" ]
             [ skip-install="skip-install" ]
             [ uninstall-before-install="uninstall-before-install" ]
             [ autogen-template="autogen-template" ]
             [ check-target="check-target" ]
             [ supports-non-srcdir-builds="supports-non-srcdir-builds" ]
             [ force-non-srcdir-builds="force-non-srcdir-builds" ]
             [ supports-unknown-configure-options="supports-unknown-configure-options" ]
             [ supports-static-analyzer="supports-static-analyzer" ]
             [ supports-parallel-builds="supports_parallel_build" ]>

     <branch [ ... ] >
       [...]
     </branch>

     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <after>
       <dep package="modulename"/>
       ...
     </after>

   </autotools>

The ``autogenargs``, ``makeargs`` and ``makeinstallargs`` attributes are used to
specify additional arguments to pass to ``autogen.sh``, ``make`` and
``make install`` respectively. Take in mind that ``makeinstallargs`` should
also include the make target to use (typically ``install``) this allows to
use a different make target for the install phase if needed.
Eg. ``makeinstallargs="install datadir=${prefix}/share"`` or ``makeinstallargs="my-target"``

The ``autogen-sh`` attribute specifies the name of the autogen.sh script to
run. The value ``autoreconf`` can be used if your module has no
``autogen.sh`` script equivalent. In that case, JHBuild will run
``autoreconf -fi``, followed by the proper ``configure``. ``skip-autogen``
chooses whether or not to run autogen.sh, it is a boolean with an extra
``never`` value to tell JHBuild to never skip running ``autogen.sh``.
``skip-install`` is a boolean attribute specifying whether to skip
``make install`` command on the module, default is ``false``. ``makefile``
specifies the filename of the makefile to use.

The ``uninstall-before-install`` specifies any old installed files from the
module should before removed before running the install step. This can
be used to work around a problem where libtool tries to link one library
it is installing against another library it is installing, but because
of jhbuild's use of ``DESTDIR``, finds the old installed library instead.
The downside of specifying this is that it could cause problems if the
user is currently running code that relies on installed files from the
module.

The ``supports-non-srcdir-builds`` attribute is used to mark modules that
can't be cleanly built using a separate source directory; it takes the values
``yes`` or ``no``, and the default is ``yes``.

The ``force-non-srcdir-builds`` attribute is used to mark modules that can't
be cleanly built from the source directory, but can be built from
outside it; it takes the values ``yes`` or ``no``, and the default is ``no``.

The ``autogen-template`` attribute can be used if you need finer control
over the autogen command line. It is a python format string, which will
be substituted with the following variables: ``srcdir``, ``autogen-sh``,
``prefix``, ``libdir``, and ``autogenargs``. For example, here is the
default autogen-template:

::

   %(srcdir)s/%(autogen-sh)s --prefix %(prefix)s --libdir %(libdir)s %(autogenargs)s

The ``check-target`` attribute must be specified (with false as value) for
modules that do not have a ``make check`` target.

The ``supports-static-analyzer`` attribute must be specified (with false as
value) for modules which don’t support being built under a static
analysis tool such as ``scan-build``.

The ``supports-unknown-configure-options`` attribute is used to mark modules
that will error out if an unknown option is passed to ``configure``.
Global configure options will not be used for that module.

The ``supports-parallel-builds`` attribute can be set to ``no`` if you don't
want your module to be built using parallel jobs according to number of cpu
cores/threads. Default is ``yes``.

cmake
~~~~~

The ``cmake`` element is used to define a module which is built using the
CMake build system.

::

     <cmake id="modulename"
               [ cmakeargs="cmakeargs" ]
               [ ninjaargs="ninjaargs" ]
               [ makeargs="makeargs" ]
               [ skip-install="skip-install" ]
               [ cmakedir="cmakedir" ]
               [ use-ninja="use-ninja" ]
               [ supports-non-srcdir-builds="supports-non-srcdir-builds" ]
               [ force-non-srcdir-builds="force-non-srcdir-builds" ]
               [ supports-parallel-builds="supports_parallel_build" ]>
     <branch [ ... ] >
       [...]
     </branch>

     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <after>
       <dep package="modulename"/>
       ...
     </after>
   </cmake>

The ``cmakeargs`` attribute is used to specify additional arguments to pass
to ``cmake``.

The ``ninjaargs`` attribute is used to specify additional arguments to pass
to ``ninja``.

The ``makeargs`` attribute is used to specify additional arguments to pass
to ``make``.

The ``cmakedir`` attribute specifies the subdirectory where cmake will run
in relation to srcdir.

``skip-install`` is a boolean attribute specifying whether to skip
the install phase of the module; default is ``false``.

The ``supports-non-srcdir-builds`` attribute is used to mark modules that
can't be cleanly built using a separate source directory, it takes the values
``yes`` or ``no``; default is ``yes``.

The ``force-non-srcdir-builds`` attribute is used to mark modules that can't
be cleanly built from the source directory, but can be built from
outside it. Possible values are ``yes`` or ``no``; default is ``no``.

The ``use-ninja`` attribute is used to mark modules should be built using
the Ninja backend for cmake, instead of the Make backend. The default is
to use the Ninja backend.

The ``supports-parallel-builds`` attribute can be set to ``no`` if you don't
want your module to be built using parallel jobs according to number of cpu
cores/threads. Default is ``yes``.

.. _meson:

meson
~~~~~

The ``meson`` element is used to define a module which is configured using
the Meson build system and built using the Ninja build tool.

::

     <meson id="modulename"
               [ mesonargs="mesonargs" ]
               [ ninjaargs="ninjaargs" ]
               [ skip-install="skip-install" ]>
     <branch [ ... ] >
       [...]
     </branch>

     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <after>
       <dep package="modulename"/>
       ...
     </after>
   </meson>

The ``mesonargs`` attribute is used to specify additional arguments to pass
to ``meson``.

The ``ninjaargs`` attribute is used to specify additional arguments to pass
to ``ninja``.

``skip-install`` is a boolean attribute specifying whether to skip
the install phase of the module; default is ``false``.

.. _pip:

pip
~~~

The ``pip`` element is used to define a module which is built using
python's pip.

::

   <pip id="modulename">
     <branch [ ... ] >
       [...]
     </branch>

     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <after>
       <dep package="modulename"/>
       ...
     </after>
   </pip>

.. _distutils:

distutils
~~~~~~~~~

The ``distutils`` element is used to define a module which is built using
python's distutils.

::

   <distutils id="modulename"
               [ supports-non-srcdir-builds="yes|no" ]>
     <branch [ ... ] >
       [...]
     </branch>

     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <after>
       <dep package="modulename"/>
       ...
     </after>
   </distutils>

.. _linux:

linux
~~~~~

The ``linux`` element defines a module used to build a linux kernel. In
addition, a separate kernel configuration can be chosen using the
kconfig subelement.

::

   <linux id="id"
         [ makeargs="makeargs" ]>

     <branch [ ... ] >
       [...]
     </branch>

     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <after>
       <dep package="modulename"/>
       ...
     </after>

     <kconfig [ repo="repo" ]
           version="version"
           [ module="module" ]
           [ config="config" ] />

   </linux>

.. _perl:

perl
~~~~

The ``perl`` element is used to build perl modules.

The ``makeargs`` attribute is used to specify additional arguments to pass
to ``make``.

::

   <perl id="modulename"
        [ makeargs="makeargs" ]>

     <branch [ ... ] >
       [...]
     </branch>

     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <after>
       <dep package="modulename"/>
       ...
     </after>

   </perl>

.. _systemmodule:

systemmodule
~~~~~~~~~~~~

The ``systemmodule`` element is used to specify modules that must be
provided by the system. The module should be installed by your
distributions package management system.

::

   <systemmodule id="modulename">
     <pkg-config>pkg-config.pc</pkg-config>

     <branch repo="system" version="version" />
   </systemmodule>

If the system module does not provide a pkg-config file,
systemdependencies tag can be used to identify the dependencies. Two
values are supported by the ``type`` attribute of the dep tag:

1. ``path`` value. The path is searched for the matching program name.

2. ``c_include`` value. The C include path is searched for the matching
   header name. name may include a sub-directory. The C include search
   path can modified by setting ``CPPFLAGS`` within the configuration
   variables ``cflags`` or :ref:`module_autogenargs`.

::

   <systemmodule id="modulename">
     <branch repo="system" version="version" />
     <systemdependencies>
       <dep type="path" name="executable-name" />
     </systemdependencies>
   </systemmodule>

   <systemmodule id="modulename">
     <branch repo="system" version="version" />
     <systemdependencies>
       <dep type="c_include" name="header-name" />
     </systemdependencies>
   </systemmodule>

If the system module may be installed in different locations or
installed with different names by different distributions, altdep tag
can be used as subelements of dep tag to specify alternative locations
or names. altdep tag support the same attributes as dep tag does.

::

   <systemmodule id="modulename">
     <branch repo="system" version="version" />
     <systemdependencies>
       <dep type="path" name="executable-name">
         <altdep type="path" name="alternative-executable-name-1" />
         <altdep type="path" name="alternative-executable-name-2" />
         ...
       <dep>
     </systemdependencies>
   </systemmodule>

   <systemmodule id="modulename">
     <branch repo="system" version="version" />
     <systemdependencies>
       <dep type="c_include" name="header-name">
         <altdep type="c_include" name="alternative-header-name-1" />
         <altdep type="c_include" name="alternative-header-name-2" />
         ...
       <dep>
     </systemdependencies>
   </systemmodule>

.. _waf:

waf
~~~

The ``waf`` element is used to define a module which is built using the Waf
build system.

The ``waf-command`` attribute is used to specify the waf command script to
use; it defaults to ``waf``.

The ``python-command`` attribute is used to specify the Python executable to
use; it defaults to ``python``. This is useful to build modules against
version 3 of Python.

::

   <waf id="modulename">
        [ python-command="python-command" ]
        [ waf-command="waf-command" ]>
     <branch [ ... ] >
       [...]
     </branch>

     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <after>
       <dep package="modulename"/>
       ...
     </after>
   </waf>

.. _testmodule:

testmodule
~~~~~~~~~~

The ``testmodule`` element is used to create a module which runs a suite of
tests using LDTP or Dogtail.

::

   <testmodule id="id"
              type="type">

     <branch [ ... ] >
       [...]
     </branch>

     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <after>
       <dep package="modulename"/>
       ...
     </after>

     <testedmodules>
       <tested package="package" />
     </testedmodules>

   </testmodule>

The ``type`` attribute gives the type of tests to be run in the module.
'dogtail' uses python to invoke all .py files. 'ldtp' invokes
'ldtprunner run.xml'.

Unless the :ref:`noxvfb` configuration option is set, an Xvfb server is started
to run the tests in.

.. _metamodule:

metamodule
~~~~~~~~~~

The ``metamodule`` element defines a module that doesn't actually do
anything. The only purpose of a module of this type is its dependencies.

For example, meta-gnome-desktop depends on all the key components of the
GNOME desktop, therefore telling JHBuild to install it actually installs
the full desktop.

::

   <metamodule id="modulename">
     <dependencies>
       <dep package="modulename"/>
       ...
     </dependencies>
     <suggests>
       <dep package="modulename"/>
       ...
     </suggests>
   </metamodule>

The ``id`` attribute gives the name of the module. The child elements are
handled as for :ref:`autotools`.

Deprecated Elements
-------------------

Module Sources
~~~~~~~~~~~~~~

.. _cvsroot:

cvsroot
^^^^^^^

The ``cvsroot`` element is now deprecated - the ``repository`` element should be
used instead.

The ``cvsroot`` element is used to describe a CVS repository.

::

     <cvsroot name="rootname"
              [ default="yes|no" ]
              root="anon-cvsroot"
              password="anon-password"/>

The ``name`` attribute should be a unique identifier for the CVS repository.

The ``default`` attribute says whether this is the default module source for
this module set file.

The ``root`` attribute lists the CVS root used for anonymous access to this
repository, and the ``password`` attribute gives the password used for
anonymous access.

.. _svnroot:

svnroot
^^^^^^^

The ``svnroot`` element is now deprecated - the ``repository`` element should be
used instead.

The ``svnroot`` element is used to describe a Subversion repository.

::

     <svnroot name="rootname"
              [ default="yes|no" ]
              href="anon-svnroot"/>

The ``name`` attribute should be a unique identifier for the Subversion
repository.

The ``default`` attribute says whether this is the default module source for
this module set file.

The ``href`` attribute lists the base URL for the repository. This will
probably be either a ``http``, ``https`` or ``svn`` URL.

Deprecated Module Types
~~~~~~~~~~~~~~~~~~~~~~~

.. warning::

   This section describes deprecated elements, they may still be used in
   existing module sets but it is advised not to use them anymore.

.. _tarball:

tarball
^^^^^^^

.. important::

   This deprecated element is just a thin wrapper around both autotools
   module type and tarball repository type.

The ``tarball`` element is used to define a module that is to be built from
a tarball.

::

     <tarball id="modulename"
                 [ version="version" ]
                 [ checkoutdir="checkoutdir" ]
                 [ autogenargs="autogenargs" ]
                 [ makeargs="makeargs" ]
                 [ autogen-sh="autogen-sh" ]
                 [ supports-non-srcdir-builds="yes|no" ]>
       <source href="source-url"
               [ size="source-size" ]
               [ hash="source-algo:source-hash" ]
               [ md5sum="source-md5sum" ]/>
       <patches>
         <patch file="filename" strip="level"/>
         ...
       </patches>
       <dependencies>
         <dep package="modulename"/>
         ...
       </dependencies>
       <suggests>
         <dep package="modulename"/>
         ...
       </suggests>
     </tarball>

The ``id`` and ``version`` attributes are used to identify the module.

The ``source`` element specifies the file to download and compile. The ``href``
attribute is mandatory, while the ``size`` and ``hash``, as well as the obsolete
``md5sum``, attributes are optional. If these last two attributes are
present, they are used to check that the source package was downloaded
correctly.

The ``patches`` element is used to specify one or more patches to apply to
the source tree after unpacking, the ``file`` attribute gives the patch
filename, and the ``strip`` attribute says how many levels of directories to
prune when applying the patch.

For module sets shipped with JHBuild, the patch files are looked up in
the ``jhbuild/patches/`` directory; for module sets referred by URI, the
patch files are looked for in the same directory as the moduleset file,
or in its ``patches/`` subdirectory. It is also possible for the file
attribute to specify a URI, in which case it will be downloaded from
that location.

The other attributes and the ``dependencies``, ``suggests`` and ``after`` elements
are processed as for :ref:`autotools`.
