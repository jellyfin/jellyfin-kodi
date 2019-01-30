# -*- coding: utf-8 -*-
"""Test suite for cross-python compatibility helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest
import six

from cheroot._compat import ntob, ntou, bton


@pytest.mark.parametrize(
    'func,inp,out',
    [
        (ntob, 'bar', b'bar'),
        (ntou, 'bar', u'bar'),
        (bton, b'bar', 'bar'),
    ],
)
def test_compat_functions_positive(func, inp, out):
    """Check that compat functions work with correct input."""
    assert func(inp, encoding='utf-8') == out


@pytest.mark.parametrize(
    'func',
    [
        ntob,
        ntou,
    ],
)
def test_compat_functions_negative_nonnative(func):
    """Check that compat functions fail loudly for incorrect input."""
    non_native_test_str = b'bar' if six.PY3 else u'bar'
    with pytest.raises(TypeError):
        func(non_native_test_str, encoding='utf-8')


@pytest.mark.skip(reason='This test does not work now')
@pytest.mark.skipif(
    six.PY3,
    reason='This code path only appears in Python 2 version.',
)
def test_ntou_escape():
    """Check that ntou supports escape-encoding under Python 2."""
    expected = u''
    actual = ntou('hi'.encode('ISO-8859-1'), encoding='escape')
    assert actual == expected
