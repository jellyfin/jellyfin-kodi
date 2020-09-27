import xml.etree.ElementTree as ET
import sys
import os
from datetime import datetime

import yaml


def indent(elem, level=0):
    '''
    Nicely formats output xml with newlines and spaces
    https://stackoverflow.com/a/33956544
    '''
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


try:
    py_version = sys.argv[1]
except IndexError:
    print('No version specified')
    sys.exit(1)

dir_path = os.path.dirname(os.path.realpath(__file__))

# Load template file
with open('{dir_path}/template.xml'.format(**locals()), 'r') as f:
    tree = ET.parse(f)
    root = tree.getroot()

# Load version dependencies
with open('{dir_path}/{py_version}.yaml'.format(**locals()), 'r') as f:
    deps = yaml.safe_load(f)

# Load version and changelog
with open('jellyfin-kodi/release.yaml', 'r') as f:
    data = yaml.safe_load(f)

# Populate xml template
for dep in deps:
    ET.SubElement(root.find('requires'), 'import', attrib=dep)

# Update version string
addon_version = data.get('version')
root.attrib['version'] = '{addon_version}+{py_version}'.format(**locals())

# Changelog
date = datetime.today().strftime('%Y-%m-%d')
changelog = data.get('changelog')
for section in root.findall('extension'):
    news = section.findall('news')
    if news:
        news[0].text = 'v{addon_version} ({date}):\n{changelog}'.format(**locals())

# Format xml tree
indent(root)

# Write addon.xml
tree.write('jellyfin-kodi/addon.xml', encoding='utf-8', xml_declaration=True)
