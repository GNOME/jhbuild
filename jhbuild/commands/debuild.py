# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   base.py: the most common jhbuild commands
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
from optparse import make_option
import sys
import md5
import urllib2
import re
import subprocess

try:
    import apt_pkg
except ImportError:
    apt_pkg = None

import jhbuild.moduleset
import jhbuild.frontends
from jhbuild.errors import UsageError, FatalError
from jhbuild.commands import Command, register_command

from jhbuild.utils.cache import get_cached_value, write_cached_value

debian_names = {
    'glib': 'glib2.0',
    'GConf': 'gconf2',
    'gconf': 'gconf2',
    'ORBit2': 'orbit2',
    'atk': 'atk1.0',
    'gtk+': 'gtk+2.0',
    'libIDL': 'libidl',
    'libart_lgpl': 'libart-lgpl',
    'pango': 'pango1.0',
    'gnome-vfs': 'gnome-vfs2',
    'libglade': 'libglade2',
    'eel': 'eel2',
    'gtk-engines': 'gtk2-engines',
    'libgtop': 'libgtop2',
    'gstreamer': 'gstreamer0.10',
    'gst-plugins-base': 'gst-plugins-base0.10',
    'gst-plugins-good': 'gst-plugins-good0.10',
    'epiphany': 'epiphany-browser',
    'gtkhtml': 'gtkhtml3.14',
    'gconfmm': 'gconfmm2.6',
    'glibmm': 'glibmm2.4',
    'gnome-vfsmm': 'gnome-vfsmm2.6',
    'gtkmm': 'gtkmm2.4',
    'libglademm': 'libglademm2.4',
    'libgnomecanvasmm': 'libgnomecanvasmm2.6',
    'libgnomemm': 'libgnomemm2.6',
    'libgnomeuimm': 'libgnomeuimm2.6',
    'libsigc++': 'libsigc++-2.0',
    'libxml++': 'libxml++2.6',
    'gnome-sharp': 'gtk-sharp2',
    'libgcrypt': 'libgcrypt11',
    'libIDL': 'libidl',
    'cairo': 'libcairo',
    'libtasn1': 'libtasn1-3',
    'opencdk': 'opencdk8',
    'gnutls': 'gnutls13',
    'mozilla': 'xulrunner',
    'gnome-control-center': 'control-center',
    'perl-net-dbus': 'libnet-dbus-perl',
    'libmusicbrainz': 'libmusicbrainz-2.1',
    'orca': 'orca-screen-reader',
    'gdm2': 'gdm',
    'NetworkManager': 'network-manager',
    'glade3': 'glade-3',
    'gtksourceview-1.0': 'gtksourceview',
    'libvolume_id': 'libvolume-id0',
    'libcolorblind': 'colorblind',
    'libsigc++-2.0': 'libsigc++2',
}

def url_cache_read(url, cache = True, prefix = ''):
    if cache:
        s = 'url-' + prefix + md5.md5(url).hexdigest()
        s2 = get_cached_value(s)
        if s2:
            return s2

    try:
        st = urllib2.urlopen(url).read()
    except:
        return ''
    if cache:
        write_cached_value(s, st)
    return st

def get_external_deps(gnome_version):
    name_mapping = {
        '2.18': 'TwoPointSeventeen',
        '2.20': 'TwoPointNineteen',
        '2.22': 'TwoPointTwentyone',
    }

    try:
        url = 'http://live.gnome.org/%s/ExternalDependencies' % name_mapping[gnome_version]
    except KeyError:
        return {}

    s = url_cache_read(url)

    current_deps = s[s.find('Current Dependencies</h2>'):]
    current_deps = current_deps[:current_deps.find('</table>')]

    tr_re = re.compile('<tr(.*?)/tr>', re.DOTALL)

    modules = {}
    for tr in tr_re.findall(current_deps):
        if '<strong>Module' in tr:
            continue
        module, minimum, recommended, download = [x[x.rindex('>')+1:].strip() for x in re.findall('>(.*)</td>', tr)]
        if '(' in minimum:
            minimum = minimum.split('(')[0].strip()
        if '(' in recommended:
            recommended = recommended.split('(')[0].strip()

        if recommended == 'same':
            recommended = minimum
        modules[module] = {
            'minimum': minimum,
            'recommended': recommended
        }

    # XXX: missing external dependencies
    modules['scrollkeeper'] = {
        'minimum': '0.3.14',
        'recommended': '0.3.14',
    }
    modules['audiofile'] = {
        'minimum': '0.2.6',
        'recommended': '0.2.6',
    }
    modules['perl-net-dbus'] = {
        'minimum': '0.33.2',
        'recommended': '0.33.2',
    }

    ### extra external dependencies

    # esound is no longer developed, and heavily patched in Debian
    modules['esound'] = {
        'minimum': '0.2.35',
        'recommended': '0.2.35',
    }

    # gstreamer from debian is good enough
    modules['gstreamer'] = {
        'minimum': '0.10.10',
        'recommended': '0.10.10'
    }
    modules['gst-plugins-base'] = modules['gstreamer']
    modules['gst-plugins-good'] = {
        'minimum': '0.10.4',
        'recommended': '0.10.4'
    }

    modules['libvolume_id'] = {
        'minimum': '0.105',
        'recommended': '0.105',
    }

    ### extra hacks
    modules['mozilla'] = {
       'minimum': '1.8.1',
       'recommended': '1.8.1',
    } 

    return modules

def debuild_init(config, buildscript):
    # perform a deb build
    config.debuild = True

    if type(config.moduleset) is list:
        moduleset = config.moduleset[0]
    else:
        moduleset = config.moduleset

    gnome_version = moduleset.split('-')[-1]

    config.external_dependencies = get_external_deps(gnome_version)
    config.debian_names = debian_names

    config.tarballs_dir = os.path.expanduser('~/.jhdebuild/tarballs')
    if not os.path.exists(config.tarballs_dir):
        os.makedirs(config.tarballs_dir)

    if not os.path.exists(config.checkoutroot):
        os.makedirs(config.checkoutroot)

    for module in config.debian_checkout_modules:
        module_dir = os.path.join(config.checkoutroot, module)
        if not os.path.exists(module_dir):
            buildscript.set_action('Getting repository', None, 0, module)
            buildscript.execute(['svn', 'checkout', 'svn://svn.debian.org/%s/' % module],
                    cwd = config.checkoutroot)
        else:
            buildscript.set_action('Updating repository', None, 0, module)
            buildscript.execute(['svn', 'update'], cwd = module_dir)

        output = subprocess.Popen(['svn', 'status'],
                stdout = subprocess.PIPE, cwd = module_dir).communicate()[0]
        for line in output.splitlines():
            if line.startswith('C '):
                buildscript.execute(['svn', 'status'], 'svn', cwd = module_dir)
                raise FatalError('Conflicts in Debian pkg- repository')
        
    apt_pkg.init()


class cmd_debuild(Command):
    """Build Debian packages."""

    name = 'debuild'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-s', '--skip', metavar='MODULES',
                        action='append', dest='skip', default=[],
                        help='treat the given modules as up to date'),
            make_option('-t', '--start-at', metavar='MODULE',
                        action='store', dest='startat', default=None,
                        help='start building at the given module'),
            make_option('--no-dinstall',
                        action='store_true', dest='nodinstall', default=False,
                        help='skip dinstall run'),
            ])

    def run(self, config, options, args):
        if options.nodinstall:
            config.nodinstall = True

        for item in options.skip:
            config.skip += item.split(',')

        module_set = jhbuild.moduleset.load(config)
        module_list = module_set.get_module_list(args or config.modules,
                                                 config.skip)
        # remove modules up to startat
        if options.startat:
            while module_list and module_list[0].name != options.startat:
                del module_list[0]
            if not module_list:
                raise FatalError('%s not in module list' % options.startat)

        build = jhbuild.frontends.get_buildscript(config, module_list)
        debuild_init(config, build)
        build.build()

register_command(cmd_debuild)


class cmd_debuildone(Command):
    """Build a Debian package."""

    name = 'debuildone'
    usage_args = '[ options ... ] [ modules ... ]'

    def __init__(self):
        Command.__init__(self, [
            make_option('-a', '--autogen',
                        action='store_true', dest='autogen', default=False,
                        help='always run autogen.sh'),
            make_option('-c', '--clean',
                        action='store_true', dest='clean', default=False,
                        help='run make clean before make'),
            make_option('--no-dinstall',
                        action='store_true', dest='nodinstall', default=False,
                        help='skip dinstall run'),
            make_option('--build-external-deps',
                        action='store', dest='build_external_deps',
                        help='build external deps (never/minimum/recommended/always)')
            ])

    def run(self, config, options, args):
        if options.autogen:
            config.alwaysautogen = True
        if options.clean:
            config.makeclean = True
        if options.nodinstall:
            config.nodinstall = True
        if options.build_external_deps:
            config.build_external_deps = options.build_external_deps

        module_set = jhbuild.moduleset.load(config)
        try:
            module_list = [module_set.modules[modname] for modname in args]
        except KeyError, e:
            raise FatalError("A module called '%s' could not be found."
                             % str(e))

        build = jhbuild.frontends.get_buildscript(config, module_list)
        debuild_init(config, build)
        build.build()

register_command(cmd_debuildone)

