# -*- coding: utf-8 -*-

#################################################################################################

import logging
import shutil
import os
import xml.etree.ElementTree as etree

import xbmc
import xbmcaddon
import xbmcvfs

import read_embyserver as embyserver
import embydb_functions as embydb
from utils import window, language as lang

#################################################################################################

log = logging.getLogger("EMBY."+__name__)
KODI = int(xbmc.getInfoLabel('System.BuildVersion')[:2])

#################################################################################################


class Views(object):

    total_nodes = 0
    nodes = list()
    playlists = list()
    views = list()
    sorted_views = list()


    def __init__(self, emby_cursor, kodi_cursor):
        self.emby_cursor = emby_cursor
        self.kodi_cursor = kodi_cursor

        self.video_nodes = VideoNodes()
        self.emby = embyserver.Read_EmbyServer()
        self.emby_db = embydb.Embydb_Functions(embycursor)

    def _populate_views(self):
        # Will get emby views and views in Kodi
        self.views = self.emby.getViews(sortedlist=True)
        for view in self.views:
            if view['type'] == "music":
                continue

            if view['type'] == "mixed":
                self.sorted_views.append(view['name'])
            self.sorted_views.append(view['name'])

        log.info("sorted views: %s", self.sorted_views)
        self.total_nodes = len(self.sorted_views)

    def maintain(self):
        # Compare views to emby
        self._populate_views()
        view_list = [view['name'] for view in self.all_views]
        grouped_views = self.emby.get_views()
        current_views = emby_db.getViews()
        # total nodes for window properties
        self.vnodes.clearProperties()

        # Set views for supported media type
        emby_mediatypes = {

            'movies': "Movie",
            'tvshows': "Series",
            'musicvideos': "MusicVideo",
            'homevideos': "Video",
            'music': "Audio",
            'photos': "Photo"
        }
        for mediatype in ['movies', 'tvshows', 'musicvideos', 'homevideos', 'music', 'photos']:

            self.nodes = list() # Prevent duplicate for nodes of the same type
            self.playlists = list() # Prevent duplicate for playlists of the same type
            # Get media folders from server
            for folder in [view for view in ordered if view['type'] == mediatype]:

                folderid = folder['id']
                foldername = folder['name']
                viewtype = folder['type']

                if foldername not in view_list:
                    # Media folders are grouped into userview
                    params = {
                        'ParentId': folderid,
                        'Recursive': True,
                        'Limit': 1,
                        'IncludeItemTypes': emby_mediatypes[mediatype]
                    } # Get one item from server using the folderid
                    url = "{server}/emby/Users/{UserId}/Items?format=json"
                    result = self.doUtils(url, parameters=params)
                    try:
                        verifyitem = result['Items'][0]['Id']
                    except (TypeError, IndexError):
                        # Something is wrong. Keep the same folder name.
                        # Could be the view is empty or the connection
                        pass
                    else:
                        for grouped_view in grouped_views:
                            # This is only reserved for the detection of grouped views
                            if (grouped_view['Type'] == "UserView" and
                                grouped_view.get('CollectionType') == mediatype):
                                # Take the userview, and validate the item belong to the view
                                if self.emby.verifyView(grouped_view['Id'], verifyitem):
                                    # Take the name of the userview
                                    log.info("Found corresponding view: %s %s"
                                        % (grouped_view['Name'], grouped_view['Id']))
                                    foldername = grouped_view['Name']
                                    break
                        else:
                            # Unable to find a match, add the name to our sorted_view list
                            self.sorted_views.append(foldername)
                            log.info("Couldn't find corresponding grouped view: %s" % self.sorted_views)

                # Failsafe
                try:
                    self.sorted_views.index(foldername)
                except ValueError:
                    self.sorted_views.append(foldername)

                # Get current media folders from emby database
                view = emby_db.getView_byId(folderid)
                try:
                    current_viewname = view[0]
                    current_viewtype = view[1]
                    current_tagid = view[2]

                except TypeError:
                    self._add_view(mediatype, folderid, foldername, viewtype)

                else:
                    log.debug(' '.join((

                        "Found viewid: %s" % folderid,
                        "viewname: %s" % current_viewname,
                        "viewtype: %s" % current_viewtype,
                        "tagid: %s" % current_tagid)))

                    # View is still valid
                    try:
                        current_views.remove(folderid)
                    except ValueError:
                        # View was just created, nothing to remove
                        pass

                    # View was modified, update with latest info
                    if current_viewname != foldername:
                        log.info("viewid: %s new viewname: %s" % (folderid, foldername))
                        tagid = self._get_tag(foldername)

                        # Update view with new info
                        emby_db.updateView(foldername, tagid, folderid)

                        if mediatype != "music":
                            if emby_db.getView_byName(current_viewname) is None:
                                # The tag could be a combined view. Ensure there's no other tags
                                # with the same name before deleting playlist.
                                self._playlist(mediatype, current_viewname, folderid,
                                              current_viewtype, True)
                                # Delete video node
                                if mediatype != "musicvideos":
                                    self.vnodes.viewNode(
                                        indexnumber=None,
                                        tagname=current_viewname,
                                        mediatype=mediatype,
                                        viewtype=current_viewtype,
                                        viewid=folderid,
                                        delete=True)
                            # Added new playlist
                            self.create_playlist(mediatype, foldername, folderid, viewtype)
                            # Add new video node
                            self.create_node(mediatype, foldername, folderid, viewtype)

                        # Update items with new tag
                        items = emby_db.getItem_byView(folderid)
                        for item in items:
                            # Remove the "s" from viewtype for tags
                            self._update_tag(
                                current_tagid, tagid, item[0], current_viewtype[:-1])
                    else:
                        # Validate the playlist exists or recreate it
                        if mediatype != "music":
                            self.create_playlist(mediatype, foldername, folderid, viewtype)
                            # Create the video node if not already exists
                            self.create_node(mediatype, foldername, folderid, viewtype)
        # Add video nodes listings
        self.add_single_node(totalnodes, "Favorite movies", "movies", "favourites")
        self.add_single_node(totalnodes, "Favorite tvshows", "tvshows", "favourites")
        self.add_single_node(totalnodes, "Favorite episodes", "episodes", "favourites")
        self.add_single_node(totalnodes, "channels", "movies", "channels")
        # Save total
        window('Emby.nodes.total', str(self.total_nodes))

        # Remove any old referenced views
        log.info("Removing views: %s", current_views)
        for view in current_views:
            self.remove_view(view)

    def create_node(self, media_type, view_name, view_id, view_type):

        if view_name not in self.nodes and media_type not in ('musicvideos', 'music'):
            index = self.sorted_views.index(view_name)
            self.video_nodes.viewNode(index, view_name, media_type,view_type, view_id)
            
            if view_type == "mixed": # Change the value
                self.sorted_views[index] = "%ss" % view_name
            
            self.nodes.append(view_name)
            self.total_nodes += 1

    def add_single_node(self, index, tag, media_type, item_type):
        self.video_nodes.singleNode(index, tag, media_type, item_type)
        self.total_nodes += 1

    def add_view(self, media_type, view_id, view_name, view_type):
        # Generate view, playlist and video node
        log.info("creating view %s: %s", view_name, view_id)
        tag_id = self._get_tag(view_name)

        # Create playlist for the video library
        self.create_playlist(media_type, view_name, view_id, view_type)
        # Create the video node
        self.create_node(media_type, view_name, view_id, view_type)
        # Add view to emby database
        self.emby_db.addView(view_id, view_name, view_type, tag_id)

    def remove_view(self, view):
        # Remove any items that belongs to the old view
        items = self.emby_db.get_item_by_view(view)
        items = [i[0] for i in items] # Convert list of tuple to list
        # TODO: Triage not accessible from here yet
        #self.triage_items("remove", items)

    def create_playlist(self, media_type, view_name, view_id, view_type):

        if view_name not in self.playlists and media_type in ('movies', 'tvshows', 'musicvideos'):

            self._playlist(media_type, view_name, view_id, view_type)
            self.playlists.append(view_name)

    @classmethod
    def _add_playlist(cls, tag, playlist_name, path, media_type):
        # Using write process since there's no guarantee the xml declaration works with etree
        special_types = {'homevideos': "movies"}
        log.info("writing playlist to: %s", path)
        try:
            f = xbmcvfs.File(path, 'w')
        except:
            log.info("failed to create playlist: %s", path)
            return False
        else:
            f.write(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                '<smartplaylist type="%s">\n\t'
                    '<name>Emby %s</name>\n\t'
                    '<match>all</match>\n\t'
                    '<rule field="tag" operator="is">\n\t\t'
                        '<value>%s</value>\n\t'
                    '</rule>'
                '</smartplaylist>'
                % (special_types.get(media_type, media_type), playlist_name, tag))
            f.close()
        log.info("successfully added playlist: %s" % tag)
        return True

    @classmethod
    def _delete_playlist(cls, path):
        xbmcvfs.delete(path)
        log.info("successfully removed playlist: %s", path)

    def _playlist(self, media_type, tag, view_id, view_type="", delete=False):
        # Tagname is in unicode - actions: add or delete
        tag = tag.encode('utf-8')
        path = xbmc.translatePath("special://profile/playlists/video/").decode('utf-8')

        if view_type == "mixed":
            playlist_name = "%s - %s" % (tag, media_type)
            xsp_path = os.path.join(path, "Emby %s - %s.xsp" % (view_id, media_type))
        else:
            playlist_name = tag
            xsp_path = os.path.join(path, "Emby %s" % view_id)

        # Only add the playlist if it doesn't exist
        if xbmcvfs.exists(xsp_path):
            if delete:
                self._delete_playlist(xsp_path)
            return True

        elif not xbmcvfs.exists(path):
            log.info("creating directory: %s", path)
            xbmcvfs.mkdirs(path)

        return self._add_playlist(tag, playlist_name, xsp_path, media_type)

    def _add_tag(self, tag):

        self.kodi_cursor.execute("select coalesce(max(tag_id),0) from tag")
        tag_id = self.kodi_cursor.fetchone()[0] + 1

        query = "INSERT INTO tag(tag_id, name) values(?, ?)"
        self.kodi_cursor.execute(query, (tag_id, tag))
        log.debug("Create tag_id: %s name: %s", tag_id, tag)

        return tag_id

    def _get_tag(self, tag):
        # This will create and return the tag_id
        if KODI in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            self.kodi_cursor.execute(query, (tag,))
            try:
                tag_id = self.kodi_cursor.fetchone()[0]
            except TypeError:
                tag_id = self._add_tag(tag)
        else:# TODO: Remove once Kodi Krypton is RC
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            self.kodi_cursor.execute(query, (tag,))
            try:
                tag_id = self.kodi_cursor.fetchone()[0]
            except TypeError:
                self.kodi_cursor.execute("select coalesce(max(idTag),0) from tag")
                tag_id = self.kodi_cursor.fetchone()[0] + 1

                query = "INSERT INTO tag(idTag, strTag) values(?, ?)"
                self.kodi_cursor.execute(query, (tag_id, tag))
                log.debug("Create idTag: %s name: %s", tag_id, tag)

        return tag_id

    def _update_tag(self, tag, new_tag, kodi_id, media_type):

        log.debug("Updating: %s with %s for %s: %s", tag, new_tag, media_type, kodi_id)

        if KODI in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            try:
                query = ' '.join((

                    "UPDATE tag_link",
                    "SET tag_id = ?",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                self.kodi_cursor.execute(query, (new_tag, kodi_id, media_type, tag,))
            except sqlite3.IntegrityError:
                # The new tag we are going to apply already exists for this item
                # delete current tag instead
                query = ' '.join((

                    "DELETE FROM tag_link",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                self.kodi_cursor.execute(query, (kodi_id, media_type, tag,))
        else:# TODO: Remove once Kodi Krypton is RC
            try:
                query = ' '.join((

                    "UPDATE taglinks",
                    "SET idTag = ?",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.kodi_cursor.execute(query, (new_tag, kodi_id, media_type, tag,))
            except sqlite3.IntegrityError:
                # The new tag we are going to apply already exists for this item
                # delete current tag instead
                query = ' '.join((

                    "DELETE FROM taglinks",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.kodi_cursor.execute(query, (kodi_id, media_type, tag,))


class VideoNodes(object):


    def __init__(self):
        pass

    def commonRoot(self, order, label, tagname, roottype=1):

        if roottype == 0:
            # Index
            root = etree.Element('node', attrib={'order': "%s" % order})
        elif roottype == 1:
            # Filter
            root = etree.Element('node', attrib={'order': "%s" % order, 'type': "filter"})
            etree.SubElement(root, 'match').text = "all"
            # Add tag rule
            rule = etree.SubElement(root, 'rule', attrib={'field': "tag", 'operator': "is"})
            etree.SubElement(rule, 'value').text = tagname
        else:
            # Folder
            root = etree.Element('node', attrib={'order': "%s" % order, 'type': "folder"})

        etree.SubElement(root, 'label').text = label
        etree.SubElement(root, 'icon').text = "special://home/addons/plugin.video.emby/icon.png"

        return root

    def viewNode(self, indexnumber, tagname, mediatype, viewtype, viewid, delete=False):

        if viewtype == "mixed":
            dirname = "%s - %s" % (viewid, mediatype)
        else:
            dirname = viewid
        
        path = xbmc.translatePath("special://profile/library/video/").decode('utf-8')
        nodepath = xbmc.translatePath(
                    "special://profile/library/video/emby/%s/" % dirname).decode('utf-8')

        # Verify the video directory
        if not xbmcvfs.exists(path):
            try:
                shutil.copytree(
                    src=xbmc.translatePath("special://xbmc/system/library/video").decode('utf-8'),
                    dst=xbmc.translatePath("special://profile/library/video").decode('utf-8'))
            except Exception as error:
                log.error(error)

            xbmcvfs.exists(path)

        emby_path = xbmc.translatePath("special://profile/library/video/emby/index.xml").decode('utf-8')
        if not emby_path:
            root = self.commonRoot(order=0, label="Emby", roottype=0)
            try:
                utils.indent(root)
            except: pass
            etree.ElementTree(root).write(emby_path)

        if delete:
            dirs, files = xbmcvfs.listdir(nodepath)
            for file in files:
                xbmcvfs.delete(nodepath + file)

            log.info("Sucessfully removed videonode: %s." % tagname)
            return
        # Create the node directory
        if not xbmcvfs.exists(nodepath) and not mediatype == "photos":
            # We need to copy over the default items
            xbmcvfs.mkdirs(nodepath)

        # Create index entry
        nodeXML = "%sindex.xml" % nodepath
        # Set windows property
        path = "library://video/emby/%s/" % dirname
        for i in range(1, indexnumber):
            # Verify to make sure we don't create duplicates
            if window('Emby.nodes.%s.index' % i) == path:
                return

        if mediatype == "photos":
            path = "plugin://plugin.video.emby/?id=%s&mode=getsubfolders" % indexnumber
            
        window('Emby.nodes.%s.index' % indexnumber, value=path)
        
        # Root
        if not mediatype == "photos":
            if viewtype == "mixed":
                specialtag = "%s - %s" % (tagname, mediatype)
                root = self.commonRoot(order=0, label=specialtag, tagname=tagname, roottype=0)
            else:
                root = self.commonRoot(order=0, label=tagname, tagname=tagname, roottype=0)
            try:
                utils.indent(root)
            except: pass
            etree.ElementTree(root).write(nodeXML)

        nodetypes = {

            '1': "all",
            '2': "recent",
            '3': "recentepisodes",
            '4': "inprogress",
            '5': "inprogressepisodes",
            '6': "unwatched",
            '7': "nextepisodes",
            '8': "sets",
            '9': "genres",
            '10': "random",
            '11': "recommended",
        }
        mediatypes = {
            # label according to nodetype per mediatype
            'movies': 
                {
                '1': tagname,
                '2': 30174,
                '4': 30177,
                '6': 30189,
                '8': 20434,
                '9': 135,
                '10': 30229,
                '11': 30230
                },

            'tvshows': 
                {
                '1': tagname,
                '2': 30170,
                '3': 30175,
                '4': 30171,
                '5': 30178,
                '7': 30179,
                '9': 135,
                '10': 30229,
                '11': 30230
                },
                
            'homevideos': 
                {
                '1': tagname,
                '2': 30251,
                '11': 30253
                },
                
            'photos': 
                {
                '1': tagname,
                '2': 30252,
                '8': 30255,
                '11': 30254
                },

            'musicvideos': 
                {
                '1': tagname,
                '2': 30256,
                '4': 30257,
                '6': 30258
                }
        }

        nodes = mediatypes[mediatype]
        for node in nodes:

            nodetype = nodetypes[node]
            nodeXML = "%s%s.xml" % (nodepath, nodetype)
            # Get label
            stringid = nodes[node]
            if node != "1":
                label = lang(stringid)
                if not label:
                    label = xbmc.getLocalizedString(stringid)
            else:
                label = stringid

            # Set window properties
            if (mediatype == "homevideos" or mediatype == "photos") and nodetype == "all":
                # Custom query
                path = ("plugin://plugin.video.emby/?id=%s&mode=browsecontent&type=%s"
                        % (tagname, mediatype))
            elif (mediatype == "homevideos" or mediatype == "photos"):
                # Custom query
                path = ("plugin://plugin.video.emby/?id=%s&mode=browsecontent&type=%s&folderid=%s"
                        % (tagname, mediatype, nodetype))
            elif nodetype == "nextepisodes":
                # Custom query
                path = "plugin://plugin.video.emby/?id=%s&mode=nextup&limit=25" % tagname
            elif self.kodiversion == 14 and nodetype == "recentepisodes":
                # Custom query
                path = "plugin://plugin.video.emby/?id=%s&mode=recentepisodes&limit=25" % tagname
            elif self.kodiversion == 14 and nodetype == "inprogressepisodes":
                # Custom query
                path = "plugin://plugin.video.emby/?id=%s&mode=inprogressepisodes&limit=25"% tagname
            else:
                path = "library://video/emby/%s/%s.xml" % (viewid, nodetype)
            
            if mediatype == "photos":
                windowpath = "ActivateWindow(Pictures,%s,return)" % path
            else:
                windowpath = "ActivateWindow(Videos,%s,return)" % path
            
            if nodetype == "all":

                if viewtype == "mixed":
                    templabel = "%s - %s" % (tagname, mediatype)
                else:
                    templabel = label

                embynode = "Emby.nodes.%s" % indexnumber
                window('%s.title' % embynode, value=templabel)
                window('%s.path' % embynode, value=windowpath)
                window('%s.content' % embynode, value=path)
                window('%s.type' % embynode, value=mediatype)
            else:
                embynode = "Emby.nodes.%s.%s" % (indexnumber, nodetype)
                window('%s.title' % embynode, value=label)
                window('%s.path' % embynode, value=windowpath)
                window('%s.content' % embynode, value=path)

            if mediatype == "photos":
                # For photos, we do not create a node in videos but we do want the window props
                # to be created.
                # To do: add our photos nodes to kodi picture sources somehow
                continue
            
            if xbmcvfs.exists(nodeXML):
                # Don't recreate xml if already exists
                continue

            # Create the root
            if (nodetype == "nextepisodes" or mediatype == "homevideos" or
                    (self.kodiversion == 14 and nodetype in ('recentepisodes', 'inprogressepisodes'))):
                # Folder type with plugin path
                root = self.commonRoot(order=node, label=label, tagname=tagname, roottype=2)
                etree.SubElement(root, 'path').text = path
                etree.SubElement(root, 'content').text = "episodes"
            else:
                root = self.commonRoot(order=node, label=label, tagname=tagname)
                if nodetype in ('recentepisodes', 'inprogressepisodes'):
                    etree.SubElement(root, 'content').text = "episodes"
                else:
                    etree.SubElement(root, 'content').text = mediatype

                limit = "25"
                # Elements per nodetype
                if nodetype == "all":
                    etree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"
                
                elif nodetype == "recent":
                    etree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"
                    etree.SubElement(root, 'limit').text = limit
                    rule = etree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
                    etree.SubElement(rule, 'value').text = "0"
                
                elif nodetype == "inprogress":
                    etree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})
                    etree.SubElement(root, 'limit').text = limit

                elif nodetype == "genres":
                    etree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"
                    etree.SubElement(root, 'group').text = "genres"
                
                elif nodetype == "unwatched":
                    etree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"
                    rule = etree.SubElement(root, "rule", {'field': "playcount", 'operator': "is"})
                    etree.SubElement(rule, 'value').text = "0"

                elif nodetype == "sets":
                    etree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"
                    etree.SubElement(root, 'group').text = "sets"

                elif nodetype == "random":
                    etree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"
                    etree.SubElement(root, 'limit').text = limit

                elif nodetype == "recommended":
                    etree.SubElement(root, 'order', {'direction': "descending"}).text = "rating"
                    etree.SubElement(root, 'limit').text = limit
                    rule = etree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
                    etree.SubElement(rule, 'value').text = "0"
                    rule2 = etree.SubElement(root, 'rule',
                        attrib={'field': "rating", 'operator': "greaterthan"})
                    etree.SubElement(rule2, 'value').text = "7"

                elif nodetype == "recentepisodes":
                    # Kodi Isengard, Jarvis
                    etree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"
                    etree.SubElement(root, 'limit').text = limit
                    rule = etree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
                    etree.SubElement(rule, 'value').text = "0"

                elif nodetype == "inprogressepisodes":
                    # Kodi Isengard, Jarvis
                    etree.SubElement(root, 'limit').text = "25"
                    rule = etree.SubElement(root, 'rule',
                        attrib={'field': "inprogress", 'operator':"true"})

            try:
                utils.indent(root)
            except: pass
            etree.ElementTree(root).write(nodeXML)

    def singleNode(self, indexnumber, tagname, mediatype, itemtype):

        tagname = tagname.encode('utf-8')
        cleantagname = utils.normalize_nodes(tagname)
        nodepath = xbmc.translatePath("special://profile/library/video/").decode('utf-8')
        nodeXML = "%semby_%s.xml" % (nodepath, cleantagname)
        path = "library://video/emby_%s.xml" % cleantagname
        windowpath = "ActivateWindow(Videos,%s,return)" % path
        
        # Create the video node directory
        if not xbmcvfs.exists(nodepath):
            # We need to copy over the default items
            shutil.copytree(
                src=xbmc.translatePath("special://xbmc/system/library/video").decode('utf-8'),
                dst=xbmc.translatePath("special://profile/library/video").decode('utf-8'))
            xbmcvfs.exists(path)

        labels = {

            'Favorite movies': 30180,
            'Favorite tvshows': 30181,
            'Favorite episodes': 30182,
            'channels': 30173
        }
        label = lang(labels[tagname])
        embynode = "Emby.nodes.%s" % indexnumber
        window('%s.title' % embynode, value=label)
        window('%s.path' % embynode, value=windowpath)
        window('%s.content' % embynode, value=path)
        window('%s.type' % embynode, value=itemtype)

        if xbmcvfs.exists(nodeXML):
            # Don't recreate xml if already exists
            return

        if itemtype == "channels":
            root = self.commonRoot(order=1, label=label, tagname=tagname, roottype=2)
            etree.SubElement(root, 'path').text = "plugin://plugin.video.emby/?id=0&mode=channels"
        elif itemtype == "favourites" and mediatype == "episodes":
            root = self.commonRoot(order=1, label=label, tagname=tagname, roottype=2)
            etree.SubElement(root, 'path').text = "plugin://plugin.video.emby/?id=%s&mode=browsecontent&type=%s&folderid=favepisodes" %(tagname, mediatype)
        else:
            root = self.commonRoot(order=1, label=label, tagname=tagname)
            etree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

        etree.SubElement(root, 'content').text = mediatype

        try:
            utils.indent(root)
        except: pass
        etree.ElementTree(root).write(nodeXML)
