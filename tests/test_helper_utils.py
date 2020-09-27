# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

import sys

import pytest

sys.path.insert(0, 'jellyfin_kodi')

from helper.utils import values  # noqa: E402

item1 = {'foo': 123, 'bar': 456, 'baz': 789}


@pytest.mark.parametrize("item,keys,expected", [
    (item1, ['{foo}', '{baz}'], [123, 789]),
    (item1, ['{foo}', 'bar'], [123, 'bar']),
    (item1, ['{foo}', 'bar', 321], [123, 'bar', 321]),
])
def test_values(item, keys, expected):
    assert list(values(item, keys)) == expected
