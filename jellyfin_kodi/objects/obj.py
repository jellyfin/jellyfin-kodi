# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

import json
import os

from ..helper import LazyLogger

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class Objects(object):

    # Borg - multiple instances, shared state
    _shared_state = {}

    def __init__(self):
        """Hold all persistent data here."""

        self.__dict__ = self._shared_state

    def mapping(self):
        """Load objects mapping."""
        file_dir = os.path.dirname(__file__)

        with open(os.path.join(file_dir, "obj_map.json")) as infile:
            self.objects = json.load(infile)

    def map(self, item, mapping_name):
        """Syntax to traverse the item dictionary.
        This of the query almost as a url.

        Item is the Jellyfin item json object structure

        ",": each element will be used as a fallback until a value is found.
        "?": split filters and key name from the query part, i.e. MediaSources/0?$Name
        "$": lead the key name with $. Only one key value can be requested per element.
        ":": indicates it's a list of elements [], i.e. MediaSources/0/MediaStreams:?$Name
            MediaStreams is a list.
        "/": indicates where to go directly
        """
        self.mapped_item = {}

        if not mapping_name:
            raise Exception("execute mapping() first")

        mapping = self.objects[mapping_name]

        for key, value in mapping.items():

            self.mapped_item[key] = None
            params = value.split(",")

            for param in params:

                obj = item
                obj_param = param
                obj_key = ""
                obj_filters = {}

                if "?" in obj_param:

                    if "$" in obj_param:
                        obj_param, obj_key = obj_param.rsplit("$", 1)

                    obj_param, filters = obj_param.rsplit("?", 1)

                    if filters:
                        for filter in filters.split("&"):
                            filter_key, filter_value = filter.split("=")
                            obj_filters[filter_key] = filter_value

                if ":" in obj_param:
                    result = []

                    for d in self.__recursiveloop__(obj, obj_param):

                        if not obj_filters or self.__filters__(d, obj_filters):
                            result.append(d)

                    obj = result
                    obj_filters = {}

                elif "/" in obj_param:
                    obj = self.__recursive__(obj, obj_param)

                elif obj is item and obj is not None:
                    obj = item.get(obj_param)

                if obj_filters and obj and not self.__filters__(obj, obj_filters):
                    obj = None

                if obj is None and len(params) != params.index(param):
                    continue

                if obj_key:
                    obj = (
                        [d[obj_key] for d in obj if d.get(obj_key)]
                        if isinstance(obj, list)
                        else obj.get(obj_key)
                    )

                self.mapped_item[key] = obj
                break

        if (
            not mapping_name.startswith("Browse")
            and not mapping_name.startswith("Artwork")
            and not mapping_name.startswith("UpNext")
        ):

            self.mapped_item["ProviderName"] = self.objects.get(
                "%sProviderName" % mapping_name
            )
            self.mapped_item["Checksum"] = json.dumps(item["UserData"])

        return self.mapped_item

    def __recursiveloop__(self, obj, keys):

        first, rest = keys.split(":", 1)
        obj = self.__recursive__(obj, first)

        if obj:
            for item in obj:
                if rest:
                    self.__recursiveloop__(item, rest)
                else:
                    yield item

    def __recursive__(self, obj, keys):

        for string in keys.split("/"):

            if not obj:
                return

            obj = obj[int(string)] if string.isdigit() else obj.get(string)

        return obj

    def __filters__(self, obj, filters):

        result = False

        for key, value in filters.items():

            inverse = False

            if value.startswith("!"):

                inverse = True
                value = value.split("!", 1)[1]

            if value.lower() == "null":
                value = None

            result = obj.get(key) != value if inverse else obj.get(key) == value

        return result
