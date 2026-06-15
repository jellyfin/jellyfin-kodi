<h1 align="center">Jellyfin for Kodi</h1>
<h3 align="center">Part of the <a href="https://jellyfin.org">Jellyfin Project</a></h3>

---

<p align="center">
<img alt="Logo Banner" src="https://raw.githubusercontent.com/jellyfin/jellyfin-ux/master/branding/SVG/banner-logo-solid.svg?sanitize=true"/>
</p>

<table>
  <thead>
    <tr>
      <td align="left">
        :warning: Python 2 deprecation (Kodi 18 Leia and older)
      </td>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        <p>
          Kodi installs based on Python 2 are no longer supported
          going forward.
          <br/>
          This means that Kodi v18 (Leia) and earlier
          (Krypton, Jarvis...) is no longer supported,
          and will cease receiving updates.
        </p>
        <p>
          Our informal support target is current release±1,
          which currently translates to Nexus (old), Omega (current) and Piers (next).
          <br />
          Please note that next release is a moving target,
          has a relatively low priority,
          and is unlikely to receive active work before the release candidate stage.
        </p>
        <p>
          The major version of Jellyfin for Kodi will be bumped for the first release without Python 2 support.
        </p>
      </td>
    </tr>
  </tbody>
</table>

---

**A whole new way to manage and view your media library.**

The Jellyfin for Kodi add-on combines the best of Kodi - ultra smooth navigation, beautiful UIs and playback of any file under the sun, and Jellyfin - the most powerful open source multi-client media metadata indexer and server. You can now retire your MySQL setup in favor of a more flexible setup.

Synchronize your media on your Jellyfin server to the native Kodi database, browsing your media at full speed, while retaining the ability to use other Kodi add-ons to enhance your experience. In addition, you can use any Kodi skin you'd like!

---

### Supported

The add-on supports a hybrid approach. You can decide which Jellyfin libraries to sync to the Kodi database. Other libraries and features are accessible dynamically, as a plugin listing.

- Library types available to sync:
  - Movies and sets
  - TV shows
  - Music videos
  - Music
- Other features supported:
  - Simple Live TV presentation
  - Home Videos & photos
  - Playlists
  - Theme media
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

### Difference compared to origin repo

- use upnext plugin to replace the credits skip button
- change upnext initialization to where credits started
