import os
import re
import glob
import apt_pkg

from jhbuild.errors import FatalError, CommandError, BuildStateError

from jhbuild.modtypes import Package, SkipToState
from jhbuild.utils import debian

class DebianBasePackage:

    STATE_TAR_X          = 'tar_x'
    STATE_DEBIAN_DIR     = 'debian_dir'
    STATE_BUILD_PACKAGE  = 'build_package'
    STATE_DINSTALL       = 'dinstall'
    STATE_UPGRADE        = 'upgrade'

    def do_deb_build_deps(self, buildscript):
        if os.path.exists(self.get_tarball_dir(buildscript)):
            buildscript.message('%s already has a tarball' % self.name)
            next_state = self.STATE_TAR_X
        else:
            next_state = self.STATE_CONFIGURE
        Package.do_deb_build_deps(self, buildscript)
        raise SkipToState(next_state)


    def skip_deb_debian_dir(self, buildscript, last_state):
        return False

    def do_deb_debian_dir(self, buildscript):
        buildscript.set_action('Getting a debian/ directory for', self)

        debian_name = self.get_debian_name(buildscript)

        pkg_dirs = []
        for pkg_dir in buildscript.config.debian_checkout_modules or []:
            pkg_dirs.extend(glob.glob('%s/%s/*/%s' % (
                buildscript.config.checkoutroot, pkg_dir, debian_name)))
            pkg_dirs.extend(glob.glob('%s/%s/*/*/%s' % (
                buildscript.config.checkoutroot, pkg_dir, debian_name)))
        versions = []
        for p in pkg_dirs:
            if not buildscript.config.nonetwork:
                buildscript.execute(['svn', 'update'], cwd = p)
            chl = os.path.join(p, 'debian', 'changelog')
            if not os.path.exists(chl):
                continue
            first_line = file(chl).readline()
            version = re.findall(r'\((.*?)\)', first_line)
            if version:
                versions.append((p, version[0]))
        versions.sort(lambda x, y: apt_pkg.VersionCompare(x[-1],y[-1]))

        builddebdir = self.get_builddebdir(buildscript)
        distdir = self.get_distdir(buildscript)

        buildscript.execute(['rm', '-rf', os.path.join(distdir, 'debian')], cwd = builddebdir)

        if versions:
            dir = os.path.join(versions[-1][0], 'debian')
            buildscript.execute(['cp', '-R', dir, distdir + '/'], cwd = builddebdir)
            base_dir = os.path.join(builddebdir, distdir, 'debian')
            for base, dirs, files in os.walk(base_dir, topdown = False):
                if '.svn' in dirs:
                    buildscript.execute(['rm', '-rf', os.path.join(base, '.svn')],
                            cwd = base_dir)
        else:
            deb_sources = os.path.join(buildscript.config.checkoutroot, 'deb-src')
            if not os.path.exists(deb_sources):
                os.makedirs(deb_sources)

            try:
                buildscript.execute(['apt-get', 'source', debian_name], cwd = deb_sources)
            except CommandError:
                raise BuildStateError('No debian source package for %s' % self.name)

            dir = [x for x in os.listdir(deb_sources) if (
                    x.startswith(debian_name) and os.path.isdir(os.path.join(deb_sources, x)))][0]

            buildscript.execute(['cp', '-R', os.path.join(deb_sources, dir, 'debian'), distdir + '/'],
                    cwd = builddebdir)

        debian_dir = os.path.join(builddebdir, distdir, 'debian')
        if os.path.exists(os.path.join(debian_dir, 'patches')):
            for patch_filename in ('libtoolize', 'reautogen', 'as-needed'):
                for filename in os.listdir(os.path.join(debian_dir, 'patches')):
                    if patch_filename in filename:
                        buildscript.execute(['rm', '%s/debian/patches/%s' % (distdir, filename)],
                                cwd = builddebdir)
                        break
                if os.path.exists(os.path.join(debian_dir, 'patches', 'series')):
                    series = open(os.path.join(debian_dir, 'patches', 'series')).readlines()
                    open(os.path.join(debian_dir, 'patches', 'series'), 'w').write(''.join(
                            [x for x in series if not filename in x]))
                if os.path.exists(os.path.join(debian_dir, 'patches', '00list')):
                    series = open(os.path.join(debian_dir, 'patches', '00list')).readlines()
                    open(os.path.join(debian_dir, 'patches', '00list'), 'w').write(''.join(
                            [x for x in series if not filename in x]))

        os.chmod(os.path.join(builddebdir, distdir, 'debian', 'rules'), 0755)
    do_deb_debian_dir.next_state = STATE_BUILD_PACKAGE
    do_deb_debian_dir.error_states = []

    def skip_deb_build_package(self, buildscript, next_state):
        builddebdir = self.get_builddebdir(buildscript)
        changes_file = self.get_changes_file(buildscript)
        if changes_file and os.path.exists(os.path.join(builddebdir, changes_file)):
            return True

        version = debian.get_version(buildscript, self.get_debian_name(buildscript))
        if version == self.get_debian_version(buildscript):
            return True

        return False

    def do_deb_build_package(self, buildscript):
        buildscript.set_action('Building package', self)
        builddebdir = self.get_builddebdir(buildscript)
        debian_version = self.get_debian_version(buildscript)
        builddebdir = os.path.join(self.get_builddebdir(buildscript), self.get_distdir(buildscript))
        if debian_version not in open(os.path.join(builddebdir, 'debian', 'changelog')).readline():
            buildscript.execute(['debchange', '--preserve', '-v', debian_version,
                    '--distribution', 'UNRELEASED', 'jhdebuild snapshot'],
                    cwd = builddebdir)

        l = debian.check_build_depends(os.path.join(builddebdir, 'debian', 'control'))
        if l:
            # first phase is installing packages where there is no alternatives
            command = ['sudo', 'apt-get', '--yes', 'install']
            command.extend([x[0] for x in l if len(x) == 1])
            try:
                buildscript.execute(command)
            except CommandError:
                raise BuildStateError('failed to install build deps (%s)' % ', '.join(command[3:]))
            l = debian.check_build_depends(os.path.join(builddebdir, 'debian', 'control'))
            for ps in l:
                for p in ps:
                    try:
                        buildscript.execute(['sudo', 'apt-get', '--yes', 'install', p])
                    except CommandError:
                        break
                else:
                    raise BuildStateError('failed to install build deps (%s)' % ' | '.join(ps))

            l = debian.check_build_depends(os.path.join(builddebdir, 'debian', 'control'))
            if l:
                raise BuildStateError('failed to install build deps (%s)' % ', '.join(
                        [' | '.join([y for y in x]) for x in l]))

        buildscript.execute(['dpkg-buildpackage','-rfakeroot', '-us', '-uc', '-D'],
                cwd = builddebdir)
    do_deb_build_package.next_state = STATE_DINSTALL
    do_deb_build_package.error_states = [STATE_DEBIAN_DIR]

    def get_changes_file(self, buildscript):
        debian_name = self.get_debian_name(buildscript)
        deb_version = self.get_debian_version(buildscript)
        if ':' in deb_version:
            deb_version = deb_version.split(':')[-1] # remove epoch
        builddebdir = self.get_builddebdir(buildscript)
        changes_file = [x for x in os.listdir(builddebdir) if (
                x.startswith('%s_%s' % (debian_name, deb_version)) and x.endswith('.changes'))]
        if not changes_file:
            return None
        return changes_file[0]

    def skip_deb_dinstall(self, buildscript, next_state):
        version = debian.get_version(buildscript, self.get_debian_name(buildscript))
        if version == self.get_debian_version(buildscript):
            return True

        return buildscript.config.nodinstall

    def do_deb_dinstall(self, buildscript):
        buildscript.set_action('Installing into repository', self)
        builddebdir = self.get_builddebdir(buildscript)
        changes_file = self.get_changes_file(buildscript)
        if changes_file is None:
            raise BuildStateError('no .changes file')
        changes_file = os.path.join(builddebdir, changes_file)
        debian.install_changes(buildscript, changes_file)

        # packages have been installed in repository, remove them from here
        in_files = False
        files = [changes_file]
        for line in open(changes_file).readlines():
            if line.startswith('Files:'):
                in_files = True
                continue
            if not in_files:
                continue
            if line and line[0] == ' ':
                files.append(os.path.join(builddebdir, line.split()[-1]))
        for f in files:
            os.unlink(f)
    do_deb_dinstall.next_state = STATE_UPGRADE
    do_deb_dinstall.error_states = []

    def skip_deb_upgrade(self, buildscript, last_state):
        return False

    def do_deb_upgrade(self, buildscript):
        buildscript.set_action('Upgrading packages', self)
        if not buildscript.config.nonetwork:
            buildscript.execute(['sudo', 'apt-get', 'update'])
            buildscript.execute(['sudo', 'apt-get', '--yes', 'upgrade'])
    do_deb_upgrade.next_state = Package.STATE_DONE
    do_deb_upgrade.error_states = []

    def get_version(self, buildscript):
        raise NotImplementedError

