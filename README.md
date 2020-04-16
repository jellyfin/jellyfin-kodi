# Jellyfin for Kodi

[![GPL 3.0 License](https://img.shields.io/github/license/jellyfin/jellyfin-kodi)](https://github.com/jellyfin/jellyfin-kodi)
![GitHub top language](https://img.shields.io/github/languages/top/jellyfin/jellyfin-kodi)
![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/jellyfin/jellyfin-kodi)
![GitHub issues](https://img.shields.io/github/issues/jellyfin/jellyfin-kodi)
![GitHub pull requests](https://img.shields.io/github/issues-pr/jellyfin/jellyfin-kodi)
![GitHub stars](https://img.shields.io/github/stars/jellyfin/jellyfin-kodi?style=social)
![GitHub forks](https://img.shields.io/github/forks/jellyfin/jellyfin-kodi?style=social)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/jellyfin/jellyfin-kodi)
![GitHub Release Date](https://img.shields.io/github/release-date/jellyfin/jellyfin-kodi)
![GitHub commits since latest release (by SemVer)](https://img.shields.io/github/commits-since/jellyfin/jellyfin-kodi/latest/master?sort=semver)
![GitHub last commit](https://img.shields.io/github/last-commit/jellyfin/jellyfin-kodi)
![GitHub contributors](https://img.shields.io/github/contributors/jellyfin/jellyfin-kodi)

[![Translation status](https://translate.jellyfin.org/widgets/jellyfin/-/jellyfin-kodi/svg-badge.svg)](https://translate.jellyfin.org/engage/jellyfin/?utm_source=widget)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=alert_status)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=bugs)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=code_smells)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
[![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=ncloc)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=duplicated_lines_density)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=sqale_rating)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=reliability_rating)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=security_rating)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
[![Technical Debt](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=sqale_index)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=vulnerabilities)](https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi)
___

**A whole new way to manage and view your media library.**

The Jellyfin for Kodi add-on combines the best of Kodi - ultra smooth navigation, beautiful UIs and playback of any file under the sun, and Jellyfin - the most powerful open source multi-client media metadata indexer and server. You can now retire your MySQL setup in favor of a more flexible setup.

Synchronize your media on your Jellyfin server to the native Kodi database, browsing your media at full speed, while retaining the ability to use other Kodi add-ons to enhance your experience. In addition, you can use any Kodi skin you'd like!
___

### Supported

The add-on supports a hybrid approach. You can decide which Jellyfin libraries to sync to the Kodi database. Other libraries and features are accessible dynamically, as a plugin listing.
- Library types available to sync:
  + Movies and sets
  + TV shows
  + Music videos
  + Music
- Other features supported:
  + Simple Live TV presentation
  + Home Videos & photos
  + Playlists
  + Theme media
- Direct play and transcode
- A 2-way watched and resume state between your server and Kodi. This is a near instant feature.
- Remote control your Kodi; send play commands from your Jellyfin web client or Jellyfin mobile apps.
- Extrafanart (rotating backgrounds) for skins that support it
- Offer to delete content after playback
- Backup your Jellyfin Kodi profile ([Create and restore from backup
](https://web.archive.org/web/20190202213116/https://github.com/MediaBrowser/plugin.video.emby/wiki/create-and-restore-from-backup))
- and more...

### Install Jellyfin for Kodi

Detailed installation instructions can be found in the [Jellyfin Client Documentation](https://docs.jellyfin.org/general/clients/kodi.html).

<!-- Get started with the [wiki guide](https://github.com/MediaBrowser/plugin.video.emby/wiki) -->

### Known limitations
- Chapter images are missing unless native playback mode is used.
- Certain add-ons that depend on seeing where your content is located will not work unless native playback mode is selected.
