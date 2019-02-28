# Jellyfin for Kodi
<!--
TODO
[![EmbyKodi_Banner](https://i.imgur.com/hx4cx41.png)](https://forum.jellyfin.org/)

[![Wiki](https://img.shields.io/badge/get%20started-wiki-brightgreen.svg)](https://github.com/MediaBrowser/plugin.video.emby/wiki) 
[![Forums](https://img.shields.io/badge/report%20issues-forums-3960C1.svg)](https://forum.jellyfin.org/)
[![Donate](https://img.shields.io/badge/donate-kofi-blue.svg)](https://ko-fi.com/A5354BI)
[![Emby](https://img.shields.io/badge/server-emby-52b54b.svg)](https://jellyfin.media/)
___
-->
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

1. Download the add-on as a [zip file](../../archive/master.zip)
   - It will be saved as `jellyfin-kodi-master.zip`
2. Install Jellyfin for Kodi
   - Navigate to "Add-on Browser"
   - Select "Install from zip file"
     + If prompted, enter settings and enable "Unknown Sources", then go back
   - Select the newly downloaded file and it will be installed
3. Within a few seconds you should be prompted for your server-details.
   - If a Jellyfin server is detected on your local network, it will displayed in the popup
   - If a Jellyfin server is not detected on your local network, select "Manually add server"
     + Enter the server name or IP address and the port number (default is 8096)
     + If using SSL and a reverse proxy, enter the full URL scheme in the "Host" field
       * Host: https://jellyfin.example.com
       * Port: 443
   - Select user account and input password
4. Once you're succesfully authenticated with your Jellyfin server, configure the libraries to sync to this device
   - Select "Proceed" to continue setup now
   - Select "All" when asked about libraries.  This will poll your server to see what is available later
   - Choose between Native and Add-on mode (Add-on is recommended)
   - Choose your artwork caching preferences
   - Choose your empty show preferences
   - Choose your ratings preferences
   - Select "Proceed" to continue setup now
   - Select the libraries you would like to keep synced with this device
5. The first sync of the Jellyfin server to the local Kodi database may take some time depending on your device and library size
6. Once the full sync is done, you can browse your media in Kodi, and syncs will be done automatically in the background

**Note: It's recommended to install the `Kodi Sync Queue` plugin into the Jellyfin server as well**

This will help keep your media libraries up to date without waiting for a periodic resync from Kodi.

<!-- Get started with the [wiki guide](https://github.com/MediaBrowser/plugin.video.emby/wiki) -->

### Known limitations
- Chapter images are missing unless native playback mode is used.
- Certain add-ons that depend on seeing where your content is located will not work unless native playback mode is selected.
