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

from __future__ import print_function

import os
import sys
import importlib
import pkgutil
import locale
import codecs

from .compat import text_type, PY2, builtins, PY3

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

    if pkgutil.get_loader(module_name) is None:
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
    if isinstance(s, text_type):
        return s.encode(_encoding, 'replace')
    else:
        return s

def udecode(s):
    if not isinstance(s, text_type):
        return s.decode(_encoding, 'replace')
    else:
        return s

def bprint(data):
    '''Write some binary data as is to stdout'''

    assert isinstance(data, bytes)
    if PY2:
        sys.stdout.write(data)
    else:
        sys.stdout.flush()
        sys.stdout.buffer.write(data)

def uprint(*args, **kwargs):
    '''Print Unicode string encoded for the terminal'''

    if PY2:
        flush = kwargs.pop("flush", False)
        file = kwargs.get("file", sys.stdout)
        print(*[uencode(s) for s in args], **kwargs)
        if flush:
            file.flush()
    else:
        print(*args, **kwargs)


def uinput(prompt=None):
    if PY2:
        if prompt is not None:
            prompt = uencode(prompt)
        return udecode(builtins.raw_input(prompt))
    else:
        return builtins.input(prompt)


def N_(x):
    return text_type(x)

_ugettext = None

def _(x):
    x = text_type(x)
    if _ugettext is not None:
        return _ugettext(x)
    return x


def install_translation(translation):
    global _ugettext

    if PY2:
        _ugettext = translation.ugettext
    else:
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

    if PY3:
        return open(filename, mode, encoding=encoding, errors=errors)
    else:
        # We can't use io.open() here as its write method is too strict and
        # only allows unicode instances and not everything in the codebase
        # forces unicode at the moment. codecs.open() on the other hand
        # happily takes ASCII str and decodes it.
        return codecs.open(filename, mode, encoding=encoding, errors=errors)