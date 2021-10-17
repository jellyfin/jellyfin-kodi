#!/usr/bin/env python

import argparse
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

import yaml


def indent(elem: ET.Element, level: int = 0) -> None:
    """
    Nicely formats output xml with newlines and spaces
    https://stackoverflow.com/a/33956544
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def create_addon_xml(config: dict, source: str, py_version: str) -> None:
    """
    Create addon.xml from template file
    """
    # Load template file
    with open('{}/.build/template.xml'.format(source), 'r') as f:
        tree = ET.parse(f)
        root = tree.getroot()

    # Populate dependencies in template
    dependencies = config['dependencies'].get(py_version)
    for dep in dependencies:
        ET.SubElement(root.find('requires'), 'import', attrib=dep)

    # Populate version string
    addon_version = config.get('version')
    root.attrib['version'] = '{}+{}'.format(addon_version, py_version)

    # Populate Changelog
    date = datetime.today().strftime('%Y-%m-%d')
    changelog = config.get('changelog')
    for section in root.findall('extension'):
        news = section.findall('news')
        if news:
            news[0].text = 'v{} ({}):\n{}'.format(addon_version, date, changelog)

    # Format xml tree
    indent(root)

    # Write addon.xml
    tree.write('{}/addon.xml'.format(source), encoding='utf-8', xml_declaration=True)


def zip_files(py_version: str, source: str, target: str, dev: bool) -> None:
    """
    Create installable addon zip archive
    """
    archive_name = 'plugin.video.jellyfin+{}.zip'.format(py_version)

    with zipfile.ZipFile('{}/{}'.format(target, archive_name), 'w') as z:
        for root, dirs, files in os.walk(args.source):
            for filename in filter(file_filter, files):
                file_path = os.path.join(root, filename)
                if dev or folder_filter(file_path):
                    relative_path = os.path.join('plugin.video.jellyfin', os.path.relpath(file_path, source))
                    z.write(file_path, relative_path)


def file_filter(file_name: str) -> bool:
    """
    True if file_name is meant to be included
    """
    return (
        not (file_name.startswith('plugin.video.jellyfin') and file_name.endswith('.zip'))
        and not file_name.endswith('.pyo')
        and not file_name.endswith('.pyc')
        and not file_name.endswith('.pyd')
    )


def folder_filter(folder_name: str) -> bool:
    """
    True if folder_name is meant to be included
    """
    filters = [
        '.ci',
        '.git',
        '.github',
        '.build',
        '.mypy_cache',
        '.pytest_cache',
        '__pycache__',
    ]
    for f in filters:
        if f in folder_name.split(os.path.sep):
            return False

    return True



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build flags:')
    parser.add_argument(
        '--version',
        type=str,
        choices=('py2', 'py3'),
        default='py3')

    parser.add_argument(
        '--source',
        type=Path,
        default=Path(__file__).absolute().parent)

    parser.add_argument(
        '--target',
        type=Path,
        default=Path(__file__).absolute().parent)

    parser.add_argument('--dev', dest='dev', action='store_true')
    parser.set_defaults(dev=False)

    args = parser.parse_args()

    # Load config file
    config_path = os.path.join(args.source, 'release.yaml')
    with open(config_path, 'r') as fh:
        release_config = yaml.safe_load(fh)

    create_addon_xml(release_config, args.source, args.version)

    zip_files(args.version, args.source, args.target, args.dev)
