# Welcome to Emby for Kodi
**A whole new way to manage and view your media library.**

The Emby addon for Kodi combines the best of Kodi - ultra smooth navigation, beautiful UIs and playback of any file under the sun, and Emby - the most powerful fully open source multi-client media metadata indexer and server.

### Download and installation

View this short [Youtube video](https://youtu.be/IaecDPcXI3I?t=119) to give you a better idea of the general process.

1. Install the Emby for Kodi repository, from the repo install the Emby addon.
2. Within a few seconds you should be prompted for your server-details.
3. Once you're succesfully authenticated with your Emby server, the initial sync will start. 
4. The first sync of the Emby server to the local Kodi database may take some time depending on your device and library size.
5. Once the full sync is done, you can browse your media in Kodi, and syncs will be done automatically in the background.

### Our Wiki

If you need additional information for Emby for Kodi, check out our [wiki](https://github.com/MediaBrowser/plugin.video.emby/wiki).

### What does Emby for Kodi do?

The Emby addon synchronizes your media on your Emby server to the native Kodi database. Because we use the native Kodi database, you can browse your media full speed and all other Kodi addons will be able to "see" your media. You can also use any Kodi skin you'd like!

### IMPORTANT NOTES

- If you require help, post to our [Emby-Kodi forums](http://emby.media/community/index.php?/forum/99-kodi/) for faster replies.
- To achieve direct play, you will need to ensure your Emby library paths point to network paths (e.g: "\\\\server\Media\Movies"). See the [Emby wiki](https://github.com/MediaBrowser/Wiki/wiki/Path%20Substitution) for additional information.
- **The addon is not (and will not be) compatible with the MySQL database replacement in Kodi.** In fact, Emby takes over the point of having a MySQL database because it acts as a "man in the middle" for your entire media library.
- Emby for Kodi is not currently compatible with Kodi's Video Extras addon unless native playback mode is used. **Deactivate Video Extras if content start randomly playing.**

### What is currently supported?

Emby for Kodi is under constant development. The following features are currently provided:

- Library types available:
  + Movies
  + Sets
  + TV Shows
  + Music Videos
  + Music
  + Home Videos
  + Pictures
- Emby for Kodi context menu:
  + Mark content as favorite
  + Refresh content
  + Delete content
- Direct play and transcode
- Watched state/resume status sync: This is a 2-way synchronisation. Any watched state or resume status will be instantly (within seconds) reflected to or from Kodi and the server.
- Remote control your Kodi; send play commands from your Emby webclient or Emby mobile apps.
- Copy Theme Music locally for use with the TV Tunes addon
- Copy ExtraFanart (rotating backgrounds) across for use with skins that support it
- Offer to delete content after playback
- **New!** Backup your emby kodi profile. See the [Emby backup option](https://github.com/MediaBrowser/plugin.video.emby/wiki/Create-and-restore-from-backup)
- and more...

### What is being worked on
Have a look at our [Trello board](https://trello.com/b/qBJ49ka4/emby-for-kodi) to follow our progress. 

### Known Issues
Solutions to the following issues are unlikely due to Kodi limitations.
- Chapter images are missing unless native playback mode is used.
- Certain add-ons that depend on seeing where your content is located will not work unless native playback mode is selected.
- ~~External subtitles (in separate files, e.g. mymovie.srt) can be used, but it is impossible to label them correctly unless direct playing~~
- Kodi only accepts direct paths for music content unlike the video library. Your Emby music library path will need to be formatted appropriately to work in Kodi (e.g: "\\\\server\Music\Album\song.ext"). See the [Emby wiki](https://github.com/MediaBrowser/Wiki/wiki/Path%20Substitution) for additional information.
