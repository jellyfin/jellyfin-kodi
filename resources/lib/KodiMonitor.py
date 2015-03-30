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
        print "onNotification:" + method + ":" + sender + ":" + str(data)
        #player started playing an item - 
        if method == "Player.OnPlay":
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
            WINDOW = xbmcgui.Window( 10000 )
            if WINDOW.getProperty("suspendDeletes") == "True":
                #This is a handshake to not try to delete if the item was removed from the Kodi DB due to sync
                xbmc.log('Item deleted by sync')
                WINDOW.setProperty("suspendDeletes", "False")
                return
            jsondata = json.loads(data)
            if jsondata != None:
                if jsondata.get("type") == "episode":
                    episodeid = jsondata.get("id")
                    MBlist = WINDOW.getProperty("episodeid" + str(episodeid)).split(";;")
                    #MBlist[0] is the ID, and [1] the title
                    url='http://' + server + '/mediabrowser/Items?Ids=' + MBlist[1] + '&format=json'
                    #This is a check to see if the item exists on the server, if it doesn't it may have already been deleted by another client
                    data = DownloadUtils().downloadUrl(url=url, suppress=True, popup=0)
                    result = json.loads(data)
                    item = result.get("Items")[0]
                    if WINDOW.getProperty("embyid" + item.get("Id")) == "deleted":
                        xbmc.log('Item was already deleted: ' + str(MBlist))
                    elif data != "":
                        return_value = xbmcgui.Dialog().yesno("Confirm Delete", "Delete: "+ MBlist[0] + "\n on Emby Server?")
                        if return_value:
                            url='http://' + server + '/mediabrowser/Items/' + MBlist[1]
                            xbmc.log('Deleting via URL: ' + url)
                            DownloadUtils().downloadUrl(url, type="DELETE")
                
                

