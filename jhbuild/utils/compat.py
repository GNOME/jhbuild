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

import sys


PY2 = sys.version_info[0] == 2
PY3 = not PY2

if PY2:
    import __builtin__ as builtins
    from StringIO import StringIO as BytesIO
    BytesIO
    from StringIO import StringIO as TextIO
    TextIO

    cmp = builtins.cmp
    text_type = builtins.unicode
    string_types = (str, builtins.unicode)
    file_type = builtins.file
    execfile = builtins.execfile

    def iteritems(d):
        return d.iteritems()

    def iterkeys(d):
        return d.iterkeys()

    filterlist = filter
    maplist = map
elif PY3:
    import builtins
    from io import IOBase
    from io import BytesIO, StringIO as TextIO

    def cmp(a, b):
        return (a > b) - (a < b)

    text_type = str
    string_types = (str,)
    file_type = IOBase

    def execfile(filename, globals=None, locals=None):
        if globals is None:
            frame = sys._getframe(1)
            globals = frame.f_globals
            if locals is None:
                locals = frame.f_locals
            del frame
        elif locals is None:
            locals = globals

        with open(filename, "rb") as f:
            source = f.read()
        code = compile(source, filename, "exec")
        exec(code, globals, locals)

    def iteritems(d):
        return iter(d.items())

    def iterkeys(d):
        return iter(d.keys())

    def filterlist(*args, **kwargs):
        return list(filter(*args, **kwargs))

    def maplist(*args, **kwargs):
        return list(map(*args, **kwargs))