# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

import os
import zipfile
from fnmatch import fnmatchcase as fnmatch
import logging

import yaml
import click
import click_log


logger = logging.getLogger("build")
click_log.basic_config(logger)


def zip_items(file_name, items, base_path=None):
    if base_path is None:
        base_path = os.path.splitext(file_name)[0]

    elif not base_path:
        base_path = ""

    with zipfile.ZipFile(file_name, "w", zipfile.ZIP_DEFLATED) as z:
        for item, path, _pattern in items:
            logger.info(path)
            archive_path = os.path.join(base_path, path)
            if path not in ["."]:
                z.write(item, archive_path)

        return file_name


def get_config(filename='release.yaml'):
    with open(filename, 'r') as fh:
        return yaml.safe_load(fh)


def match_item(item, include, exclude):
    for pattern in exclude:
        if fnmatch(item, pattern):
            logger.debug('Excluded: {!r} {!r}'.format(pattern, item))
            return False, pattern

    for pattern in include:
        if fnmatch(item, pattern):
            logger.debug('Included: {!r} {!r}'.format(pattern, item))
            return True, pattern

    return None, None


def get_items(include, exclude, basepath='.'):
    for base, dirs, files in os.walk(basepath):
        for dir_name in dirs:
            dir_path = os.path.join(base, dir_name)
            normalized_dir_path = os.path.normpath(os.path.relpath(dir_path, basepath))
            match, pattern = match_item(normalized_dir_path, include, exclude)
            if match:
                yield dir_path, normalized_dir_path, pattern

        for file_name in files:
            file_path = os.path.join(base, file_name)
            normalized_file_path = os.path.normpath(os.path.relpath(file_path, basepath))
            match, pattern = match_item(normalized_file_path, include, exclude)
            if match:
                yield file_path, normalized_file_path, pattern


def build_filename(config, py3):
    # type: (dict, bool) -> str
    return "{}-{}+{}.zip".format(
        config.get('id'),
        config.get('version', '0.0.0'),
        'py3' if py3 else 'py2'
    )


@click.command()
@click.option('-3/-2', '--py3/--py2', default=True, type=bool, help="Default is Python 3.")
@click.option('--source', default='.', type=click.Path(exists=True, file_okay=False), help="Path to addon sources (current_dir).")
@click.option('--output', default=None, type=click.Path(), help="Output file (current_dir/addon-version+py3.zip).")
@click_log.simple_verbosity_option(logger)
def main(py3, source, output):
    config = get_config(os.path.join(source, 'release.yaml'))
    config_build = config.get('build', {})
    include = config_build.get('include', [])
    exclude = config_build.get('exclude', [])

    if output is None:
        output = build_filename(config, py3)

    items = get_items(include, exclude, source)

    zip_file_name = zip_items(output, items, base_path=config.get('id'))

    click.echo(zip_file_name)


if __name__ == "__main__":
    main()
