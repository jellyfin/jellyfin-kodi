#!/usr/bin/env python3.8

import argparse
import sys
import re
from typing import Dict, List, Pattern, Union, TypedDict

from emoji.core import emojize, demojize, replace_emoji


ITEM_FORMAT = "+ {title} (#{issue}) @{username}"
OUTPUT_EMOJI = False

ITEM_PATTERN: Pattern = re.compile(
    r"^\s*(?P<old_listchar>[-*+])\s*(?P<title>.*?)\s*\(#(?P<issue>[0-9]+)\)\s*@(?P<username>[^\s]*)$"
)


class SectionType(TypedDict):
    title: str
    items: List[Dict[str, str]]


def reformat(item_format: str, output_emoji: bool) -> None:
    data = [
        emojize(x.strip(), variant="emoji_type")
        for x in sys.stdin.readlines()
        if x.strip()
    ]

    sections = []

    skip = False
    section: Union[SectionType, Dict] = {}
    for line in data:
        # If the line is not a list item or a header, skip it
        if not line[0] in ["#", "*", "-", "+"]:
            continue

        # Skip big header
        if line.startswith("## "):
            skip = True
            continue

        # Beginning of new section
        if line.startswith("### "):
            skip = False
            # Save the previous section
            if section:
                sections.append(section)

            # Start a new section
            section: SectionType = {
                "title": line.strip("# "),
                "items": [],
            }
            continue

        # If skip is enabled, skip the line
        if skip:
            continue

        # Line is a list item in the current section
        item_pattern_match = ITEM_PATTERN.match(line)
        if item_pattern_match:
            gd = item_pattern_match.groupdict()
            section["items"].append(gd)
            continue

    # Save the last section
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
