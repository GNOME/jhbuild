import os
import re
import glob
import apt_pkg

from jhbuild.errors import FatalError, CommandError, BuildStateError

from jhbuild.modtypes import Package
from jhbuild.utils import debian

try:
    import apt_pkg
except ImportError:
    apt_pkg = None

def lax_int(s):
    try:
        return int(s)
    except ValueError:
        return -1


class DebianBasePackage:
    PHASE_APT_GET_UPDATE = 'deb_apt_get_update'
    PHASE_BUILD_DEPS     = 'deb_build_deps'
    PHASE_DEB_DIST       = 'deb_dist'
    PHASE_TAR_X          = 'deb_tar_x'
    PHASE_DEBIAN_DIR     = 'deb_debian_dir'
    PHASE_BUILD_PACKAGE  = 'deb_build_package'
    PHASE_DINSTALL       = 'deb_dinstall'
    PHASE_UPGRADE        = 'deb_upgrade'

    def do_deb_start(self, buildscript):
        buildscript.set_action('Starting building', self)
        ext_dep = buildscript.config.external_dependencies.get(self.name)
        if ext_dep:
            available = self.get_available_debian_version(buildscript).split('-')[0]
            if ':' in available: # remove epoch
                available = available.split(':')[-1]

            deb_available = [lax_int(x) for x in available.split('.')]
            ext_minimum = [lax_int(x) for x in ext_dep.get('minimum').split('.')]
            ext_recommended = [lax_int(x) for x in ext_dep.get('recommended').split('.')]

            if deb_available >= ext_recommended:
                buildscript.message('external dependency, available')
                if not buildscript.config.build_external_deps == 'always':
                    raise SkipToEnd()

            if deb_available >= ext_minimum:
                buildscript.message(
                        'external dependency, available (but recommended version is not)')
                if not buildscript.config.build_external_deps in ('always', 'recommended'):
                    raise SkipToEnd()
            else:
                buildscript.message('external dependency, no version high enough')
                if buildscript.config.build_external_deps == 'never':
                    raise SkipToEnd()
    do_deb_start.error_phases = []

    def do_deb_apt_get_update(self, buildscript):
        if not buildscript.config.nonetwork:
            buildscript.set_action('Updating packages database for', self)
            try:
                buildscript.execute(['sudo', 'apt-get', 'update'])
            except CommandError:
                pass
    do_deb_apt_get_update.error_phases = []

    def do_deb_build_deps(self, buildscript):
        buildscript.set_action('Installing build deps for', self)
        debian_name = self.get_debian_name(buildscript)
        v = None
        try:
            v = self.get_available_debian_version(buildscript)
        except KeyError:
            pass
        if v:
            try:
                buildscript.execute(['sudo', 'apt-get', '--yes', 'build-dep', debian_name])
            except CommandError:
                raise BuildStateError('Failed to install build deps')
    do_deb_build_deps.error_phases = []
    do_deb_build_deps.depends = [PHASE_APT_GET_UPDATE]

    def skip_deb_tar_x(self, buildscript, last_state):
        if os.path.exists(self.get_tarball_dir(buildscript)):
            buildscript.message('%s already has a tarball' % self.name)
            return True
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
    do_deb_debian_dir.error_phases = []
    do_deb_debian_dir.depends = [PHASE_TAR_X]

    def skip_deb_build_package(self, buildscript, last_state):
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
    do_deb_build_package.error_phases = [PHASE_DEBIAN_DIR]
    do_deb_build_package.depends = [PHASE_DEBIAN_DIR]

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

    def skip_deb_dinstall(self, buildscript, last_state):
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
    do_deb_dinstall.error_phases = []

    def do_deb_upgrade(self, buildscript):
        buildscript.set_action('Upgrading packages', self)
        if not buildscript.config.nonetwork:
            buildscript.execute(['sudo', 'apt-get', 'update'])
            buildscript.execute(['sudo', 'apt-get', '--yes', 'upgrade'])
    do_deb_upgrade.error_phases = []

    def get_version(self, buildscript):
        raise NotImplementedError

    def get_builddebdir(self, buildscript):
        return os.path.normpath(os.path.join(self.get_builddir(buildscript), '..', 'debian'))

    def get_debian_name(self, buildscript):
        debian_name = buildscript.config.debian_names.get(self.name)
        if not debian_name:
            debian_name = self.name
        return debian_name

    def get_one_binary_package_name(self, buildscript):
        debian_name = self.get_debian_name(buildscript)
        sources = apt_pkg.GetPkgSrcRecords()
        sources.Restart()
        t = []
        while sources.Lookup(debian_name):
            try:
                t.append((sources.Package, sources.Binaries, sources.Version))
            except AttributeError:
                pass
        if not t:
            raise KeyError
        t.sort(lambda x, y: apt_pkg.VersionCompare(x[-1],y[-1]))
        return t[-1][1][0]

    def get_available_debian_version(self, buildscript):
        apt_cache = apt_pkg.GetCache()
        binary_name = self.get_one_binary_package_name(buildscript)
        for pkg in apt_cache.Packages:
            if pkg.Name == binary_name:
                t = list(pkg.VersionList)
                t.sort(lambda x, y: apt_pkg.VersionCompare(x.VerStr, y.VerStr))
                return t[-1].VerStr
        return None

    def get_installed_debian_version(self):
        apt_cache = apt_pkg.GetCache()
        for pkg in apt_cache.Packages:
            if pkg.Name == self.name:
                return pkg.CurrentVer.VerStr
        return None

    def create_a_debian_dir(self, buildscript):
        buildscript.set_action('Getting a debian/ directory for', self)
        builddir = self.get_builddir(buildscript)
        deb_sources = os.path.expanduser('~/.jhdebuild/apt-get-sources/')
        if not os.path.exists(deb_sources):
            os.makedirs(deb_sources)

        debian_name = self.get_debian_name(buildscript)

        try:
            buildscript.execute(['apt-get', 'source', debian_name], cwd = deb_sources)
        except CommandError:
            raise BuildStateError('No debian source package for %s' % self.name)

        dir = [x for x in os.listdir(deb_sources) if (
                x.startswith(debian_name) and os.path.isdir(os.path.join(deb_sources, x)))][0]
        buildscript.execute(['rm', '-rf', 'debian/*'], cwd = builddir)
        if not os.path.exists(os.path.join(builddir, 'debian')):
            os.mkdir(os.path.join(builddir, 'debian'))
        buildscript.execute('cp -R %s/* debian/' % os.path.join(deb_sources, dir, 'debian'),
                cwd = builddir)
        file(os.path.join(builddir, 'debian', 'APPROPRIATE_FOR_JHDEBUILD'), 'w').write('')

    def get_makefile_var(self, buildscript, variable_name):
        builddir = self.get_builddir(buildscript)
        makefile = os.path.join(builddir, 'Makefile')
        if not os.path.exists(makefile):
            return None
        v = re.findall(r'\b%s *= *(.*)' % variable_name, open(makefile).read())
        if v:
            return v[0]
        else:
            return None

