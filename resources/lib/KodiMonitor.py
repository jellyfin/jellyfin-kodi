#################################################################################################
# Kodi  Monitor
# Watched events that occur in Kodi, like setting media watched
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import json

import Utils as utils
from WriteKodiDB import WriteKodiDB
from ReadKodiDB import ReadKodiDB
from PlayUtils import PlayUtils
from DownloadUtils import DownloadUtils
from PlaybackUtils import PlaybackUtils

class Kodi_Monitor(xbmc.Monitor):
    def __init__(self, *args, **kwargs):
        xbmc.Monitor.__init__(self)

    def onDatabaseUpdated(self, database):
        pass
    
    #this library monitor is used to detect a watchedstate change by the user through the library
    #as well as detect when a library item has been deleted to pass the delete to the Emby server
    def onNotification  (self,sender,method,data):
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        downloadUtils = DownloadUtils()
        print "onNotification:" + method + ":" + sender + ":" + str(data)
        #player started playing an item - 
        if method == "Playlist.OnAdd":
            print "playlist onadd is called"
            jsondata = json.loads(data)
            if jsondata != None:
                if jsondata.has_key("item"):
                    if jsondata.get("item").has_key("id") and jsondata.get("item").has_key("type"):
                        id = jsondata.get("item").get("id")
                        type = jsondata.get("item").get("type")
                        embyid = ReadKodiDB().getEmbyIdByKodiId(id,type)
                        
                        print "id --> " + str(id)
                        print "type --> " + type
                        print "emby_id --> " + embyid
                        if embyid != None:
                           
                            WINDOW = xbmcgui.Window( 10000 )
                            
                            username = WINDOW.getProperty('currUser')
                            userid = WINDOW.getProperty('userId%s' % username)
                            server = WINDOW.getProperty('server%s' % username)

                            url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&ImageTypeLimit=1" % embyid
                            result = downloadUtils.downloadUrl(url)     
                            
                            userData = result[u'UserData']

                            playurl = PlayUtils().getPlayUrl(server, embyid, result)
                            thumbPath = API().getArtwork(result, "Primary")

                            watchedurl = "%s/mediabrowser/Users/%s/PlayedItems/%s" % (server, userid, embyid)
                            positionurl = "%s/mediabrowser/Users/%s/PlayingItems/%s" % (server, userid, embyid)
                            deleteurl = "%s/mediabrowser/Items/%s" % (server, embyid)
                            
                            listItem = xbmcgui.ListItem(path=playurl, iconImage=thumbPath, thumbnailImage=thumbPath)
                            self.setListItemProps(server, id, listItem, result)    

                            # Can not play virtual items
                            if (result.get("LocationType") == "Virtual"):
                              xbmcgui.Dialog().ok(self.language(30128), self.language(30129))

                            # set the current playing info
                            WINDOW.setProperty(playurl+"watchedurl", watchedurl)
                            WINDOW.setProperty(playurl+"positionurl", positionurl)
                            WINDOW.setProperty(playurl+"deleteurl", "")
                            WINDOW.setProperty(playurl+"deleteurl", deleteurl)
                            if result[u'Type']=="Episode":
                                WINDOW.setProperty(playurl+"refresh_id", result[u'SeriesId'])
                            else:
                                WINDOW.setProperty(playurl+"refresh_id", embyid)
                                
                            WINDOW.setProperty(playurl+"runtimeticks", str(result[u'RunTimeTicks']))
                            WINDOW.setProperty(playurl+"type", result[u'Type'])
                            WINDOW.setProperty(playurl+"item_id", embyid)

                            if PlayUtils().isDirectPlay(result) == True:
                                playMethod = "DirectPlay"
                            else:
                                playMethod = "Transcode"

                            WINDOW.setProperty(playurl+"playmethod", playMethod)
                            
                            if result.get("Type")=="Episode":
                                WINDOW.setProperty(playurl+"refresh_id", result.get("SeriesId"))
                            else:
                                WINDOW.setProperty(playurl+"refresh_id", id)
                                
                            mediaSources = result[u'MediaSources']
                            if(mediaSources != None):
                                if mediaSources[0].get('DefaultAudioStreamIndex') != None:
                                    WINDOW.setProperty(playurl+"AudioStreamIndex", str(mediaSources[0][u'DefaultAudioStreamIndex']))  
                                if mediaSources[0].get('DefaultSubtitleStreamIndex') != None:
                                    WINDOW.setProperty(playurl+"SubtitleStreamIndex", str(mediaSources[0][u'DefaultSubtitleStreamIndex']))
                            
                            # start the playback
                            PlaybackUtils().PLAY(id)
        
        if method == "VideoLibrary.OnUpdate":
            jsondata = json.loads(data)
            if jsondata != None:
                
                playcount = None
                playcount = jsondata.get("playcount")
                item = jsondata.get("item").get("id")
                type = jsondata.get("item").get("type")
                if playcount != None:
                    utils.logMsg("MB# Sync","Kodi_Monitor--> VideoLibrary.OnUpdate : " + str(data),2)
                    WriteKodiDB().updatePlayCountFromKodi(item, type, playcount)
                    
                
                

