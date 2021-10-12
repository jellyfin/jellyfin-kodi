import pytest

from jellyfin_kodi.jellyfin.utils import clean_none_dict_values


@pytest.mark.parametrize("obj,expected", [
    (None, None),
    ([None, 1, 2, 3, None, 4], [None, 1, 2, 3, None, 4]),
    ({'foo': None, 'bar': 123}, {'bar': 123}),
    ({
        'dict': {
            'empty': None,
            'string': "Hello, Woorld!",
        },
        'number': 123,
        'list': [
            None,
            123,
            "foo",
            {
                'empty': None,
                'number': 123,
                'string': "foo",
                'list': [],
                'dict': {},
            }
        ]
    }, {
        'dict': {
            'string': "Hello, Woorld!",
        },
        'number': 123,
        'list': [
            None,
            123,
            "foo",
            {
                'number': 123,
                'string': "foo",
                'list': [],
                'dict': {},
            }
        ]
    }),
])
def test_clean_none_dict_values(obj, expected):
    assert clean_none_dict_values(obj) == expected
