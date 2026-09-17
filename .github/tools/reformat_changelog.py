#!/usr/bin/env python

import argparse
import sys
import re
from typing import Dict, List, Pattern, Union, TypedDict

from emoji.core import emojize, demojize, replace_emoji

ITEM_FORMAT = "+ {title} (#{issue}) {usernames}"
OUTPUT_EMOJI = False

ITEM_PATTERN: Pattern = re.compile(
    r"^\s*(?P<old_listchar>[-*+])\s*(?P<title>.*?)\s*\(#(?P<issue>[0-9]+)\)\s*(?P<usernames>(\[?@[^\s,]+(\]\([^)]+\))?[, ]*)*)$"
)
USERNAME_PATTERN: Pattern = re.compile(
    r"(?:(?:\[@(?P<linked_username>[^\s]+)(?:\]\((?P<link>[^)]+)\)))|(?:@(?P<username>[^\s]+)))(?:,|$)"
)


class SectionType(TypedDict):
    title: str
    items: List[Dict[str, str]]


def reformat(item_format: str, output_emoji: bool) -> None:
    data = [
        emojize(x.strip(), variant="emoji_type", language="alias")
        for x in sys.stdin.readlines()
        if x.strip()
    ]

    sections = []

    section: Union[SectionType, Dict] = {}
    for line in data:
        if line.startswith("## "):
            pass
        if line.startswith("### "):
            if section:
                sections.append(section)
            _section: SectionType = {
                "title": line.strip("# "),
                "items": [],
            }
            section = _section

        m = ITEM_PATTERN.match(line)
        if m:
            gd = m.groupdict()
            section["items"].append(gd)

    sections.append(section)

    first = True

    for section in sections:
        if not section:
            continue
        if first:
            first = False
        else:
            print()

        title = section["title"]
        if not output_emoji:
            title = replace_emoji(title).strip()

        print(title)
        print("-" * len(title))

        for item in section["items"]:
            usernames = []
            for match in USERNAME_PATTERN.finditer(item["usernames"]):
                gd = match.groupdict()

                if gd["linked_username"]:
                    if output_emoji:
                        usernames.append("[@{linked_username}]({link})".format(**gd))
                    else:
                        usernames.append("@{linked_username}".format(**gd))

                elif gd["username"]:
                    usernames.append("@{username}".format(**gd))

            item["usernames"] = ", ".join(usernames)
            formatted_item = item_format.format(**item)
            if not output_emoji:
                formatted_item = demojize(formatted_item)
            print(formatted_item)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", type=str, default=ITEM_FORMAT)

    parser.add_argument("--no-emoji", dest="emoji", action="store_false")
    parser.add_argument("--emoji", dest="emoji", action="store_true")
    parser.set_defaults(emoji=OUTPUT_EMOJI)

    args = parser.parse_args()

    reformat(args.format, args.emoji)
