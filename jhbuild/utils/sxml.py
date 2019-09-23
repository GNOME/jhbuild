# jhbuild - a tool to ease building collections of source packages
# Copyright (C) 2008  Andy Wingo <wingo@pobox.com>
#
#   sxml.py: xml as s-expressions
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

"""
An s-expression syntax for XML documents.

Use like this:

>>> x = [sxml.h1, "text"]
>>> sxml_to_string (x)
"<h1>text</h1>"

>>> x = [sxml.a(href="about:blank", title="foo"), [sxml.i, "italics & stuff"]]
>>> sxml_to_string (x)
"<a href="about:blank" title="foo"><i>italics &amp; stuff</i></a>"
"""


__all__ = ['sxml', 'sxml_to_string']

def quote(s):
    quoted = {'"': '&quot;',
              '&': '&amp;',
              '<': '&lt;',
              '>': '&gt;'}
    return ''.join([quoted.get(c,c) for c in s])

def sxml_to_string(expr):
    if not isinstance(expr, list):
        return quote(expr)
    operator = expr[0]
    args = [sxml_to_string(arg) for arg in expr[1:]]
    return operator(args)

class sxml:
    def __getattr__(self, attr):
        def _trans(k):
            table = {'klass': 'class'}
            return table.get(k, k)

        def tag(*targs, **kw):
            def render(args):
                return ('<%s%s>%s</%s>'
                        % (attr,
                           ''.join([' %s="%s"' % (_trans(k), quote(v))
                                    for k, v in kw.items()]),
                           '\n'.join(args),
                           attr))
            render.__name__ = attr
            if targs:
                return render(targs[0])
            else:
                return render
        # this only works with python2.4
        tag.__name__ = attr 
        return tag
sxml = sxml()
