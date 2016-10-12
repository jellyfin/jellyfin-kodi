# -*- coding: utf-8 -*-

##################################################################################################

import logging
import urllib

import api
import embydb_functions as embydb
import _kodi_musicvideos
from _common import Items
from utils import window, language as lang, catch_except

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class MusicVideos(Items):


    def __init__(self, embycursor, kodicursor, pdialog=None):

        self.embycursor = embycursor
        self.emby_db = embydb.Embydb_Functions(self.embycursor)
        self.kodicursor = kodicursor
        self.kodi_db = _kodi_musicvideos.KodiMusicVideos(self.kodicursor)
        self.pdialog = pdialog

        Items.__init__(self)

    def _get_func(self, item_type, action):

        if item_type == "MusicVideo":
            actions = {
                'added': self.added,
                'update': self.add_update,
                'userdata': self.updateUserdata,
                'remove': self.remove
            }
        else:
            log.info("Unsupported item_type: %s", item_type)
            actions = {}

        return actions.get(action)

    def compare_all(self):
        pdialog = self.pdialog
        # Pull the list of musicvideos in Kodi
        views = self.emby_db.getView_byType('musicvideos')
        log.info("Media folders: %s", views)

        try:
            all_kodimvideos = dict(self.emby_db.get_checksum('MusicVideo'))
        except ValueError:
            all_kodimvideos = {}

        all_embymvideosIds = set()
        updatelist = []

        for view in views:

            if self.should_stop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading=lang(29999),
                        message="%s %s..." % (lang(33028), viewName))

            all_embymvideos = self.emby.getMusicVideos(viewId, basic=True, dialog=pdialog)
            for embymvideo in all_embymvideos['Items']:

                if self.should_stop():
                    return False

                API = api.API(embymvideo)
                itemid = embymvideo['Id']
                all_embymvideosIds.add(itemid)


                if all_kodimvideos.get(itemid) != API.get_checksum():
                    # Only update if musicvideo is not in Kodi or checksum is different
                    updatelist.append(itemid)

            log.info("MusicVideos to update for %s: %s", viewName, updatelist)
            embymvideos = self.emby.getFullItems(updatelist)
            self.total = len(updatelist)
            del updatelist[:]


            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, self.total))

            self.count = 0
            for embymvideo in embymvideos:
                # Process individual musicvideo
                if self.should_stop():
                    return False
                self.title = embymvideo['Name']
                self.update_pdialog()
                self.add_update(embymvideo, view)
                self.count += 1

        ##### PROCESS DELETES #####

        for kodimvideo in all_kodimvideos:
            if kodimvideo not in all_embymvideosIds:
                self.remove(kodimvideo)

        log.info("MusicVideos compare finished.")
        return True


    def added(self, items, total=None, view=None):
        for item in super(MusicVideos, self).added(items, total):
            if self.add_update(item, view):
                self.content_pop(item.get('Name', "unknown"))

    @catch_except()
    def add_update(self, item, view=None):
        # Process single music video
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        artwork = self.artwork
        API = api.API(item)

        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            log.info("mvideoid: %s fileid: %s pathid: %s", mvideoid, fileid, pathid)

        except TypeError:
            update_item = False
            log.debug("mvideoid: %s not found", itemid)
            # mvideoid
            mvideoid = self.kodi_db.create_entry()

        else:
            if self.kodi_db.get_musicvideo(mvideoid) is None:
                # item is not found, let's recreate it.
                update_item = False
                log.info("mvideoid: %s missing from Kodi, repairing the entry.", mvideoid)

        if not view:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)
            log.debug("View tag found: %s", viewtag)
        else:
            viewtag = view['name']
            viewid = view['id']

        # fileId information
        checksum = API.get_checksum()
        dateadded = API.get_date_created()
        userdata = API.get_userdata()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        runtime = API.get_runtime()
        plot = API.get_overview()
        title = item['Name']
        year = item.get('ProductionYear')
        genres = item['Genres']
        genre = " / ".join(genres)
        studios = API.get_studios()
        studio = " / ".join(studios)
        artist = " / ".join(item.get('Artists'))
        album = item.get('Album')
        track = item.get('Track')
        people = API.get_people()
        director = " / ".join(people['Director'])


        ##### GET THE FILE AND PATH #####
        playurl = API.get_file_path()

        if "\\" in playurl:
            # Local path
            filename = playurl.rsplit("\\", 1)[1]
        else: # Network share
            filename = playurl.rsplit("/", 1)[1]

        if self.direct_path:
            # Direct paths is set the Kodi way
            if not self.path_validation(playurl):
                return False

            path = playurl.replace(filename, "")
            window('emby_pathverified', value="true")
        else:
            # Set plugin path and media flags using real filename
            path = "plugin://plugin.video.emby.musicvideos/"
            params = {

                'filename': filename.encode('utf-8'),
                'id': itemid,
                'dbid': mvideoid,
                'mode': "play"
            }
            filename = "%s?%s" % (path, urllib.urlencode(params))


        ##### UPDATE THE MUSIC VIDEO #####
        if update_item:
            log.info("UPDATE mvideo itemid: %s - Title: %s", itemid, title)

            # Update the music video entry
            self.kodi_db.update_musicvideo(title, runtime, director, studio, year, plot, album,
                                           artist, genre, track, mvideoid)

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        ##### OR ADD THE MUSIC VIDEO #####
        else:
            log.info("ADD mvideo itemid: %s - Title: %s", itemid, title)

            # Add path
            pathid = self.kodi_db.add_path(path)
            # Add the file
            fileid = self.kodi_db.add_file(filename, pathid)

            # Create the musicvideo entry
            self.kodi_db.add_musicvideo(mvideoid, fileid, title, runtime, director, studio,
                                        year, plot, album, artist, genre, track)

            # Create the reference in emby table
            emby_db.addReference(itemid, mvideoid, "MusicVideo", "musicvideo", fileid, pathid,
                                 checksum=checksum, mediafolderid=viewid)

        # Update the path
        self.kodi_db.update_path(pathid, path, "musicvideos", "metadata.local")
        # Update the file
        self.kodi_db.update_file(fileid, filename, pathid, dateadded)

        # Process cast
        people = item['People']
        artists = item['ArtistItems']
        for artist in artists:
            artist['Type'] = "Artist"
        people.extend(artists)
        people = artwork.get_people_artwork(people)
        self.kodi_db.add_people(mvideoid, people, "musicvideo")
        # Process genres
        self.kodi_db.add_genres(mvideoid, genres, "musicvideo")
        # Process artwork
        artwork.add_artwork(artwork.get_all_artwork(item), mvideoid, "musicvideo", kodicursor)
        # Process stream details
        streams = API.get_media_streams()
        self.kodi_db.add_streams(fileid, streams, runtime)
        # Process studios
        self.kodi_db.add_studios(mvideoid, studios, "musicvideo")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite musicvideos")
        self.kodi_db.add_tags(mvideoid, tags, "musicvideo")
        # Process playstates
        resume = API.adjust_resume(userdata['Resume'])
        total = round(float(runtime), 6)
        self.kodi_db.add_playstate(fileid, resume, total, playcount, dateplayed)

        return True

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        API = api.API(item)

        # Get emby information
        itemid = item['Id']
        checksum = API.get_checksum()
        userdata = API.get_userdata()
        runtime = API.get_runtime()

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            log.info("Update playstate for musicvideo: %s fileid: %s", item['Name'], fileid)
        except TypeError:
            return

        # Process favorite tags
        if userdata['Favorite']:
            self.kodi_db.get_tag(mvideoid, "Favorite musicvideos", "musicvideo")
        else:
            self.kodi_db.remove_tag(mvideoid, "Favorite musicvideos", "musicvideo")

        # Process playstates
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = API.adjust_resume(userdata['Resume'])
        total = round(float(runtime), 6)

        self.kodi_db.add_playstate(fileid, resume, total, playcount, dateplayed)
        emby_db.updateReference(itemid, checksum)

    def remove(self, itemid):
        # Remove mvideoid, fileid, pathid, emby reference
        emby_db = self.emby_db
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            log.info("Removing mvideoid: %s fileid: %s pathid: %s", mvideoid, fileid, pathid)
        except TypeError:
            return

        # Remove the emby reference
        emby_db.removeItem(itemid)
        # Remove artwork
        artwork.delete_artwork(mvideoid, "musicvideo", self.kodicursor)

        self.kodi_db.remove_musicvideo(mvideoid, fileid)
        if self.direct_path:
            self.kodi_db.remove_path(pathid)

        log.info("Deleted musicvideo %s from kodi database", itemid)
