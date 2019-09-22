# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
#   sanitycheck.py: check whether build environment is sane
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os

from jhbuild.commands import Command, register_command
from jhbuild.utils.cmds import get_output, check_version
from jhbuild.utils import inpath, uprint, N_, _
from jhbuild.errors import UsageError, CommandError

def get_aclocal_path():
    # drop empty paths, including the case where ACLOCAL_PATH is unset
    path = [x for x in os.environ.get('ACLOCAL_PATH', '').split(':') if x]
    data = get_output(['aclocal', '--print-ac-dir'])
    path.append(data[:-1])
    return path


class cmd_sanitycheck(Command):
    doc = N_('Check that required support tools are available')

    name = 'sanitycheck'
    usage_args = ''

    def run(self, config, options, args, help=None):
        if args:
            raise UsageError(_('no extra arguments expected'))

        # try creating jhbuild directories before checking they are accessible.
        try:
            os.makedirs(config.checkoutroot)
            os.makedirs(config.prefix)
        except OSError:
            pass

        # check whether the checkout root and install prefix are writable
        if not (os.path.isdir(config.checkoutroot) and
                os.access(config.checkoutroot, os.R_OK|os.W_OK|os.X_OK)):
            uprint(_('checkout root (%s) is not writable') % config.checkoutroot)
        if not (os.path.isdir(config.prefix) and
                os.access(config.prefix, os.R_OK|os.W_OK|os.X_OK)):
            uprint(_('install prefix (%s) is not writable') % config.prefix)

        autoconf = True

        # check whether various tools are installed
        if not check_version(['libtoolize', '--version'],
                             r'libtoolize \([^)]*\) ([\d.]+)', '1.5'):
            uprint(_('%s not found') % 'libtool >= 1.5')
        if not check_version(['gettext', '--version'],
                             r'gettext \([^)]*\) ([\d.]+)', '0.10.40'):
            uprint(_('%s not found') % 'gettext >= 0.10.40')
        if not check_version(['pkg-config', '--version'],
                             r'^([\d.]+)', '0.14.0'):
            uprint(_('%s not found') % 'pkg-config >= 0.14.0')
        if not check_version(['autoconf', '--version'],
                             r'autoconf \([^)]*\) ([\d.]+)', '2.53'):
            autoconf = False
            uprint(_('%s not found') % 'autoconf >= 2.53')
        if not check_version(['automake', '--version'],
                             r'automake \([^)]*\) ([\d.]+)', '1.10'):
            uprint(_('%s not found') % 'automake >= 1.10')

        if (autoconf):
            self.check_m4()

        # XML catalog sanity checks
        xmlcatalog = True
        try:
            get_output(['which', 'xmlcatalog'])
        except CommandError:
            xmlcatalog = False
            uprint(_('Could not find XML catalog (usually part of the package \'libxml2-utils\')'))

        if (xmlcatalog):
            for (item, name) in [('-//OASIS//DTD DocBook XML V4.1.2//EN',
                                  'DocBook XML DTD V4.1.2'),
                                 ('http://docbook.sourceforge.net/release/xsl/current/html/chunk.xsl',
                                  'DocBook XSL Stylesheets')]:
                try:
                    get_output(['xmlcatalog', '/etc/xml/catalog', item])
                except CommandError:
                    uprint(_('Could not find %s in XML catalog (usually part of package \'docbook-xsl\')') % name)

        # Perl module used by tools such as intltool:
        perlmod = 'XML::Parser'
        try:
            get_output(['perl', '-M%s' % perlmod, '-e', 'exit'])
        except CommandError:
            uprint(_('Could not find the Perl module %s (usually part of package \'libxml-parser-perl\' or \'perl-XML-Parser\')') % perlmod)

        # check for a downloading util:
        if not (inpath('curl', os.environ['PATH'].split(os.pathsep)) or
                inpath('wget', os.environ['PATH'].split(os.pathsep))):
            uprint(_('curl or wget not found'))

        # check for git:
        if not inpath('git', os.environ['PATH'].split(os.pathsep)):
            uprint(_('%s not found') % 'git')
        else:
            try:
                git_help = os.popen('git --help', 'r').read()
                if 'clone' not in git_help:
                    uprint(_('Installed git program is not the right git'))
                else:
                    if not check_version(['git', '--version'],
                                 r'git version ([\d.]+)', '1.5.6'):
                        uprint(_('%s not found') % 'git >= 1.5.6')
            except EnvironmentError:
                uprint(_('Could not check git program'))

        # check for flex/bison:
        if not inpath('flex', os.environ['PATH'].split(os.pathsep)):
            uprint(_('%s not found') % 'flex')
        if not inpath('bison', os.environ['PATH'].split(os.pathsep)):
            uprint(_('%s not found') % 'bison')
        if not inpath('xzcat', os.environ['PATH'].split(os.pathsep)):
            uprint(_('%s not found') % 'xzcat')

        # check for "sysdeps --install" deps:
        try:
            from gi.repository import GLib
            GLib
        except ImportError:
            uprint(_('%s not found') % 'python-gobject')
        try:
            import dbus.glib
            dbus.glib
        except ImportError:
            uprint(_('%s not found') % 'dbus-python')

    def check_m4(self):
        try:
            not_in_path = []
            path = get_aclocal_path()

            macros = ['libtool.m4', 'gettext.m4', 'pkg.m4']
            for macro in macros:
                if not inpath (macro, path):
                    uprint(_("aclocal can't see %s macros") % (macro.split('.m4')[0]))
                    if not_in_path.count(macro) == 0:
                        not_in_path.append(macro)

            if len(not_in_path) > 0:
                uprint(_("Please copy the lacking macros (%(macros)s) in one of the following paths: %(path)s") % \
                       {'macros': ', '.join(not_in_path), 'path': ', '.join(path)})

        except CommandError as exc:
            uprint(str(exc))

register_command(cmd_sanitycheck)
