from collections import namedtuple
from collections.abc import Iterable, Mapping, MutableMapping


def clean_none_dict_values(obj):
    """
    Recursively remove keys with a value of None
    """
    if not isinstance(obj, Iterable) or isinstance(obj, str):
        return obj

    queue = [obj]

    while queue:
        item = queue.pop()

        if isinstance(item, Mapping):
            mutable = isinstance(item, MutableMapping)
            remove = []

            for key, value in item.items():
                if value is None and mutable:
                    remove.append(key)

                elif isinstance(value, str):
                    continue

                elif isinstance(value, Iterable):
                    queue.append(value)

            if mutable:
                # Remove keys with None value
                for key in remove:
                    item.pop(key)

        elif isinstance(item, Iterable):
            for value in item:
                if value is None or isinstance(value, str):
                    continue
                elif isinstance(value, Iterable):
                    queue.append(value)

    return obj


def sqlite_namedtuple_factory(cursor, row):
    """
    Usage:
    con.row_factory = namedtuple_factory

    http://peter-hoffmann.com/2010/python-sqlite-namedtuple-factory.html
    """
    fields = [col[0] for col in cursor.description]
    Row = namedtuple("Row", fields)
    return Row(*row)
