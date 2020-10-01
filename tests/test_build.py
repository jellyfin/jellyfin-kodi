
import pytest

from build import get_config, get_items

config = get_config()
build_config = config.get('build', {})
include = build_config.get('include', [])
exclude = build_config.get('exclude', [])

items = list(get_items(include, exclude))


def test_config():
    assert 'version' in config and type(config['version']) is str
    assert 'changelog' in config and type(config['changelog']) is str

    assert 'build' in config
    build = config['build']
    assert type(build) is dict

    assert 'include' in build and type(build['include']) is list
    assert 'exclude' in build and type(build['exclude']) is list


@pytest.mark.parametrize("pattern", include)
def test_include_pattern_matched(pattern):
    matched = False
    for _fp, _nfp, item_pattern in items:
        if pattern == item_pattern:
            matched = True

    assert matched, "Pattern `{}` matches no files.".format(pattern)
