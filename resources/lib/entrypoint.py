# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os
import shutil
import sys
import urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import xbmcplugin

import artwork
import utils
import clientinfo
import connectmanager
import downloadutils
import librarysync
import read_embyserver as embyserver
import embydb_functions as embydb
import playlist
import playbackutils as pbutils
import playutils
import api
from utils import window, settings, dialog, language as lang

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


def doPlayback(itemId, dbId):

    emby = embyserver.Read_EmbyServer()
    item = emby.getItem(itemId)
    pbutils.PlaybackUtils(item).play(itemId, dbId)

##### DO RESET AUTH #####
def resetAuth():
    # User tried login and failed too many times
    resp = xbmcgui.Dialog().yesno(
                heading=lang(30132),
                line1=lang(33050))
    if resp:
        log.info("Reset login attempts.")
        window('emby_serverStatus', value="Auth")
    else:
        xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

def addDirectoryItem(label, path, folder=True):
    li = xbmcgui.ListItem(label, path=path)
    li.setThumbnailImage("special://home/addons/plugin.video.emby/icon.png")
    li.setArt({"fanart":"special://home/addons/plugin.video.emby/fanart.jpg"})
    li.setArt({"landscape":"special://home/addons/plugin.video.emby/fanart.jpg"})
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=li, isFolder=folder)

def doMainListing():

    xbmcplugin.setContent(int(sys.argv[1]), 'files')    
    # Get emby nodes from the window props
    embyprops = window('Emby.nodes.total')
    if embyprops:
        totalnodes = int(embyprops)
        for i in range(totalnodes):
            path = window('Emby.nodes.%s.index' % i)
            if not path:
                path = window('Emby.nodes.%s.content' % i)
            label = window('Emby.nodes.%s.title' % i)
            node = window('Emby.nodes.%s.type' % i)
            
            ''' because we do not use seperate entrypoints for each content type,
                we need to figure out which items to show in each listing.
                for now we just only show picture nodes in the picture library
                video nodes in the video library and all nodes in any other window 
            '''

            if path:
                if xbmc.getCondVisibility("Window.IsActive(Pictures)") and node == "photos":
                    addDirectoryItem(label, path)
                elif xbmc.getCondVisibility("Window.IsActive(Videos)") and node != "photos":
                    addDirectoryItem(label, path)
                elif not xbmc.getCondVisibility("Window.IsActive(Videos) | Window.IsActive(Pictures) | Window.IsActive(Music)"):
                    addDirectoryItem(label, path)

    # experimental live tv nodes
    if not xbmc.getCondVisibility("Window.IsActive(Pictures)"):
        addDirectoryItem(lang(33051),
            "plugin://plugin.video.emby/?mode=browsecontent&type=tvchannels&folderid=root")
        addDirectoryItem(lang(33052),
            "plugin://plugin.video.emby/?mode=browsecontent&type=recordings&folderid=root")

    '''
    TODO: Create plugin listing for servers
    servers = window('emby_servers.json')
    if servers:
        for server in servers:
            log.info(window('emby_server%s.name' % server))
            addDirectoryItem(window('emby_server%s.name' % server), "plugin://plugin.video.emby/?mode=%s" % server)'''

    addDirectoryItem(lang(30517), "plugin://plugin.video.emby/?mode=passwords")
    addDirectoryItem(lang(33053), "plugin://plugin.video.emby/?mode=settings")
    addDirectoryItem(lang(33054), "plugin://plugin.video.emby/?mode=adduser")
    addDirectoryItem(lang(33055), "plugin://plugin.video.emby/?mode=refreshplaylist")
    addDirectoryItem(lang(33056), "plugin://plugin.video.emby/?mode=manualsync")
    addDirectoryItem(lang(33057), "plugin://plugin.video.emby/?mode=repair")
    addDirectoryItem(lang(33058), "plugin://plugin.video.emby/?mode=reset")
    addDirectoryItem(lang(33059), "plugin://plugin.video.emby/?mode=texturecache")
    addDirectoryItem(lang(33060), "plugin://plugin.video.emby/?mode=thememedia")

    if settings('backupPath'):
        addDirectoryItem(lang(33092), "plugin://plugin.video.emby/?mode=backup")
    
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

def emby_connect():
    # Login user to emby connect
    connect = connectmanager.ConnectManager()
    try:
        connectUser = connect.login_connect()
    except RuntimeError:
        return
    else:
        user = connectUser['User']
        token = connectUser['AccessToken']
        username = user['Name']
        dialog(type_="notification",
               heading="{emby}",
               message="%s %s" % (lang(33000), username.decode('utf-8')),
               icon=user.get('ImageUrl') or "{emby}",
               time=2000,
               sound=False)
        
        settings('connectUsername', value=username)

def emby_backup():
    # Create a backup at specified location
    path = settings('backupPath')

    # filename
    default_value = "Kodi%s.%s" % (xbmc.getInfoLabel('System.BuildVersion')[:2],
                                   xbmc.getInfoLabel('System.Date(dd-mm-yy)'))
    filename = dialog(type_="input",
                      heading=lang(33089),
                      defaultt=default_value)
    if not filename:
        return

    backup = os.path.join(path, filename)
    log.info("Backup: %s", backup)

    # Create directory
    if xbmcvfs.exists(backup+"\\"):
        log.info("Existing directory!")
        if not dialog(type_="yesno",
                      heading="{emby}",
                      line1=lang(33090)):
            return emby_backup()
        shutil.rmtree(backup)

    # Addon_data
    shutil.copytree(src=xbmc.translatePath(
                        "special://profile/addon_data/plugin.video.emby").decode('utf-8'),
                    dst=os.path.join(backup, "addon_data", "plugin.video.emby"))

    # Database files
    database = os.path.join(backup, "Database")
    xbmcvfs.mkdir(database)

    shutil.copy(src=utils.getKodiVideoDBPath(),
                dst=database)
    
    if settings('enableMusic') == "true":
        shutil.copy(src=utils.getKodiMusicDBPath(),
                    dst=database)

    dialog(type_="ok",
           heading="{emby}",
           line1="%s: %s" % (lang(33091), backup))

##### Generate a new deviceId
def resetDeviceId():

    dialog = xbmcgui.Dialog()

    deviceId_old = window('emby_deviceId')
    try:
        window('emby_deviceId', clear=True)
        deviceId = clientinfo.ClientInfo().get_device_id(reset=True)
    except Exception as e:
        log.error("Failed to generate a new device Id: %s" % e)
        dialog.ok(
            heading=lang(29999),
            line1=lang(33032))
    else:
        log.info("Successfully removed old deviceId: %s New deviceId: %s" % (deviceId_old, deviceId))
        dialog.ok(
            heading=lang(29999),
            line1=lang(33033))
        xbmc.executebuiltin('RestartApp')

##### Delete Item
def deleteItem():

    # Serves as a keymap action
    if xbmc.getInfoLabel('ListItem.Property(embyid)'): # If we already have the embyid
        itemId = xbmc.getInfoLabel('ListItem.Property(embyid)')
    else:
        dbId = xbmc.getInfoLabel('ListItem.DBID')
        itemType = xbmc.getInfoLabel('ListItem.DBTYPE')

        if not itemType:

            if xbmc.getCondVisibility('Container.Content(albums)'):
                itemType = "album"
            elif xbmc.getCondVisibility('Container.Content(artists)'):
                itemType = "artist"
            elif xbmc.getCondVisibility('Container.Content(songs)'):
                itemType = "song"
            elif xbmc.getCondVisibility('Container.Content(pictures)'):
                itemType = "picture"
            else:
                log.info("Unknown type, unable to proceed.")
                return

        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        emby_db = embydb.Embydb_Functions(embycursor)
        item = emby_db.getItem_byKodiId(dbId, itemType)
        embycursor.close()

        try:
            itemId = item[0]
        except TypeError:
            log.error("Unknown itemId, unable to proceed.")
            return

    if settings('skipContextMenu') != "true":
        resp = xbmcgui.Dialog().yesno(
                                heading=lang(29999),
                                line1=lang(33041))
        if not resp:
            log.info("User skipped deletion for: %s." % itemId)
            return
    
    embyserver.Read_EmbyServer().deleteItem(itemId)

##### ADD ADDITIONAL USERS #####
def addUser():

    doUtils = downloadutils.DownloadUtils()
    art = artwork.Artwork()
    clientInfo = clientinfo.ClientInfo()
    deviceId = clientInfo.get_device_id()
    deviceName = clientInfo.get_device_name()
    userid = window('emby_currUser')
    dialog = xbmcgui.Dialog()

    # Get session
    url = "{server}/emby/Sessions?DeviceId=%s&format=json" % deviceId
    result = doUtils.downloadUrl(url)
    
    try:
        sessionId = result[0]['Id']
        additionalUsers = result[0]['AdditionalUsers']
        # Add user to session
        userlist = {}
        users = []
        url = "{server}/emby/Users?IsDisabled=false&IsHidden=false&format=json"
        result = doUtils.downloadUrl(url)

        # pull the list of users
        for user in result:
            name = user['Name']
            userId = user['Id']
            if userid != userId:
                userlist[name] = userId
                users.append(name)

        # Display dialog if there's additional users
        if additionalUsers:

            option = dialog.select(lang(33061), [lang(33062), lang(33063)])
            # Users currently in the session
            additionalUserlist = {}
            additionalUsername = []
            # Users currently in the session
            for user in additionalUsers:
                name = user['UserName']
                userId = user['UserId']
                additionalUserlist[name] = userId
                additionalUsername.append(name)

            if option == 1:
                # User selected Remove user
                resp = dialog.select(lang(33064), additionalUsername)
                if resp > -1:
                    selected = additionalUsername[resp]
                    selected_userId = additionalUserlist[selected]
                    url = "{server}/emby/Sessions/%s/Users/%s" % (sessionId, selected_userId)
                    doUtils.downloadUrl(url, postBody={}, action_type="DELETE")
                    dialog.notification(
                            heading=lang(29999),
                            message="%s %s" % (lang(33066), selected),
                            icon="special://home/addons/plugin.video.emby/icon.png",
                            time=1000)

                    # clear picture
                    position = window('EmbyAdditionalUserPosition.%s' % selected_userId)
                    window('EmbyAdditionalUserImage.%s' % position, clear=True)
                    return
                else:
                    return

            elif option == 0:
                # User selected Add user
                for adduser in additionalUsername:
                    try: # Remove from selected already added users. It is possible they are hidden.
                        users.remove(adduser)
                    except: pass

            elif option < 0:
                # User cancelled
                return

        # Subtract any additional users
        log.info("Displaying list of users: %s" % users)
        resp = dialog.select("Add user to the session", users)
        # post additional user
        if resp > -1:
            selected = users[resp]
            selected_userId = userlist[selected]
            url = "{server}/emby/Sessions/%s/Users/%s" % (sessionId, selected_userId)
            doUtils.downloadUrl(url, postBody={}, action_type="POST")
            dialog.notification(
                    heading=lang(29999),
                    message="%s %s" % (lang(33067), selected),
                    icon="special://home/addons/plugin.video.emby/icon.png",
                    time=1000)

    except:
        log.error("Failed to add user to session.")
        dialog.notification(
                heading=lang(29999),
                message=lang(33068),
                icon=xbmcgui.NOTIFICATION_ERROR)

    # Add additional user images
    # always clear the individual items first
    totalNodes = 10
    for i in range(totalNodes):
        if not window('EmbyAdditionalUserImage.%s' % i):
            break
        window('EmbyAdditionalUserImage.%s' % i, clear=True)

    url = "{server}/emby/Sessions?DeviceId=%s" % deviceId
    result = doUtils.downloadUrl(url)
    additionalUsers = result[0]['AdditionalUsers']
    count = 0
    for additionaluser in additionalUsers:
        userid = additionaluser['UserId']
        url = "{server}/emby/Users/%s?format=json" % userid
        result = doUtils.downloadUrl(url)
        window('EmbyAdditionalUserImage.%s' % count,
            value=art.get_user_artwork(result['Id'], 'Primary'))
        window('EmbyAdditionalUserPosition.%s' % userid, value=str(count))
        count +=1

##### THEME MUSIC/VIDEOS #####
def getThemeMedia():

    doUtils = downloadutils.DownloadUtils()
    dialog = xbmcgui.Dialog()
    playback = None

    # Choose playback method
    resp = dialog.select(lang(33072), [lang(30165), lang(33071)])
    if resp == 0:
        playback = "DirectPlay"
    elif resp == 1:
        playback = "DirectStream"
    else:
        return

    library = xbmc.translatePath(
                "special://profile/addon_data/plugin.video.emby/library/").decode('utf-8')
    # Create library directory
    if not xbmcvfs.exists(library):
        xbmcvfs.mkdir(library)

    # Set custom path for user
    tvtunes_path = xbmc.translatePath(
        "special://profile/addon_data/script.tvtunes/").decode('utf-8')
    if xbmcvfs.exists(tvtunes_path):
        tvtunes = xbmcaddon.Addon(id="script.tvtunes")
        tvtunes.setSetting('custom_path_enable', "true")
        tvtunes.setSetting('custom_path', library)
        log.info("TV Tunes custom path is enabled and set.")
    else:
        # if it does not exist this will not work so warn user
        # often they need to edit the settings first for it to be created.
        dialog.ok(heading=lang(29999), line1=lang(33073))
        xbmc.executebuiltin('Addon.OpenSettings(script.tvtunes)')
        return
        
    # Get every user view Id
    embyconn = utils.kodiSQL('emby')
    embycursor = embyconn.cursor()
    emby_db = embydb.Embydb_Functions(embycursor)
    viewids = emby_db.getViews()
    embycursor.close()

    # Get Ids with Theme Videos
    itemIds = {}
    for view in viewids:
        url = "{server}/emby/Users/{UserId}/Items?HasThemeVideo=True&ParentId=%s&format=json" % view
        result = doUtils.downloadUrl(url)
        if result['TotalRecordCount'] != 0:
            for item in result['Items']:
                itemId = item['Id']
                folderName = item['Name']
                folderName = utils.normalize_string(folderName.encode('utf-8'))
                itemIds[itemId] = folderName

    # Get paths for theme videos
    for itemId in itemIds:
        nfo_path = xbmc.translatePath(
            "special://profile/addon_data/plugin.video.emby/library/%s/" % itemIds[itemId])
        # Create folders for each content
        if not xbmcvfs.exists(nfo_path):
            xbmcvfs.mkdir(nfo_path)
        # Where to put the nfos
        nfo_path = "%s%s" % (nfo_path, "tvtunes.nfo")

        url = "{server}/emby/Items/%s/ThemeVideos?format=json" % itemId
        result = doUtils.downloadUrl(url)

        # Create nfo and write themes to it
        nfo_file = xbmcvfs.File(nfo_path, 'w')
        pathstowrite = ""
        # May be more than one theme
        for theme in result['Items']:
            putils = playutils.PlayUtils(theme)
            if playback == "DirectPlay":
                playurl = putils.directPlay()
            else:
                playurl = putils.directStream()
            pathstowrite += ('<file>%s</file>' % playurl.encode('utf-8'))
        
        # Check if the item has theme songs and add them   
        url = "{server}/emby/Items/%s/ThemeSongs?format=json" % itemId
        result = doUtils.downloadUrl(url)

        # May be more than one theme
        for theme in result['Items']:
            putils = playutils.PlayUtils(theme)  
            if playback == "DirectPlay":
                playurl = putils.directPlay()
            else:
                playurl = putils.directStream()
            pathstowrite += ('<file>%s</file>' % playurl.encode('utf-8'))

        nfo_file.write(
            '<tvtunes>%s</tvtunes>' % pathstowrite
        )
        # Close nfo file
        nfo_file.close()

    # Get Ids with Theme songs
    musicitemIds = {}
    for view in viewids:
        url = "{server}/emby/Users/{UserId}/Items?HasThemeSong=True&ParentId=%s&format=json" % view
        result = doUtils.downloadUrl(url)
        if result['TotalRecordCount'] != 0:
            for item in result['Items']:
                itemId = item['Id']
                folderName = item['Name']
                folderName = utils.normalize_string(folderName.encode('utf-8'))
                musicitemIds[itemId] = folderName

    # Get paths
    for itemId in musicitemIds:
        
        # if the item was already processed with video themes back out
        if itemId in itemIds:
            continue
        
        nfo_path = xbmc.translatePath(
            "special://profile/addon_data/plugin.video.emby/library/%s/" % musicitemIds[itemId])
        # Create folders for each content
        if not xbmcvfs.exists(nfo_path):
            xbmcvfs.mkdir(nfo_path)
        # Where to put the nfos
        nfo_path = "%s%s" % (nfo_path, "tvtunes.nfo")
        
        url = "{server}/emby/Items/%s/ThemeSongs?format=json" % itemId
        result = doUtils.downloadUrl(url)

        # Create nfo and write themes to it
        nfo_file = xbmcvfs.File(nfo_path, 'w')
        pathstowrite = ""
        # May be more than one theme
        for theme in result['Items']: 
            putils = playutils.PlayUtils(theme)
            if playback == "DirectPlay":
                playurl = putils.directPlay()
            else:
                playurl = putils.directStream()
            pathstowrite += ('<file>%s</file>' % playurl.encode('utf-8'))

        nfo_file.write(
            '<tvtunes>%s</tvtunes>' % pathstowrite
        )
        # Close nfo file
        nfo_file.close()

    dialog.notification(
            heading=lang(29999),
            message=lang(33069),
            icon="special://home/addons/plugin.video.emby/icon.png",
            time=1000,
            sound=False)

##### REFRESH EMBY PLAYLISTS #####
def refreshPlaylist():

    lib = librarysync.LibrarySync()
    dialog = xbmcgui.Dialog()
    try:
        # First remove playlists
        utils.deletePlaylists()
        # Remove video nodes
        utils.deleteNodes()
        # Refresh views
        lib.refreshViews()
        dialog.notification(
                heading=lang(29999),
                message=lang(33069),
                icon="special://home/addons/plugin.video.emby/icon.png",
                time=1000,
                sound=False)

    except Exception as e:
        log.error("Refresh playlists/nodes failed: %s" % e)
        dialog.notification(
            heading=lang(29999),
            message=lang(33070),
            icon=xbmcgui.NOTIFICATION_ERROR,
            time=1000,
            sound=False)

#### SHOW SUBFOLDERS FOR NODE #####
def GetSubFolders(nodeindex):
    nodetypes = ["",".recent",".recentepisodes",".inprogress",".inprogressepisodes",".unwatched",".nextepisodes",".sets",".genres",".random",".recommended"]
    for node in nodetypes:
        title = window('Emby.nodes.%s%s.title' %(nodeindex,node))
        if title:
            path = window('Emby.nodes.%s%s.content' %(nodeindex,node))
            addDirectoryItem(title, path)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
              
##### BROWSE EMBY NODES DIRECTLY #####    
def BrowseContent(viewname, browse_type="", folderid=""):
    
    emby = embyserver.Read_EmbyServer()
    art = artwork.Artwork()
    doUtils = downloadutils.DownloadUtils()
    
    #folderid used as filter ?
    if folderid in ["recent","recentepisodes","inprogress","inprogressepisodes","unwatched","nextepisodes","sets","genres","random","recommended"]:
        filter_type = folderid
        folderid = ""
    else:
        filter_type = ""
    
    xbmcplugin.setPluginCategory(int(sys.argv[1]), viewname)
    #get views for root level
    if not folderid:
        views = emby.getViews(browse_type)
        for view in views:
            if view.get("name") == viewname.decode('utf-8'):
                folderid = view.get("id")
                break
    
    if viewname is not None:
        log.info("viewname: %s - type: %s - folderid: %s - filter: %s" %(viewname.decode('utf-8'), browse_type.decode('utf-8'), folderid.decode('utf-8'), filter_type.decode('utf-8')))
    #set the correct params for the content type
    #only proceed if we have a folderid
    if folderid:
        if browse_type.lower() == "homevideos":
            xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
            itemtype = "Video,Folder,PhotoAlbum"
        elif browse_type.lower() == "photos":
            xbmcplugin.setContent(int(sys.argv[1]), 'files')
            itemtype = "Photo,PhotoAlbum,Folder"
        else:
            itemtype = ""
        
        #get the actual listing
        if browse_type == "recordings":
            listing = emby.getTvRecordings(folderid)
        elif browse_type == "tvchannels":
            listing = emby.getTvChannels()
        elif filter_type == "recent":
            listing = emby.getFilteredSection(folderid, itemtype=itemtype.split(",")[0], sortby="DateCreated", recursive=True, limit=25, sortorder="Descending")
        elif filter_type == "random":
            listing = emby.getFilteredSection(folderid, itemtype=itemtype.split(",")[0], sortby="Random", recursive=True, limit=150, sortorder="Descending")
        elif filter_type == "recommended":
            listing = emby.getFilteredSection(folderid, itemtype=itemtype.split(",")[0], sortby="SortName", recursive=True, limit=25, sortorder="Ascending", filter_type="IsFavorite")
        elif folderid == "favepisodes":
            xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
            listing = emby.getFilteredSection(None, itemtype="Episode", sortby="SortName", recursive=True, limit=25, sortorder="Ascending", filter_type="IsFavorite")
        elif filter_type == "sets":
            listing = emby.getFilteredSection(folderid, itemtype=itemtype.split(",")[1], sortby="SortName", recursive=True, limit=25, sortorder="Ascending", filter_type="IsFavorite")
        else:
            listing = emby.getFilteredSection(folderid, itemtype=itemtype, recursive=False)
        
        #process the listing
        if listing:
            for item in listing.get("Items"):
                li = createListItemFromEmbyItem(item,art,doUtils)
                if item.get("IsFolder") == True:
                    #for folders we add an additional browse request, passing the folderId
                    path = "%s?id=%s&mode=browsecontent&type=%s&folderid=%s" % (sys.argv[0].decode('utf-8'), viewname.decode('utf-8'), browse_type.decode('utf-8'), item.get("Id").decode('utf-8'))
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=li, isFolder=True)
                else:
                    #playable item, set plugin path and mediastreams
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=li.getProperty("path"), listitem=li)


    if filter_type == "recent":
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
    else:
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_TITLE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### CREATE LISTITEM FROM EMBY METADATA #####
def createListItemFromEmbyItem(item,art=artwork.Artwork(),doUtils=downloadutils.DownloadUtils()):
    API = api.API(item)
    itemid = item['Id']
    
    title = item.get('Name')
    li = xbmcgui.ListItem(title)
    
    premieredate = item.get('PremiereDate',"")
    if not premieredate: premieredate = item.get('DateCreated',"")
    if premieredate:
        premieredatelst = premieredate.split('T')[0].split("-")
        premieredate = "%s.%s.%s" %(premieredatelst[2],premieredatelst[1],premieredatelst[0])

    li.setProperty("embyid",itemid)
    
    allart = art.get_all_artwork(item)
    
    if item["Type"] == "Photo":
        #listitem setup for pictures...
        img_path = allart.get('Primary')
        li.setProperty("path",img_path)
        picture = doUtils.downloadUrl("{server}/Items/%s/Images" %itemid)
        if picture:
            picture = picture[0]
            if picture.get("Width") > picture.get("Height"):
                li.setArt( {"fanart":  img_path}) #add image as fanart for use with skinhelper auto thumb/backgrund creation
            li.setInfo('pictures', infoLabels={ "picturepath": img_path, "date": premieredate, "size": picture.get("Size"), "exif:width": str(picture.get("Width")), "exif:height": str(picture.get("Height")), "title": title})
        li.setThumbnailImage(img_path)
        li.setProperty("plot",API.get_overview())
        li.setIconImage('DefaultPicture.png')
    else:
        #normal video items
        li.setProperty('IsPlayable', 'true')
        path = "%s?id=%s&mode=play" % (sys.argv[0], item.get("Id"))
        li.setProperty("path",path)
        genre = API.get_genres()
        overlay = 0
        userdata = API.get_userdata()
        runtime = item.get("RunTimeTicks",0)/ 10000000.0
        seektime = userdata['Resume']
        if seektime:
            li.setProperty("resumetime", str(seektime))
            li.setProperty("totaltime", str(runtime))
        
        played = userdata['Played']
        if played: overlay = 7
        else: overlay = 6       
        playcount = userdata['PlayCount']
        if playcount is None:
            playcount = 0
            
        rating = item.get('CommunityRating')
        if not rating: rating = userdata['UserRating']

        # Populate the extradata list and artwork
        extradata = {
            'id': itemid,
            'rating': rating,
            'year': item.get('ProductionYear'),
            'genre': genre,
            'playcount': str(playcount),
            'title': title,
            'plot': API.get_overview(),
            'Overlay': str(overlay),
            'duration': runtime
        }
        if premieredate:
            extradata["premieredate"] = premieredate
            extradata["date"] = premieredate
        li.setInfo('video', infoLabels=extradata)
        if allart.get('Primary'):
            li.setThumbnailImage(allart.get('Primary'))
        else: li.setThumbnailImage('DefaultTVShows.png')
        li.setIconImage('DefaultTVShows.png')
        if not allart.get('Background'): #add image as fanart for use with skinhelper auto thumb/backgrund creation
            li.setArt( {"fanart": allart.get('Primary') } )
        else:
            pbutils.PlaybackUtils(item).setArtwork(li)

        mediastreams = API.get_media_streams()
        videostreamFound = False
        if mediastreams:
            for key, value in mediastreams.iteritems():
                if key == "video" and value: videostreamFound = True
                if value: li.addStreamInfo(key, value[0])
        if not videostreamFound:
            #just set empty streamdetails to prevent errors in the logs
            li.addStreamInfo("video", {'duration': runtime})
        
    return li
    
##### BROWSE EMBY CHANNELS #####    
def BrowseChannels(itemid, folderid=None):
    
    _addon_id   =   int(sys.argv[1])
    _addon_url  =   sys.argv[0]
    doUtils = downloadutils.DownloadUtils()
    art = artwork.Artwork()

    xbmcplugin.setContent(int(sys.argv[1]), 'files')
    if folderid:
        url = (
                "{server}/emby/Channels/%s/Items?userid={UserId}&folderid=%s&format=json"
                % (itemid, folderid))
    elif itemid == "0":
        # id 0 is the root channels folder
        url = "{server}/emby/Channels?{UserId}&format=json"
    else:
        url = "{server}/emby/Channels/%s/Items?UserId={UserId}&format=json" % itemid

    result = doUtils.downloadUrl(url)
    if result and result.get("Items"):
        for item in result.get("Items"):
            itemid = item['Id']
            itemtype = item['Type']
            li = createListItemFromEmbyItem(item,art,doUtils)
            
            isFolder = item.get('IsFolder', False)

            channelId = item.get('ChannelId', "")
            channelName = item.get('ChannelName', "")
            if itemtype == "Channel":
                path = "%s?id=%s&mode=channels" % (_addon_url, itemid)
                xbmcplugin.addDirectoryItem(handle=_addon_id, url=path, listitem=li, isFolder=True)
            elif isFolder:
                path = "%s?id=%s&mode=channelsfolder&folderid=%s" % (_addon_url, channelId, itemid)
                xbmcplugin.addDirectoryItem(handle=_addon_id, url=path, listitem=li, isFolder=True)
            else:
                path = "%s?id=%s&mode=play" % (_addon_url, itemid)
                li.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(handle=_addon_id, url=path, listitem=li)

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### LISTITEM SETUP FOR VIDEONODES #####
def createListItem(item):

    title = item['title']
    li = xbmcgui.ListItem(title)
    li.setProperty('IsPlayable', "true")
    
    metadata = {

        'Title': title,
        'duration': str(item['runtime']/60),
        'Plot': item['plot'],
        'Playcount': item['playcount']
    }

    if "episode" in item:
        episode = item['episode']
        metadata['Episode'] = episode

    if "season" in item:
        season = item['season']
        metadata['Season'] = season

    if season and episode:
        li.setProperty('episodeno', "s%.2de%.2d" % (season, episode))

    if "firstaired" in item:
        metadata['Premiered'] = item['firstaired']

    if "showtitle" in item:
        metadata['TVshowTitle'] = item['showtitle']

    if "rating" in item:
        metadata['Rating'] = str(round(float(item['rating']),1))

    if "director" in item:
        metadata['Director'] = " / ".join(item['director'])

    if "writer" in item:
        metadata['Writer'] = " / ".join(item['writer'])

    if "cast" in item:
        cast = []
        castandrole = []
        for person in item['cast']:
            name = person['name']
            cast.append(name)
            castandrole.append((name, person['role']))
        metadata['Cast'] = cast
        metadata['CastAndRole'] = castandrole

    li.setInfo(type="Video", infoLabels=metadata)  
    li.setProperty('resumetime', str(item['resume']['position']))
    li.setProperty('totaltime', str(item['resume']['total']))
    li.setArt(item['art'])
    li.setThumbnailImage(item['art'].get('thumb',''))
    li.setIconImage('DefaultTVShows.png')
    li.setProperty('dbid', str(item['episodeid']))
    li.setProperty('fanart_image', item['art'].get('tvshow.fanart',''))
    for key, value in item['streamdetails'].iteritems():
        for stream in value:
            li.addStreamInfo(key, stream)
    
    return li

##### GET NEXTUP EPISODES FOR TAGNAME #####    
def getNextUpEpisodes(tagname, limit):
    
    count = 0
    # if the addon is called with nextup parameter,
    # we return the nextepisodes list of the given tagname
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    # First we get a list of all the TV shows - filtered by tag
    query = {

        'jsonrpc': "2.0",
        'id': "libTvShows",
        'method': "VideoLibrary.GetTVShows",
        'params': {

            'sort': {'order': "descending", 'method': "lastplayed"},
            'filter': {
                'and': [
                    {'operator': "true", 'field': "inprogress", 'value': ""},
                    {'operator': "is", 'field': "tag", 'value': "%s" % tagname}
                ]},
            'properties': ['title', 'studio', 'mpaa', 'file', 'art']
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(result)
    # If we found any, find the oldest unwatched show for each one.
    try:
        items = result['result']['tvshows']
    except (KeyError, TypeError):
        pass
    else:
        for item in items:
            if settings('ignoreSpecialsNextEpisodes') == "true":
                query = {

                    'jsonrpc': "2.0",
                    'id': 1,
                    'method': "VideoLibrary.GetEpisodes",
                    'params': {

                        'tvshowid': item['tvshowid'],
                        'sort': {'method': "episode"},
                        'filter': {
                            'and': [
                                {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                                {'operator': "greaterthan", 'field': "season", 'value': "0"}
                        ]},
                        'properties': [
                            "title", "playcount", "season", "episode", "showtitle",
                            "plot", "file", "rating", "resume", "tvshowid", "art",
                            "streamdetails", "firstaired", "runtime", "writer",
                            "dateadded", "lastplayed"
                        ],
                        'limits': {"end": 1}
                    }
                }
            else:
                query = {

                    'jsonrpc': "2.0",
                    'id': 1,
                    'method': "VideoLibrary.GetEpisodes",
                    'params': {

                        'tvshowid': item['tvshowid'],
                        'sort': {'method': "episode"},
                        'filter': {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                        'properties': [
                            "title", "playcount", "season", "episode", "showtitle",
                            "plot", "file", "rating", "resume", "tvshowid", "art",
                            "streamdetails", "firstaired", "runtime", "writer",
                            "dateadded", "lastplayed"
                        ],
                        'limits': {"end": 1}
                    }
                }

            result = xbmc.executeJSONRPC(json.dumps(query))
            result = json.loads(result)
            try:
                episodes = result['result']['episodes']
            except (KeyError, TypeError):
                pass
            else:
                for episode in episodes:
                    li = createListItem(episode)
                    xbmcplugin.addDirectoryItem(
                                handle=int(sys.argv[1]),
                                url=episode['file'],
                                listitem=li)
                    count += 1

            if count == limit:
                break

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### GET INPROGRESS EPISODES FOR TAGNAME #####    
def getInProgressEpisodes(tagname, limit):
    
    count = 0
    # if the addon is called with inprogressepisodes parameter,
    # we return the inprogressepisodes list of the given tagname
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    # First we get a list of all the in-progress TV shows - filtered by tag
    query = {

        'jsonrpc': "2.0",
        'id': "libTvShows",
        'method': "VideoLibrary.GetTVShows",
        'params': {

            'sort': {'order': "descending", 'method': "lastplayed"},
            'filter': {
                'and': [
                    {'operator': "true", 'field': "inprogress", 'value': ""},
                    {'operator': "is", 'field': "tag", 'value': "%s" % tagname}
                ]},
            'properties': ['title', 'studio', 'mpaa', 'file', 'art']
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(result)
    # If we found any, find the oldest unwatched show for each one.
    try:
        items = result['result']['tvshows']
    except (KeyError, TypeError):
        pass
    else:
        for item in items:
            query = {

                'jsonrpc': "2.0",
                'id': 1,
                'method': "VideoLibrary.GetEpisodes",
                'params': {

                    'tvshowid': item['tvshowid'],
                    'sort': {'method': "episode"},
                    'filter': {'operator': "true", 'field': "inprogress", 'value': ""},
                    'properties': [
                        "title", "playcount", "season", "episode", "showtitle", "plot",
                        "file", "rating", "resume", "tvshowid", "art", "cast",
                        "streamdetails", "firstaired", "runtime", "writer",
                        "dateadded", "lastplayed"
                    ]
                }
            }
            result = xbmc.executeJSONRPC(json.dumps(query))
            result = json.loads(result)
            try:
                episodes = result['result']['episodes']
            except (KeyError, TypeError):
                pass
            else:
                for episode in episodes:
                    li = createListItem(episode)
                    xbmcplugin.addDirectoryItem(
                                handle=int(sys.argv[1]),
                                url=episode['file'],
                                listitem=li)
                    count += 1

            if count == limit:
                break

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### GET RECENT EPISODES FOR TAGNAME #####    
def getRecentEpisodes(tagname, limit):
    
    count = 0
    # if the addon is called with recentepisodes parameter,
    # we return the recentepisodes list of the given tagname
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    # First we get a list of all the TV shows - filtered by tag
    query = {

        'jsonrpc': "2.0",
        'id': "libTvShows",
        'method': "VideoLibrary.GetTVShows",
        'params': {

            'sort': {'order': "descending", 'method': "dateadded"},
            'filter': {'operator': "is", 'field': "tag", 'value': "%s" % tagname},
            'properties': ["title","sorttitle"]
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(result)
    # If we found any, find the oldest unwatched show for each one.
    try:
        items = result['result']['tvshows']
    except (KeyError, TypeError):
        pass
    else:
        allshowsIds = set()
        for item in items:
            allshowsIds.add(item['tvshowid'])

        query = {

            'jsonrpc': "2.0",
            'id': 1,
            'method': "VideoLibrary.GetEpisodes",
            'params': {

                'sort': {'order': "descending", 'method': "dateadded"},
                'filter': {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                'properties': [
                    "title", "playcount", "season", "episode", "showtitle", "plot",
                    "file", "rating", "resume", "tvshowid", "art", "streamdetails",
                    "firstaired", "runtime", "cast", "writer", "dateadded", "lastplayed"
                ],
                "limits": {"end": limit}
            }
        }
        result = xbmc.executeJSONRPC(json.dumps(query))
        result = json.loads(result)
        try:
            episodes = result['result']['episodes']
        except (KeyError, TypeError):
            pass
        else:
            for episode in episodes:
                if episode['tvshowid'] in allshowsIds:
                    li = createListItem(episode)
                    xbmcplugin.addDirectoryItem(
                                handle=int(sys.argv[1]),
                                url=episode['file'],
                                listitem=li)
                    count += 1

                if count == limit:
                    break

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### GET VIDEO EXTRAS FOR LISTITEM #####
def getVideoFiles(embyId,embyPath):
    #returns the video files for the item as plugin listing, can be used for browsing the actual files or videoextras etc.
    emby = embyserver.Read_EmbyServer()
    if not embyId:
        if "plugin.video.emby" in embyPath:
            embyId = embyPath.split("/")[-2]
    if embyId:
        item = emby.getItem(embyId)
        putils = playutils.PlayUtils(item)
        if putils.isDirectPlay():
            #only proceed if we can access the files directly. TODO: copy local on the fly if accessed outside
            filelocation = putils.directPlay()
            if not filelocation.endswith("/"):
                filelocation = filelocation.rpartition("/")[0]
            dirs, files = xbmcvfs.listdir(filelocation)
            for file in files:
                file = filelocation + file
                li = xbmcgui.ListItem(file, path=file)
                xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=file, listitem=li)
            for dir in dirs:
                dir = filelocation + dir
                li = xbmcgui.ListItem(dir, path=dir)
                xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=dir, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    
##### GET EXTRAFANART FOR LISTITEM #####
def getExtraFanArt(embyId,embyPath):
    
    emby = embyserver.Read_EmbyServer()
    art = artwork.Artwork()
    
    # Get extrafanart for listitem 
    # will be called by skinhelper script to get the extrafanart
    try:
        # for tvshows we get the embyid just from the path
        if not embyId:
            if "plugin.video.emby" in embyPath:
                embyId = embyPath.split("/")[-2]
        
        if embyId:
            #only proceed if we actually have a emby id
            log.info("Requesting extrafanart for Id: %s" % embyId)

            # We need to store the images locally for this to work
            # because of the caching system in xbmc
            fanartDir = xbmc.translatePath("special://thumbnails/emby/%s/" % embyId).decode('utf-8')
            
            if not xbmcvfs.exists(fanartDir):
                # Download the images to the cache directory
                xbmcvfs.mkdirs(fanartDir)
                item = emby.getItem(embyId)
                if item:
                    backdrops = art.get_all_artwork(item)['Backdrop']
                    tags = item['BackdropImageTags']
                    count = 0
                    for backdrop in backdrops:
                        # Same ordering as in artwork
                        tag = tags[count]
                        if os.path.supports_unicode_filenames:
                            fanartFile = os.path.join(fanartDir, "fanart%s.jpg" % tag)
                        else:
                            fanartFile = os.path.join(fanartDir.encode("utf-8"), "fanart%s.jpg" % tag.encode("utf-8"))
                        li = xbmcgui.ListItem(tag, path=fanartFile)
                        xbmcplugin.addDirectoryItem(
                                            handle=int(sys.argv[1]),
                                            url=fanartFile,
                                            listitem=li)
                        xbmcvfs.copy(backdrop, fanartFile) 
                        count += 1               
            else:
                log.debug("Found cached backdrop.")
                # Use existing cached images
                dirs, files = xbmcvfs.listdir(fanartDir)
                for file in files:
                    fanartFile = os.path.join(fanartDir, file.decode('utf-8'))
                    li = xbmcgui.ListItem(file, path=fanartFile)
                    xbmcplugin.addDirectoryItem(
                                            handle=int(sys.argv[1]),
                                            url=fanartFile,
                                            listitem=li)
    except Exception as e:
        log.error("Error getting extrafanart: %s" % e)
    
    # Always do endofdirectory to prevent errors in the logs
    xbmcplugin.endOfDirectory(int(sys.argv[1]))