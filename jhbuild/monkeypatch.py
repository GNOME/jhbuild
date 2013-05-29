# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2001-2006  James Henstridge
#
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

# extras not found in old versions of Python

import sys
import __builtin__


# Windows lacks all sorts of subprocess features that we need to kludge around
if sys.platform.startswith('win'):
    from jhbuild.utils import subprocess_win32
    sys.modules['subprocess'] = subprocess_win32

# Python < 2.4 lacks reversed() builtin
if not hasattr(__builtin__, 'reversed'):
    def reversed(l):
        l = list(l)
        l.reverse()
        return iter(l)
    __builtin__.reversed = reversed

# Python < 2.4 lacks string.Template class
import string
if not hasattr(string, 'Template'):
    import re as _re

    class _multimap:
        """Helper class for combining multiple mappings.

        Used by .{safe_,}substitute() to combine the mapping and keyword
        arguments.
        """
        def __init__(self, primary, secondary):
            self._primary = primary
            self._secondary = secondary

        def __getitem__(self, key):
            try:
                return self._primary[key]
            except KeyError:
                return self._secondary[key]


    class _TemplateMetaclass(type):
        pattern = r"""
        %(delim)s(?:
          (?P<escaped>%(delim)s) |   # Escape sequence of two delimiters
          (?P<named>%(id)s)      |   # delimiter and a Python identifier
          {(?P<braced>%(id)s)}   |   # delimiter and a braced identifier
          (?P<invalid>)              # Other ill-formed delimiter exprs
        )
        """

        def __init__(cls, name, bases, dct):
            super(_TemplateMetaclass, cls).__init__(name, bases, dct)
            if 'pattern' in dct:
                pattern = cls.pattern
            else:
                pattern = _TemplateMetaclass.pattern % {
                    'delim' : _re.escape(cls.delimiter),
                    'id'    : cls.idpattern,
                    }
            cls.pattern = _re.compile(pattern, _re.IGNORECASE | _re.VERBOSE)


    class Template:
        """A string class for supporting $-substitutions."""
        __metaclass__ = _TemplateMetaclass
        __module__ = 'string'

        delimiter = '$'
        idpattern = r'[_a-z][_a-z0-9]*'

        def __init__(self, template):
            self.template = template

        # Search for $$, $identifier, ${identifier}, and any bare $'s

        def _invalid(self, mo):
            i = mo.start('invalid')
            lines = self.template[:i].splitlines(True)
            if not lines:
                colno = 1
                lineno = 1
            else:
                colno = i - len(''.join(lines[:-1]))
                lineno = len(lines)
            raise ValueError(_('Invalid placeholder in string: line %d, col %d') %
                             (lineno, colno))

        def substitute(self, *args, **kws):
            if len(args) > 1:
                raise TypeError(_('Too many positional arguments'))
            if not args:
                mapping = kws
            elif kws:
                mapping = _multimap(kws, args[0])
            else:
                mapping = args[0]
            # Helper function for .sub()
            def convert(mo):
                # Check the most common path first.
                named = mo.group('named') or mo.group('braced')
                if named is not None:
                    val = mapping[named]
                    # We use this idiom instead of str() because the latter will
                    # fail if val is a Unicode containing non-ASCII characters.
                    return '%s' % val
                if mo.group('escaped') is not None:
                    return self.delimiter
                if mo.group('invalid') is not None:
                    self._invalid(mo)
                raise ValueError(_('Unrecognized named group in pattern'),
                                 self.pattern)
            return self.pattern.sub(convert, self.template)

        def safe_substitute(self, *args, **kws):
            if len(args) > 1:
                raise TypeError(_('Too many positional arguments'))
            if not args:
                mapping = kws
            elif kws:
                mapping = _multimap(kws, args[0])
            else:
                mapping = args[0]
            # Helper function for .sub()
            def convert(mo):
                named = mo.group('named')
                if named is not None:
                    try:
                        # We use this idiom instead of str() because the latter
                        # will fail if val is a Unicode containing non-ASCII
                        return '%s' % mapping[named]
                    except KeyError:
                        return self.delimiter + named
                braced = mo.group('braced')
                if braced is not None:
                    try:
                        return '%s' % mapping[braced]
                    except KeyError:
                        return self.delimiter + '{' + braced + '}'
                if mo.group('escaped') is not None:
                    return self.delimiter
                if mo.group('invalid') is not None:
                    return self.delimiter
                raise ValueError(_('Unrecognized named group in pattern'),
                                 self.pattern)
            return self.pattern.sub(convert, self.template)

    string.Template = Template

# Python < 2.4 lacks subprocess module
try:
    import subprocess
except ImportError:
    from jhbuild.cut_n_paste import subprocess
    sys.modules['subprocess'] = subprocess
