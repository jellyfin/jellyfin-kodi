# Releasing a new Version via GitHub Actions

0. (optional) label the PRs you want to include in this release (if you want to group them in the GH release based on topics). \
    Supported labels can be found in the Release Drafter [config-file](https://github.com/jellyfin/jellyfin-meta-plugins/blob/master/.github/release-drafter.yml) (currently inherited from `jellyfin/jellyfin-meta-plugins`)
1. ensure you have merged the PRs you want to include in the release and that the so far drafted GitHub release has captured them
2. Create a `release-prep` PR by manually triggering the 'Create Prepare-Release PR' Workflow from the Actions tab on GitHub
3. check the newly created `Prepare for release vx.y.z` PR if updated the `release.yaml` properly (update it manually if need be)
4. merge the `Prepare for release vx.y.z` and let the Actions triggered by doing that finis (should just be a couple of seconds)
5. FINALLY, trigger the `Publish Jellyfin-Kodi` manually from the Actions tab on GitHub.
    1. this will release the up to that point drafted GitHub Release and tag the default branch accordingly
    2. this will package and deploy `Jellyfin-Kodi` in the new version to the deployment server and trigger the 'kodirepo' script on it
6. Done, assuming everything ran successfully, you have now successfully published a new version! :tada:
