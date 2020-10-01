# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

import os
import zipfile
from fnmatch import fnmatchcase as fnmatch

import yaml


def zip_items(file_name, items, base_path=None):
    if base_path is None:
        base_path = os.path.splitext(file_name)[0]

    elif not base_path:
        base_path = ""

    with zipfile.ZipFile(file_name, "w", zipfile.ZIP_DEFLATED) as z:
        for item, path, _pattern in items:
            print(path)
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
            print('-', item, pattern)
            return False, pattern

    for pattern in include:
        if fnmatch(item, pattern):
            print('+', item, pattern)
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


def main():
    relpath = os.path.dirname(__file__) or '.'

    config = get_config(os.path.join(relpath, 'release.yaml'))
    build_config = config.get('build', {})
    include = build_config.get('include', [])
    exclude = build_config.get('exclude', [])

    print("Relpath:", relpath)
    print("Include:", include)
    print("Exclude:", exclude)
    print("Config:", config)

    items = get_items(include, exclude, relpath)

    zip_file_name = zip_items('test.zip', items, base_path='plugin.video.jellyfin')
    print(zip_file_name)


if __name__ == "__main__":
    main()
