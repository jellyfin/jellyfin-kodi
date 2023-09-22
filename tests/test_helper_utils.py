# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

import os
import time

import pytest

from jellyfin_kodi.helper.utils import values, convert_to_local

item1 = {"foo": 123, "bar": 456, "baz": 789}


@pytest.mark.parametrize(
    "item,keys,expected",
    [
        (item1, ["{foo}", "{baz}"], [123, 789]),
        (item1, ["{foo}", "bar"], [123, "bar"]),
        (item1, ["{foo}", "bar", 321], [123, "bar", 321]),
    ],
)
def test_values(item, keys, expected):
    assert list(values(item, keys)) == expected


class timezone_context:
    tz = None

    def __init__(self, tz):
        self.tz = tz

    def __enter__(self):
        os.environ["TZ"] = self.tz
        time.tzset()

    def __exit__(self, *args, **kwargs):
        del os.environ["TZ"]
        time.tzset()


@pytest.mark.parametrize(
    "utctime,timezone,expected",
    [
        # Special case for malformed data from the server, see #212
        ("0001-01-01T00:00:00.0000000Z", "UTC", "0001-01-01T00:00:00"),
        ("Hello, error.", "Etc/UTC", "Hello, error."),
        ("2023-09-21T23:54:24", "Etc/UTC", "2023-09-21T23:54:24"),
        # See #725
        ("1957-09-21T00:00:00Z", "Europe/Paris", "1957-09-21T01:00:00"),
        ("1970-01-01T00:00:00", "Etc/UTC", "1970-01-01T00:00:00"),
        ("1969-01-01T00:00:00", "Etc/UTC", "1969-01-01T00:00:00"),
        ("1970-01-01T00:00:00", "Europe/Oslo", "1970-01-01T01:00:00"),
        ("1969-01-01T00:00:00", "Europe/Oslo", "1969-01-01T01:00:00"),
        ("2023-09-21T23:54:24", "Europe/Oslo", "2023-09-22T01:54:24"),
        # End of DST in Europe
        ("2023-10-29T00:00:00", "Europe/Oslo", "2023-10-29T02:00:00"),
        ("2023-10-29T00:59:59", "Europe/Oslo", "2023-10-29T02:59:59"),
        ("2023-10-29T01:00:00", "Europe/Oslo", "2023-10-29T02:00:00"),
        # Start of DST in Europe
        ("2023-03-26T00:59:59", "Europe/Oslo", "2023-03-26T01:59:59"),
        ("2023-03-26T01:00:00", "Europe/Oslo", "2023-03-26T03:00:00"),
        # Norway was in permanent summertime 1940-08-11 -> 1942-11-02
        ("1941-06-24T00:00:00", "Europe/Oslo", "1941-06-24T02:00:00"),
        ("1941-12-24T00:00:00", "Europe/Oslo", "1941-12-24T02:00:00"),
        # Not going to test them all, but you get the point...
        ("1917-07-20T00:00:00", "Europe/Oslo", "1917-07-20T01:00:00"),
        ("1916-07-20T00:00:00", "Europe/Oslo", "1916-07-20T02:00:00"),
        ("1915-07-20T00:00:00", "Europe/Oslo", "1915-07-20T01:00:00"),
        # Some fun outside Europe too!
        ("2023-03-11T03:30:00", "America/St_Johns", "2023-03-11T00:00:00"),
        ("2023-03-13T02:30:00", "America/St_Johns", "2023-03-13T00:00:00"),
        ("2023-11-04T02:30:00", "America/St_Johns", "2023-11-04T00:00:00"),
        ("2023-11-06T03:30:00", "America/St_Johns", "2023-11-06T00:00:00"),
        ("2023-12-24T00:00:00", "Australia/Eucla", "2023-12-24T08:45:00"),
        ("2023-06-24T00:00:00", "Australia/Eucla", "2023-06-24T08:45:00"),
        ("2023-12-24T00:00:00", "Australia/Broken_Hill", "2023-12-24T10:30:00"),
        ("2023-06-24T00:00:00", "Australia/Broken_Hill", "2023-06-24T09:30:00"),
        ("2023-10-31T00:00:00", "Pacific/Kiritimati", "2023-10-31T14:00:00"),
        ("2023-10-31T00:00:00", "Pacific/Midway", "2023-10-30T13:00:00"),
    ],
)
def test_convert_to_local(utctime, timezone, expected):
    with timezone_context(timezone):
        assert convert_to_local(utctime) == expected
