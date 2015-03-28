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

class Kodi_Monitor(xbmc.Monitor):
    def __init__(self, *args, **kwargs):
        xbmc.Monitor.__init__(self)

    def onDatabaseUpdated(self, database):
        pass
    
    #this library monitor is used to detect a watchedstate change by the user through the library
    #as well as detect when a library item has been deleted to pass the delete to the Emby server
    def onNotification  (self,sender,method,data):
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        downloadUtils = DownloadUtils()
        
        #player started playing an item - 
        if "Playlist.OnAdd" in method:
            print "playlist onadd is called"
            jsondata = json.loads(data)
            if jsondata != None:
                if jsondata.has_key("item"):
                    if jsondata.get("item").has_key("id") and jsondata.get("item").has_key("type"):
                        id = jsondata.get("item").get("id")
                        type = jsondata.get("item").get("type")
                        embyid = ReadKodiDB().getEmbyIdByKodiId(id,type)

                        if embyid != None:
                           
                            WINDOW = xbmcgui.Window( 10000 )
                            
                            userid = downloadUtils.getUserId()
                            jsonData = downloadUtils.downloadUrl("http://" + server + "/mediabrowser/Users/" + userid + "/Items/" + embyid + "?format=json&ImageTypeLimit=1", suppress=False, popup=1 )     
                            result = json.loads(jsonData)
                            userData = result.get("UserData")
                            
                            playurl = PlayUtils().getPlayUrl(server, embyid, result)
                            
                            watchedurl = 'http://' + server + '/mediabrowser/Users/'+ userid + '/PlayedItems/' + embyid
                            positionurl = 'http://' + server + '/mediabrowser/Users/'+ userid + '/PlayingItems/' + embyid
                            deleteurl = 'http://' + server + '/mediabrowser/Items/' + embyid

                            # set the current playing info
                            WINDOW.setProperty(playurl+"watchedurl", watchedurl)
                            WINDOW.setProperty(playurl+"positionurl", positionurl)
                            WINDOW.setProperty(playurl+"deleteurl", "")
                            WINDOW.setProperty(playurl+"deleteurl", deleteurl)
                            if result.get("Type")=="Episode":
                                WINDOW.setProperty(playurl+"refresh_id", result.get("SeriesId"))
                            else:
                                WINDOW.setProperty(playurl+"refresh_id", embyid)
                                
                            WINDOW.setProperty(playurl+"runtimeticks", str(result.get("RunTimeTicks")))
                            WINDOW.setProperty(playurl+"type", result.get("Type"))
                            WINDOW.setProperty(playurl+"item_id", embyid)

                            if PlayUtils().isDirectPlay(result) == True:
                                playMethod = "DirectPlay"
                            else:
                                playMethod = "Transcode"

                            WINDOW.setProperty(playurl+"playmethod", playMethod)
                                
                            mediaSources = result.get("MediaSources")
                            if(mediaSources != None):
                                if mediaSources[0].get('DefaultAudioStreamIndex') != None:
                                    WINDOW.setProperty(playurl+"AudioStreamIndex", str(mediaSources[0].get('DefaultAudioStreamIndex')))  
                                if mediaSources[0].get('DefaultSubtitleStreamIndex') != None:
                                    WINDOW.setProperty(playurl+"SubtitleStreamIndex", str(mediaSources[0].get('DefaultSubtitleStreamIndex')))
        
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
        if method == "VideoLibrary.OnRemove":
            xbmc.log('Intercepted remove from sender: ' + sender + ' method: ' + method + ' data: ' + data)
            jsondata = json.loads(data)
            if jsondata != None:
                if jsondata.get("type") == "episode":
                    episodeid = jsondata.get("id")
                    WINDOW = xbmcgui.Window( 10000 )
                    #ignore if the item has just been deleted by the background sync
                    if not WINDOW.getProperty(episodeid,"deleted"):
                        MBlist = WINDOW.getProperty("episodeid" + str(episodeid)).split(";;")
                        url='http://' + server + '/mediabrowser/Items?Ids=' + MBlist[1] + '&format=json'
                        data = DownloadUtils().downloadUrl(url=url, suppress=True, popup=0)
                        if data != "":
                            return_value = xbmcgui.Dialog().yesno("Confirm Delete", "Delete: "+ MBlist[0] + "\n on Emby Server?\nEmbyID: " + MBlist[1])
                            if return_value:
                                url='http://' + server + '/mediabrowser/Items/' + MBlist[1]
                                xbmc.log('Deleting via URL: ' + url)
                                DownloadUtils().downloadUrl(url, type="DELETE")
                
                

