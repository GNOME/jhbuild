import base

class Tarball(base.Package):
    STATE_DOWNLOAD  = 'download'
    STATE_UNPACK    = 'unpack'
    STATE_PATCH     = 'patch'
    STATE_CONFIGURE = 'configure'
    STATE_BUILD     = 'build'
    STATE_INSTALL   = 'install'
    def __init__(self, name, version, source_url, source_size,
                 patches=[], versioncheck=None, dependencies=[]):
        base.Package.__init__(self, name, dependencies)
        self.version      = version
        self.source_url   = source_url
        self.source_size  = source_size
        self.patches      = []
        self.versioncheck = versioncheck

    def get_builddir(self, buildscript):
        localfile = os.path.basename(self.source_url)
        # strip off packaging extension ...
        if localfile.endswith('.tar.gz'):
            localfile = localfile[:-7]
        elif localfile.endswith('.tar.bz2'):
            localfile = localfile[:-8]
        elif localfile.endswith('.tgz'):
            localfile = localfile[:-4]
        return os.path.join(buildscript.config.checkoutroot, localfile)

    def do_start(self, buildscript):
        # check if jhbuild previously built it ...
        checkoutdir = self.get_builddir(buildscript)
        if os.path.exists(os.path.join(checkoutdir, 'jhbuild-build-stamp')):
            return (self.STATE_DONE, None, None)

        # check if we already have it ...
        if self.versioncheck:
            out = os.popen(self.versioncheck, 'r').read()
            if out and string.find(out, self.version) >= 0:
                return (self.STATE_DONE, None, None)

        return (self.STATE_DOWNLOAD, None, None)

    def do_download(self, buildscript):
        localfile = os.path.join(buildscript.config.checkoutroot,
                                 os.path.basename(self.source_url))
        if not buildscript.config.nonetwork:
            if (not os.path.exists(localfile) or
                os.stat(localfile)[6] != self.source_size):
                buildscript.set_action('Downloading', self, action_target=self.source_url)
                res = buildscript.execute('wget "%s" -O "%s"' %
                                          (self.source_url, localfile))
                if res:
                    return (self.STATE_UNPACK, 'error downloading file', [])

        if not os.path.exists(localfile) or \
               os.stat(localfile)[6] != self.source_size:
            return (self.STATE_UNPACK,
                    'file not downloaded, or of incorrect size', [])
        return (self.STATE_UNPACK, None, None)

    def do_unpack(self, buildscript):
        os.chdir(buildscript.config.checkoutroot)
        localfile = os.path.basename(self.source_url)
        checkoutdir = self.get_builddir(buildscript)

        buildscript.set_action('Unpacking', self)
        if localfile.endswith('.bz2'):
            res = buildscript.execute('bunzip2 -dc %s | tar xf -' % localfile)
        elif localfile.endswith('.gz'):
            res = buildscript.execute('gunzip -dc %s | tar xf -' % localfile)
        else:
            raise TypeError, "don't know how to handle: %s" % localfile
        
        if res or not os.path.exists(checkoutdir):
            return (self.STATE_PATCH, 'could not unpack tarball', [])

        return (self.STATE_PATCH, None, None)

    def do_patch(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        
        for patch in self.patches:
            patchfile = os.path.join(os.path.dirname(__file__), patch[0])
            buildscript.set_action('Applying Patch', self, action_target=patch[0])
            res = buildscript.execute('patch -p%d < %s' % (patch[1],patchfile))
            if res:
                return (self.STATE_CONFIGURE, 'could not apply patch', [])
            
        if buildscript.config.nobuild:
            return (self.STATE_DONE, None, None)
        else:
            return (self.STATE_CONFIGURE, None, None)

    def do_configure(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Configuring', self)
        cmd = './configure --prefix %s' % buildscript.config.prefix
        if buildscript.config.use_lib64:
            cmd += " --libdir '${exec_prefix}/lib64'"
        ret = buildscript.execute(cmd)
        error = None
        if res != 0:
            error = 'could not configure package'
        return (self.STATE_BUILD, error, [])

    def do_build(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Building', self)
        cmd = 'make %s' % buildscript.config.makeargs
        if buildscript.execute(cmd) == 0:
            return (self.STATE_INSTALL, None, None)
        else:
            return (self.STATE_INSTALL, 'could not build module', [])

    def do_install(self, buildscript):
        os.chdir(self.get_builddir(buildscript))
        buildscript.set_action('Installing', self)
        cmd = 'make %s install' % buildscript.config.makeargs
        error = None
        if buildscript.execute(cmd) != 0:
            error = 'could not make module'
        else:
            open('jhbuild-build-stamp', 'w').write('stamp')
        return (self.STATE_DONE, error, [])

def parse_tarball(node, config, dependencies, cvsroot):
    name = node.getAttribute('id')
    version = node.getAttribute('version')
    versioncheck = None
    source_url = None
    source_size = None
    patches = []
    dependencies = []
    if node.hasAttribute('versioncheck'):
        versioncheck = node.getAttribute('versioncheck')
    for childnode in node.childNodes:
        if childnode.nodeType != childnode.ELEMENT_NODE: continue
        if childnode.nodeName == 'source':
            source_url = childnode.getAttribute('href')
            source_size = int(childnode.getAttribute('size'))
        elif childnode.nodeName == 'patches':
            for patch in childnode.childNodes:
                if patch.nodeType == dep.ELEMENT_NODE:
                    assert patch.nodeName == 'patch'
                    text = ''.join([node.data
                                    for node in patch.childNodes
                                    if node.nodeType==node.TEXT_NODE])
                    patch.append(text)

    return Tarball(name, version, source_url, source_size,
                   patches, versioncheck, dependencies)

base.register_module_type('tarball', parse_tarball)
