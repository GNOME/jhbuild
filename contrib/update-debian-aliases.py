import subprocess
import os

# Read in a list of packages from jhbuild
# FIXME: Ideally this would be a list of modules that satisfy dependencies
# rather than all modules
#  At the moment it just operates on output of 'jhbuild list > feed'
aliases = {}
for pkg in open('feed').read().split('\n'):
    if pkg.startswith("meta"):
         continue
    aliases[pkg] = None
pkgs = set(aliases.keys())

# Try to find mappings based on pkg-config files
p = subprocess.Popen(['apt-file', 'search', '/pkgconfig/'], stdout=subprocess.PIPE)
stdout, stderr = p.communicate()
for line in stdout.split('\n'):
    if not ": " in line:
        continue
    package, pcfile = line.split(": ")
    pcfile = os.path.basename(pcfile)[:-3]
    if pcfile in pkgs:
        aliases[pcfile] = package
    if 'lib'+pcfile in pkgs:
        aliases['lib'+pcfile] = package

def generate_variants(name):
    lower = name.lower()
    if lower.startswith("lib"):
        yield lower+"-dev"
    else:
        yield lower
        yield lower + "-dev"
        yield "lib" + lower + "-dev"
    if lower.endswith("-python"):
        yield "python-" + lower[:-7]
    if "-python-" in lower:
        yield "python-" + lower.replace("-python-", "-")

def simplify(name):
    s = name.lower().replace("-","").replace(".","")
    for i in range(0,10):
        s = s.replace(str(i),"")
    return s

# Try and find package names (and variants) in app
import apt
c = apt.Cache()
apt_pkgs = set(c.keys())

hashes = {}
for pkg in apt_pkgs:
    hashes.setdefault(simplify(pkg), []).append(pkg)

for pkg in pkgs:
    for variant in generate_variants(pkg):
        if variant in apt_pkgs:
            aliases[pkg] = variant
        elif simplify(variant) in hashes:
            x = hashes[simplify(variant)][:]
            x.sort()
            if len(x) > 1:
                #print "Multiple matches: %s %s [%s]" % (pkg, len(x), " ".join(x))
                pass
            aliases[pkg] = x[-1]

print "aliases = {"
for k, v in aliases.iteritems():
    print "    '%s':'%s'," % (k, v)
print "}"
