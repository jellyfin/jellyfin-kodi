#!/bin/bash
# Exit on error, print commands
set -o errexit
set -o xtrace

#
# Copyright (c) Odd Stråbø, 2024
# File-License: the Unlicense
#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <http://unlicense.org/>
#

# Ensure we are in the repository root
pushd "$(realpath $(dirname $0)/../..)"

# Make sure black is installed and up to date
pipx upgrade black

# Make sure we are on latest master
git checkout master
git fetch upstream master
git pull upstream master --ff-only

# Create new branch, deleting if existing
git checkout -B black

# Ensure workdir is clean
git stash --include-untracked
git reset --hard

# Run black and git add changed files
black . -t py38 -t py39 -t py310 -t py311 -t py312 -t py313 2>&1 | sed -nr 's/^reformatted\s(.*)$/\1/p' | tr '\n' '\0' | xargs -0 git add

# Commit changes
git commit -m 'Tool black: auto-format Python code'

# Hide previous commit from blame to avoid clutter
echo "# Tool: black" >>.git-blame-ignore-revs
git rev-parse HEAD >>.git-blame-ignore-revs
git add .git-blame-ignore-revs
git commit -m 'Tool black: ignore blame'

# Push branch to fork
git push --set-upstream origin black --force

# Go back to previous directory
popd
