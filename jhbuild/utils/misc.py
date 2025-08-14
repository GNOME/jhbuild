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

import builtins
import os
import sys
import importlib
import locale


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


def inpath(filename, path):
    for dir in path:
        if os.path.isfile(os.path.join(dir, filename)):
            return True
        # also check for filename.exe on Windows
        if sys.platform.startswith('win') and os.path.isfile(os.path.join(dir, filename + '.exe')):
            return True
    return False


def try_import_module(module_name):
    """Like importlib.import_module() but doesn't raise if the module doesn't exist"""

    if importlib.util.find_spec(module_name) is None:
        return
    return importlib.import_module(module_name)


def _get_encoding():
    try:
        encoding = locale.getpreferredencoding()
    except locale.Error:
        encoding = ""
    if not encoding:
        # work around locale.getpreferredencoding() returning an empty string in
        # Mac OS X, see http://bugzilla.gnome.org/show_bug.cgi?id=534650
        if sys.platform == "darwin":
            encoding = "utf-8"
        else:
            encoding = "ascii"
    return encoding

_encoding = _get_encoding()


def uencode(s):
    if isinstance(s, str):
        return s.encode(_encoding, 'replace')
    else:
        return s

def udecode(s):
    if not isinstance(s, str):
        return s.decode(_encoding, 'replace')
    else:
        return s

def bprint(data):
    '''Write some binary data as is to stdout'''

    assert isinstance(data, bytes)
    sys.stdout.flush()
    sys.stdout.buffer.write(data)

def uprint(*args, **kwargs):
    '''Print Unicode string encoded for the terminal'''

    print(*args, **kwargs)


def uinput(prompt=None):
    return builtins.input(prompt)


def N_(x):
    return str(x)

_ugettext = None

def _(x):
    x = str(x)
    if _ugettext is not None:
        return _ugettext(x)
    return x


def install_translation(translation):
    global _ugettext

    _ugettext = translation.gettext


def open_text(filename, mode="r", encoding="utf-8", errors="strict"):
    """An open() which removes some differences between Python 2 and 3 and
    has saner defaults.
    Unlike the builtin open by default utf-8 is used and not the locale
    encoding (which is ANSI on Windows for example, not very helpful)
    For Python 2, files are opened in text mode like with Python 3.
    """

    if mode not in ("r", "w"):
        raise ValueError("mode %r not supported, must be 'r' or 'w'" % mode)

    return open(filename, mode, encoding=encoding, errors=errors)
