for modname in ['base', 'mozilla', 'tarball']:
    exec 'import %s' % modname

from base import parse_xml_node
