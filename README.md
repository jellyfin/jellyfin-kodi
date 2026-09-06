<h1 align="center">Jellyfin for Kodi</h1>
<h3 align="center">Part of the <a href="https://jellyfin.org">Jellyfin Project</a></h3>

---

<p align="center">
<img alt="Logo Banner" src="https://raw.githubusercontent.com/jellyfin/jellyfin-ux/master/branding/SVG/banner-logo-solid.svg?sanitize=true"/>
<br/>
<br/>
<a href="https://github.com/jellyfin/jellyfin-kodi"><img src="https://img.shields.io/github/license/jellyfin/jellyfin-kodi" alt="GPL 3.0 License" /></a>
<a href="https://github.com/jellyfin/jellyfin-kodi/releases"><img src="https://img.shields.io/github/v/release/jellyfin/jellyfin-kodi" alt="GitHub release (latest SemVer)" /></a>
<a href="https://matrix.to/#/+jellyfin:matrix.org"><img alt="Chat on Matrix" src="https://img.shields.io/matrix/jellyfin:matrix.org.svg?logo=matrix"/></a>
<br />
<a href="https://translate.jellyfin.org/engage/jellyfin/?utm_source=widget"><img src="https://translate.jellyfin.org/widgets/jellyfin/-/jellyfin-kodi/svg-badge.svg" alt="Translation status" /></a>
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=alert_status" alt="Quality Gate Status" /></a>
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=sqale_index" alt="Technical Debt" /></a>
<br />
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=code_smells" alt="Code Smells" /></a>
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=bugs" alt="Bugs" /></a>
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=vulnerabilities" alt="Vulnerabilities" /></a>
<br />
<img src="https://img.shields.io/github/languages/code-size/jellyfin/jellyfin-kodi" alt="GitHub code size in bytes" />
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=ncloc" alt="Lines of Code" /></a>
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=duplicated_lines_density" alt="Duplicated Lines (%)" /></a>
<br />
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=sqale_rating" alt="Maintainability Rating" /></a>
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=reliability_rating" alt="Reliability Rating" /></a>
<a href="https://sonarcloud.io/dashboard?id=jellyfin_jellyfin-kodi"><img src="https://sonarcloud.io/api/project_badges/measure?project=jellyfin_jellyfin-kodi&metric=security_rating" alt="Security Rating" /></a>
<br />
<a href="https://codecov.io/github/jellyfin/jellyfin-kodi"><img src="https://codecov.io/github/jellyfin/jellyfin-kodi/graph/badge.svg" alt="Code coverage" /></a>
<a href="https://github.com/jellyfin/jellyfin-kodi/actions/workflows/codeql.yaml"><img alt="CodeQL Analysis" src="https://github.com/jellyfin/jellyfin-kodi/actions/workflows/codeql.yaml/badge.svg" /></a>
</p>

Our informal Kodi support target is current release±1,
which currently translates to Nexus (old), Omega (current) and Piers (next).

Please note that next release is a moving target,
has a relatively low priority,
and is unlikely to receive active work before the release candidate stage.

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

### Contributing

#### AI/LLM

Please see [Jellyfin's official LLM policy](https://jellyfin.org/docs/general/contributing/llm-policies).

Any PR, issue or comment that is primarily LLM generated will be rejected outright on principe.

Machine translation as a communication aid is allowed,
but do include the original language text in addition.

LLM generated code has a high probability of getting rejected.
Relatively low effort AI contributions put an unsustainable
and unproportional extra burden on project maintainers,
which during the review process need to understand the suggested changes,
and evaluate whether they are good changes, whether there are better alternatives and so on.

LLM can be a decent tool to get up to speed and learn about the code-base,
but is highly likely to generate subpar code.

Fine for debugging, research and proof of concept,
but not currently suitable for production code.

#### Dev environment

The project use the following tools:

- [black](https://black.readthedocs.io/en/stable/) auto-formats the Python code (mandatory)
- [flake8](https://flake8.pycqa.org/en/latest/) to highlight potential issues
- [EditorConfig](https://editorconfig.org/) to ensure consistency in editor indentation and similar
- [pytest](https://docs.pytest.org/en/stable/) for code regression testing
- [pre-commit](https://pre-commit.com/) helps run the most important ones before commiting

[Visual Studio Code](https://code.visualstudio.com/) is my current editor of choice,
and as such the project is configured around this.
A [devcontainer](https://containers.dev/) config is available for consistency's sake
and quick setup, but I often don't use it myself.

[mypy](https://mypy.readthedocs.io/en/stable/index.html) is planned,
but there is a lot of work needed to properly implemet type-checking.
