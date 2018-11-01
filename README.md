# Emby for Kodi

[![EmbyKodi_Banner](https://i.imgur.com/hx4cx41.png)](https://emby.media/community/index.php?/forum/99-kodi/)

[![Wiki](https://img.shields.io/badge/get%20started-wiki-brightgreen.svg)](https://github.com/MediaBrowser/plugin.video.emby/wiki) 
[![Forums](https://img.shields.io/badge/report%20issues-forums-3960C1.svg)](https://emby.media/community/index.php?/forum/99-kodi/)
[![Donate](https://img.shields.io/badge/donate-kofi-blue.svg)](https://ko-fi.com/A5354BI)
[![Emby](https://img.shields.io/badge/server-emby-lightgray.svg)](https://emby.media/)
___
**A whole new way to manage and view your media library.**

The Emby for Kodi add-on combines the best of Kodi - ultra smooth navigation, beautiful UIs and playback of any file under the sun, and Emby - the most powerful open source multi-client media metadata indexer and server. You can now retire your MySQL setup in favor of a more flexible setup.

Synchronize your media on your Emby server to the native Kodi database, browsing your media at full speed, while retaining the ability to use other Kodi add-ons to enhance your experience. In addition, you can use any Kodi skin you'd like!
___

### Supported

The add-on supports a hybrid approach. You can decide which Emby libraries to sync to the Kodi database. Other libraries and features are accessible dynamically, as a plugin listing.
- Library types available to sync:
  + Movies and sets
  + TV shows
  + Music videos
  + Music
- Other features supported:
  + Simple Live TV presentation
  + Home Videos & photos
  + Audiobooks
  + Playlists
  + Theme media
- Direct play and transcode
- A 2-way watched and resume state between your server and Kodi. This is a near instant feature.
- Remote control your Kodi; send play commands from your Emby web client or Emby mobile apps.
- Extrafanart (rotating backgrounds) for skins that support it
- Offer to delete content after playback
- Backup your emby kodi profile. See the [Emby backup option](https://github.com/MediaBrowser/plugin.video.emby/wiki/Create-and-restore-from-backup)
- and more...

### Download and installation
**Important notes**
- To achieve direct play, you will need to ensure your Emby library paths point to network paths (e.g: "\\\\server\Media\Movies"). See the [Emby wiki](https://github.com/MediaBrowser/Wiki/wiki/Path%20Substitution) for additional information.
- **The addon is not (and will not be) compatible with the MySQL database replacement in Kodi.** In fact, Emby takes over the point of having a MySQL database because it acts as a "man in the middle" for your entire media library.
- Emby for Kodi is not currently compatible with Kodi's Video Extras addon unless native playback mode is used. **Deactivate Video Extras if content start randomly playing.**

View this short [Youtube video](https://youtu.be/IaecDPcXI3I?t=119) to give you a better idea of the general process.

1. Install the Emby for Kodi repository, from the repo install the Emby addon.
2. Within a few seconds you should be prompted for your server-details.
3. Once you're succesfully authenticated with your Emby server, the initial sync will start. 
4. The first sync of the Emby server to the local Kodi database may take some time depending on your device and library size.
5. Once the full sync is done, you can browse your media in Kodi, and syncs will be done automatically in the background.

### Known limitations
- Chapter images are missing unless native playback mode is used.
- Certain add-ons that depend on seeing where your content is located will not work unless native playback mode is selected.

___
### Help translate
Check [Transifex](https://www.transifex.com/emby-for-kodi/emby-for-kodi/stringspo/) to help translate this project. Thank you!
