from six import string_types
from six.moves import collections_abc


def clean_none_dict_values(obj):
    """
    Recursively remove keys with a value of None
    """
    if not isinstance(obj, collections_abc.Iterable) or isinstance(obj, string_types):
        return obj

    queue = [obj]

    while queue:
        item = queue.pop()

        if isinstance(item, collections_abc.Mapping):
            mutable = isinstance(item, collections_abc.MutableMapping)
            remove = []

            for key, value in item.items():
                if value is None and mutable:
                    remove.append(key)

                elif isinstance(value, string_types):
                    continue

                elif isinstance(value, collections_abc.Iterable):
                    queue.append(value)

            if mutable:
                # Remove keys with None value
                for key in remove:
                    item.pop(key)

        elif isinstance(item, collections_abc.Iterable):
            for value in item:
                if value is None or isinstance(value, string_types):
                    continue
                elif isinstance(value, collections_abc.Iterable):
                    queue.append(value)

    return obj
