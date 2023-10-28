import sys
import os

if sys.version_info.major > 3 or sys.version_info.minor >= 12:
    from setuptools._distutils import sysconfig
else:
    from distutils import sysconfig

if 'JHBUILD_PREFIX' in os.environ:
    sys.path.insert(1, os.environ['JHBUILD_PREFIX'] + '/lib/python3/dist-packages')

if 'JHBUILD_PREFIXES' in os.environ:
    for prefix in reversed(os.environ['JHBUILD_PREFIXES'].split(':')):
        sitedir = sysconfig.get_python_lib(prefix=prefix)

        # if it is in there already, promote it
        if sitedir in sys.path:
            sys.path.remove(sitedir)

        sys.path.insert(1, sitedir)

        # work around https://bugzilla.redhat.com/show_bug.cgi?id=1076293
        sitedir2 = sysconfig.get_python_lib(1, prefix=prefix)
        if sitedir2 != sitedir:
            if sitedir2 in sys.path:
                sys.path.remove(sitedir2)
            sys.path.insert(1, sitedir2)
