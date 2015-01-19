#!/usr/bin/env python2

from email.utils import formataddr
import email.generator
import email.message
import subprocess
import sys
import ast

if len(sys.argv) != 3:
    print "error: must give a sysid and Debian package name to create"
    print "example:\n\n   ./debian-mkequivs.py debian-8 jhbuild-sysdeps"
    sys.exit(1)

myid = sys.argv[1]

debian_sysdeps = ast.literal_eval(open('../data/debian-sysdeps.py').read())

if not myid in debian_sysdeps:
    print "error: don't know about a release called '{}'".format(myid)
    sys.exit(1)

package_list = dict(debian_sysdeps[myid])
package_list.update(debian_sysdeps['common'])
depends = []

for line in sys.stdin:
    dep = line.strip()

    if dep in package_list:
        depends.append(' | '.join (pkg.split('/')[-1] for pkg in package_list[dep]))
    else:
        print "warning: don't know how to satisfy '{}'".format(dep)


control = email.message.Message()
control['Package'] = sys.argv[2]
control['Depends'] = ', '.join (depends)
try:
    control['Maintainer'] = formataddr((subprocess.check_output(['git', 'config', 'user.name']).strip(),
                                        subprocess.check_output(['git', 'config', 'user.email']).strip()))
except: pass
control['Description'] = 'jhbuild dependencies meta-package\nSee https://wiki.gnome.org/HowDoI/Jhbuild for more info'
control['Readme'] = '/dev/null'
equivs = subprocess.Popen(['equivs-build', '-'], stdin = subprocess.PIPE)
email.generator.Generator(equivs.stdin).flatten(control)
equivs.stdin.close()
equivs.wait()
