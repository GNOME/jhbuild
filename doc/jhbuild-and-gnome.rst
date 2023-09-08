JHBuild and GNOME
=================

This section provides guidance on building, installing and running
GNOME.

Building GNOME
--------------

To build GNOME some development packages are required. This includes:

-  DocBook XML DTD and XSLT stylesheets. These need to be registered in
   the XML catalog (``/etc/xml/catalog``).

-  X libraries.

-  ``libsmbclient`` from Samba (used for browsing Windows networks).

-  ``libbz2`` from bzip2.

-  ``libpng``, ``libjpeg`` and ``libtiff`` (used for image loading).

If installing distribution packages, and if applicable for your
distribution, install the corresponding “dev” or “devel” packages. A
list of `package names <http://live.gnome.org/JhbuildDependencies>`__
for different distributions is maintained on the GNOME wiki.

Running a Single GNOME Application
----------------------------------

This section details how to run a single GNOME application. The
application will run within the current desktop environment. To run the
application within the complete JHBuild GNOME see `Running the GNOME
Desktop Environment <#running-gnome>`__.

Launch a JHBuild shell. The JHBuild shell has all the necessary
environment variables set.

::

   $ jhbuild shell

Verify the correct application will be run. For example:

::

   $ which gedit
   /home/wanda/jhbuild/install/bin/gedit

Run the application:

::

   $ gedit &

Alternatively, run the application using the ``run`` command:

::

   $ jhbuild run gedit

Running the GNOME Desktop Environment
-------------------------------------

Create a new user account to run the JHBuild GNOME. Running JHBuild
GNOME using a different user account is recommended to avoid problems
caused by user settings stored in the home directory. This manual refers
to the new account as ``gnomedev``.

Setup JHBuild on the new ``gnomedev`` account. Copy or soft-link
``~/.config/jhbuildrc`` and ``~/.local/bin/jhbuild`` to ``gnomedev``
home directory.

Open a terminal as the user ``gnomedev``. Permanently add
``~/.local/bin`` to the ``PATH`` variable, run the following command:

::

   $ echo 'PATH=$PATH:~/.local/bin' >> ~/.bashrc

Test JHBuild works:

::

   $ jhbuild run pkg-config gtk+-2.0 --modversion
   2.20.1

Setup GNOME to run from the display manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Build and install JHBuild GNOME.

Enable system services. JHBuild GNOME will use the ``/usr/bin`` system
D-Bus daemon and the system services within
``/usr/share/dbus-1/system-services/``. JHBuild GNOME will use the
JHBuild session D-Bus daemon and the services within
``~/jhbuild/install//share/dbus-1/services/``. Replace
``~/jhbuild/install`` with GNOME install ``prefix`` in the command
below:

::

   $ rm -rf ~/jhbuild/install/var/run/dbus
   $ ln -s /var/run/dbus ~/jhbuild/install/var/run/dbus
   $ rm -rf ~/jhbuild/install/var/lib/dbus/machine-id
   $ ln -s /var/lib/dbus/machine-id ~/jhbuild/install/var/lib/dbus/machine-id

Create a GNOME startup script at ``/usr/bin/gnome-jhbuild-session`` with
the following, replacing ``~/jhbuild/install`` with GNOME install
``prefix``:

::

   #!/bin/sh

   GNOME=~/jhbuild/install

   GDK_USE_XFT=1
   XDG_DATA_DIRS=$XDG_DATA_DIRS:$GNOME/share
   XDG_CONFIG_DIRS=$XDG_CONFIG_DIRS:$GNOME/etc/xdg

   jhbuild run gnome-session

Make the file ``/usr/bin/gnome-jhbuild-session`` executable:

::

   $ chmod a+x /usr/bin/gnome-jhbuild-session

To add a new session entry in the display manager, create
``/usr/share/xsessions/gnome-jhbuild.desktop`` and enter:

::

   [Desktop Entry]
   Name=GNOME (JHBuild)
   Comment=This session logs you into GNOME testing session
   TryExec=/usr/bin/gnome-jhbuild-session
   Exec=/usr/bin/gnome-jhbuild-session
   Icon=
   Type=Application

Restart ``gdm``.

Running GNOME from the display manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To run the JHBuild GNOME, select the GNOME (JHBuild) session at the
display manager before entering ``gnomedev`` login credentials. If
successful, JHBuild GNOME will be displayed. If unsuccessful, check the
log file. The log file will be located at
``~gnomedev/.cache/gdm/session.log`` or ``~gnomedev/.xsession-errors``.

Static Analysis
---------------

JHBuild supports running static analysis tools on the code in modules as
they’re built. To enable this, set the ``static_analyzer`` configuration
variable to ``True`` in the ``.jhbuildrc`` configuration file.

If enabled, every time a module is built using JHBuild, the build
process will be wrapped in a static analyzer, which will generate a
report of any problems it finds with the code. These reports are saved
as HTML files in subdirectories of ``/tmp/jhbuild_static_analyzer`` (by
default; the path can be changed using the ``static_analyzer_outputdir``
configuration variable).

Static analysis currently only works for modules which use autotools as
their build system. It requires the ``scan-build`` program to be
installed, although the command it uses can be changed by modifying the
``static_analyzer_template`` configuration variable.
