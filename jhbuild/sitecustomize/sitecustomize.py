from distutils import sysconfig
import sys
import os

if 'JHBUILD_PREFIXES' in os.environ:
    for prefix in reversed(os.environ['JHBUILD_PREFIXES'].split(':')):
        sitedir = sysconfig.get_python_lib(prefix=prefix)

        # if it is in there already, promote it
        if sitedir in sys.path:
            sys.path.remove(sitedir)

        sys.path.insert(1, sitedir)
