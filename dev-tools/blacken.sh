#!/bin/bash
# TODO: ensure clean workdir

git checkout -B pr-black upstream/master

git add $(black . 2>&1| grep -P '^reformatted' | cut -d' ' -f2)

git commit -m 'Tool: black'

git log HEAD~..HEAD --pretty=tformat:"# %s%n%H" >> .git-blame-ignore-revs
git add .git-blame-ignore-revs
git commit -m 'Git blame ignore black formatting'
