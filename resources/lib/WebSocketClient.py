#################################################################################################
# WebSocket Client thread
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon

import json
import threading
import urllib
import socket
import websocket

import KodiMonitor
import Utils as utils

from ClientInformation import ClientInformation
from DownloadUtils import DownloadUtils
from PlaybackUtils import PlaybackUtils
from LibrarySync import LibrarySync
from WriteKodiVideoDB import WriteKodiVideoDB
from ReadEmbyDB import ReadEmbyDB

pendingUserDataList = []
pendingItemsToRemove = []
pendingItemsToUpdate = []
_MODE_BASICPLAY=12

class WebSocketThread(threading.Thread):

    _shared_state = {}

    clientInfo = ClientInformation()
    KodiMonitor = KodiMonitor.Kodi_Monitor()
    addonName = clientInfo.getAddonName()

    client = None
    keepRunning = True
    
    def __init__(self, *args):

        self.__dict__ = self._shared_state
        threading.Thread.__init__(self, *args)
    
    def logMsg(self, msg, lvl=1):

        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, int(lvl))
    
    def sendProgressUpdate(self, data):
        self.logMsg("sendProgressUpdate", 1)
        if self.client:
            try:
                # Send progress update
                messageData = {
                    'MessageType': "ReportPlaybackProgress",
                    'Data': data
                }
                messageString = json.dumps(messageData)
                self.client.send(messageString)
                self.logMsg("Message data: %s" % messageString, 2)
            except Exception, e:
                self.logMsg("Exception: %s" % e, 1)  
    
    def stopClient(self):
        # stopping the client is tricky, first set keep_running to false and then trigger one 
        # more message by requesting one SessionsStart message, this causes the 
        # client to receive the message and then exit
        if(self.client != None):
            self.logMsg("Stopping Client")
            self.keepRunning = False
            self.client.keep_running = False            
            self.client.close() 
            self.logMsg("Stopping Client : KeepRunning set to False")
            '''
            try:
                self.keepRunning = False
                self.client.keep_running = False
                self.logMsg("Stopping Client")
                self.logMsg("Calling Ping")
                self.client.sock.ping()
                
                self.logMsg("Calling Socket Shutdown()")
                self.client.sock.sock.shutdown(socket.SHUT_RDWR)
                self.logMsg("Calling Socket Close()")
                self.client.sock.sock.close()
                self.logMsg("Stopping Client Done")
                self.logMsg("Calling Ping")
                self.client.sock.ping()     
                               
            except Exception, e:
                self.logMsg("Exception : " + str(e), level=0)      
            '''
        else:
            self.logMsg("Stopping Client NO Object ERROR")
            
    def on_message(self, ws, message):
        global pendingUserDataList
        global pendingItemsToRemove
        global pendingItemsToUpdate
        self.logMsg("Message : " + str(message), 0)
        result = json.loads(message)
        
        messageType = result.get("MessageType")
        data = result.get("Data")
        
        if(messageType != None and messageType == "Play" and data != None):
            itemIds = data.get("ItemIds")
            playCommand = data.get("PlayCommand")
            
            if(playCommand != None and playCommand == "PlayNow"):
            
                xbmc.executebuiltin("Dialog.Close(all,true)")
                startPositionTicks = data.get("StartPositionTicks")
                PlaybackUtils().PLAYAllItems(itemIds, startPositionTicks)
                xbmc.executebuiltin("XBMC.Notification(Playlist: Added " + str(len(itemIds)) + " items to Playlist,)")

            elif(playCommand != None and playCommand == "PlayNext"):
            
                playlist = PlaybackUtils().AddToPlaylist(itemIds)
                xbmc.executebuiltin("XBMC.Notification(Playlist: Added " + str(len(itemIds)) + " items to Playlist,)")
                if(xbmc.Player().isPlaying() == False):
                    xbmc.Player().play(playlist)
                            
        elif(messageType != None and messageType == "Playstate"):
            command = data.get("Command")
            if(command != None and command == "Stop"):
                self.logMsg("Playback Stopped")
                xbmc.executebuiltin('xbmc.activatewindow(10000)')
                xbmc.Player().stop()
            elif(command != None and command == "Pause"):
                self.logMsg("Playback Paused")
                xbmc.Player().pause()
            elif(command != None and command == "Unpause"):
                self.logMsg("Playback UnPaused")
                xbmc.Player().pause()
            elif(command != None and command == "NextTrack"):
                self.logMsg("Playback NextTrack")
                xbmc.Player().playnext()
            elif(command != None and command == "PreviousTrack"):
                self.logMsg("Playback PreviousTrack")
                xbmc.Player().playprevious()
            elif(command != None and command == "Seek"):
                seekPositionTicks = data.get("SeekPositionTicks")
                self.logMsg("Playback Seek : " + str(seekPositionTicks))
                seekTime = (seekPositionTicks / 1000) / 10000
                xbmc.Player().seekTime(seekTime)
                
        elif(messageType != None and messageType == "UserDataChanged"):
            # for now just do a full playcount sync
            WINDOW = xbmcgui.Window( 10000 )
            self.logMsg("Message : Doing UserDataChanged", 0)
            userDataList = data.get("UserDataList")
            self.logMsg("Message : Doing UserDataChanged : UserDataList : " + str(userDataList), 0)
            if(userDataList != None):
                if xbmc.Player().isPlaying():
                    pendingUserDataList += userDataList
                else:
                    self.user_data_update(userDataList)
        
        elif(messageType != None and messageType == "LibraryChanged"):
            foldersAddedTo = data.get("FoldersAddedTo")
            foldersRemovedFrom = data.get("FoldersRemovedFrom")
            
            # doing items removed
            itemsRemoved = data.get("ItemsRemoved")
            itemsAdded = data.get("ItemsAdded")
            itemsUpdated = data.get("ItemsUpdated")
            itemsToUpdate = itemsAdded + itemsUpdated
            self.logMsg("Message : WebSocket LibraryChanged : Items Added : " + str(itemsAdded), 0)
            self.logMsg("Message : WebSocket LibraryChanged : Items Updated : " + str(itemsUpdated), 0)
            self.logMsg("Message : WebSocket LibraryChanged : Items Removed : " + str(itemsRemoved), 0)

            #if xbmc.Player().isPlaying():
            #    pendingItemsToRemove += itemsRemoved
            #    pendingItemsToUpdate += itemsToUpdate
            #else:
            self.remove_items(itemsRemoved)
            self.update_items(itemsToUpdate)

        elif messageType == "GeneralCommand":
            
            if data.get("Name") == "DisplayMessage":
                message = data.get("Arguments")
                header = message[u'Header']
                text = message[u'Text']
                xbmcgui.Dialog().notification(header, text)

            elif data.get("Name") == "SendString":
                message = data.get("Arguments")
                string = message[u'String']
                xbmcgui.Dialog().notification("Emby server", string)

    def remove_items(self, itemsRemoved):
        
        #Process video library
        connection = utils.KodiSQL("video")
        cursor = connection.cursor()
        for item in itemsRemoved:
            self.logMsg("Message : Doing LibraryChanged : Items Removed : Calling deleteItemFromKodiLibrary: " + item, 0)
            WriteKodiVideoDB().deleteItemFromKodiLibrary(item, connection, cursor)
        connection.commit()
        cursor.close()
        
        #Process music library
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        if addon.getSetting("enableMusicSync") == "true":
            connection = utils.KodiSQL("music")
            cursor = connection.cursor()
            for item in itemsRemoved:
                self.logMsg("Message : Doing LibraryChanged : Items Removed : Calling deleteItemFromKodiLibrary (musiclibrary): " + item, 0)
                WriteKodiMusicDB().deleteItemFromKodiLibrary(item, connection, cursor)
            connection.commit()
            cursor.close()

    def update_items(self, itemsToUpdate):
        # doing adds and updates
        if(len(itemsToUpdate) > 0):
            self.logMsg("Message : Doing LibraryChanged : Processing Added and Updated : " + str(itemsToUpdate), 0)
            LibrarySync().IncrementalSync(itemsToUpdate)

    def user_data_update(self, userDataList):
        itemsToUpdate = list()
        for userData in userDataList:
            itemId = userData.get("ItemId")
            if(itemId != None):
                itemsToUpdate.append(itemId)
        if(len(itemsToUpdate) > 0):
            self.logMsg("Message : Doing UserDataChanged : Processing Updated : " + str(itemsToUpdate), 0)
            LibrarySync().IncrementalSync(itemsToUpdate)
                
    def on_error(self, ws, error):
        if "10061" in str(error):
            # Server is offline
            pass
        else:
            self.logMsg("Error: %s" % error, 1)
        #raise

    def on_close(self, ws):
        self.logMsg("Closed", 2)

    def on_open(self, ws):
        pass

    def run(self):
        
        WINDOW = xbmcgui.Window(10000)
        logLevel = int(WINDOW.getProperty('logLevel'))
        username = WINDOW.getProperty('currUser')
        server = WINDOW.getProperty('server%s' % username)
        token = WINDOW.getProperty('accessToken%s' % username)
        deviceId = ClientInformation().getMachineId()

        if (logLevel == 2):
            websocket.enableTrace(True)        

        # Get the appropriate prefix for websocket
        if "https" in server:
            server = server.replace('https', 'wss')
        else:
            server = server.replace('http', 'ws')
        
        websocketUrl = "%s?api_key=%s&deviceId=%s" % (server, token, deviceId)
        self.logMsg("websocket URL: %s" % websocketUrl)

        self.client = websocket.WebSocketApp(websocketUrl,
                                    on_message = self.on_message,
                                    on_error = self.on_error,
                                    on_close = self.on_close)
                                    
        self.client.on_open = self.on_open
        
        while not self.KodiMonitor.abortRequested():
            
            self.client.run_forever()

            if (self.keepRunning):
                # Server is not online
                if WINDOW.getProperty("Server_online") == "true":
                    self.logMsg("Server is unreachable.", 1)
                    WINDOW.setProperty("Server_online", "false")
                    xbmcgui.Dialog().notification("Error connecting", "Server is unreachable.")
                
                if self.KodiMonitor.waitForAbort(5):
                    break

        self.logMsg("Thread Exited")
        
        
    def processPendingActions(self):
        global pendingUserDataList
        global pendingItemsToRemove
        global pendingItemsToUpdate    
        if pendingUserDataList != []:
            self.user_data_update(pendingUserDataList)
            pendingUserDataList = []
        if pendingItemsToRemove != []:
            self.remove_items(pendingItemsToRemove)
            pendingItemsToRemove = []
        if pendingItemsToUpdate != []:
            self.update_items(pendingItemsToUpdate)
            pendingItemsToUpdate = []