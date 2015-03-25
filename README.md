### Welcome to Emby for Kodi
**A whole new way to manage and view your media library.**

The Emby addon for Kodi combines the best of Kodi - ultra smooth navigation, beautiful UIs and playback of any file under the sun, and Emby - the most powerful fully open source multi-client media metadata indexer and server.

**What does it do?**

With the old MediaBrowser addon for Kodi we have a couple of issues because you browse your media as a "video addon":
- 3th party addons such as NextAired, remote apps etc. won't work
- Speed: when browsing the data has to be retrieved from the server. Especially on slower devices this can take too much time.
- All kinds of workaround were needed to get the best experience on Kodi clients

The new Emby addon synchronizes your media on your MediaBrowser (Emby) server to the native Kodi database. Because we use the native Kodi database with this new approach the above limitations are gone! You can browse your media full speed and all other Kodi addons will be able to "see" your media.

**What is currently supported ?**

We're still in beta stage of development. Currently this features are working:
- Movies
- TV Shows
- MusicVideos
- Full sync at first run (import), background syncs configurable by the user in the addonsetting. The current default is that it will do a full sync on the background every couple of minutes.
- Deletions are supported: Items that are deleted on the MB3 server will be deleted on the Kodi database. Deletions done from the Kodi client TO the Emby server is only supported if you enable file deletions in the Kodi settings. An additional warning will be diaplayed if you really want to remove the item from the Emby server.
- Watched state/resume status sync: This is a 2-way synchronisation. Any watched state or resume status will be instantly (within seconds) reflected to or from Kodi and the server.


**To get started with the Emby addon for Kodi, first follow these guides to set up Emby and Kodi:**

1. To prevent any conflicts, remove the "old" MediaBrowser addon from your Kodi setup.
2. If you were using a modded skin for the MediaBrowser addon, make sure to set it in "normal Kodi mode" or just install the unmodded version of the skin.
3. Install the MediaBrowser/Emby BETA repository for Kodi, from the repo install the Emby addon.
4. Within a few seconds you should be prompted for your server-details (or auto discovered). If not, try to restart Kodi
5. Once you're succesfully authenticated to your MediaBrowser/Emby server, the initial sync will start. 
6. The first sync of the Emby server to local Kodi database may take some time.  On a powerful machine and fast network, expect around 15-45 minutes.  On a slow machine (such as a Raspberry Pi) the first sync may take up to two hours.
7. Once the full sync is done, you can browse your media in Kodi, syncs will be automatically done in the background.


**Known Issues:**
- Windows users: Kodi Helix 14.2 RC1 required - other versions will result in errors with recently added items etc.

**Important note about MySQL database in kodi**

The addon is not (and will not be) compatible with the MySQL database replacement in Kodi. In fact, Emby takes over the point of having a MySQL database because it acts as a "man in the middle" for your entire media library. Offcourse you can still use MySQL for your music while music is not supported by the addon currently.

**Important note about user collections/nodes**

Emby has the ability to create custom nodes/folders for your Media, such as having a seperate folder for your "Kids Movies" etc. In Kodi this isn't supported, you just have "movies" or "tvshows". But... Kodi let's you create your own playlists and tags to get this same experience. During the sync the foldernode from the MB3 server is added to the movies that are imported. In Kodi you can browse to Movie library --> tags and you will have a filtered result that points at your custom node. If you have a skin that let's you create any kind of shortcut on the homescreen you can simply create a shortcut to that tag. Another possibility is to create a "smart playlist" with Kodi and set it to show the content of a certain tag. 

At this point, please hold on to your feature requests and report bugs only.

Report bugs or any usefull feedback on the forums 
