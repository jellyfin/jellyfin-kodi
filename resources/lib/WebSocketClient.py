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
from ClientInformation import ClientInformation
from DownloadUtils import DownloadUtils
from PlaybackUtils import PlaybackUtils
from LibrarySync import LibrarySync

_MODE_BASICPLAY=12

class WebSocketThread(threading.Thread):

    logLevel = 0
    client = None
    keepRunning = True
    
    def __init__(self, *args):
        addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
        level = addonSettings.getSetting('logLevel')        
        self.logLevel = 0
        if(level != None):
            self.logLevel = int(level)           
    
        xbmc.log("emby WebSocketThread -> Log Level:" +  str(self.logLevel))
        
        threading.Thread.__init__(self, *args)
    
    def logMsg(self, msg, level = 1):
        if(self.logLevel >= level):
            try:
                xbmc.log("emby WebSocketThread -> " + str(msg))
            except UnicodeEncodeError:
                try:
                    xbmc.log("emby WebSocketThread -> " + str(msg.encode('utf-8')))
                except: pass
            
    '''
    def playbackStarted(self, itemId):
        if(self.client != None):
            try:
                self.logMsg("Sending Playback Started")
                messageData = {}
                messageData["MessageType"] = "PlaybackStart"
                messageData["Data"] = itemId + "|true|audio,video"
                messageString = json.dumps(messageData)
                self.logMsg("Message Data : " + messageString)
                self.client.send(messageString)
            except Exception, e:
                self.logMsg("Exception : " + str(e), level=0)
        else:
            self.logMsg("Sending Playback Started NO Object ERROR")
    '''

    '''
    def playbackStopped(self, itemId, ticks):
        if(self.client != None):
            try:
                self.logMsg("Sending Playback Stopped")
                messageData = {}
                messageData["MessageType"] = "PlaybackStopped"
                messageData["Data"] = itemId + "|" + str(ticks)
                messageString = json.dumps(messageData)
                self.client.send(messageString)
            except Exception, e:
                self.logMsg("Exception : " + str(e), level=0)            
        else:
            self.logMsg("Sending Playback Stopped NO Object ERROR")
    '''

    '''
    def sendProgressUpdate(self, itemId, ticks):
        if(self.client != None):
            try:
                self.logMsg("Sending Progress Update")
                messageData = {}
                messageData["MessageType"] = "PlaybackProgress"
                messageData["Data"] = itemId + "|" + str(ticks) + "|false|false"
                messageString = json.dumps(messageData)
                self.logMsg("Message Data : " + messageString)
                self.client.send(messageString)
            except Exception, e:
                self.logMsg("Exception : " + str(e), level=0)              
        else:
            self.logMsg("Sending Progress Update NO Object ERROR")
    '''
    
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
                for userData in userDataList:
                    self.logMsg("Message : Doing UserDataChanged : UserData : " + str(userData), 0)
                    userKey = userData.get("Key")
                    if(userKey != None):
                        embyItemId = WINDOW.getProperty("EmbyUserKey" + userKey).split(";;")
                        self.logMsg("Message : Doing UserDataChanged : window data : " + str(embyItemId), 0)
                        if(embyItemId != None and len(embyItemId) == 2):
                            LibrarySync().updatePlayCount(embyItemId[0], embyItemId[1])
        
        elif(messageType != None and messageType == "LibraryChanged"):
            foldersAddedTo = data.get("FoldersAddedTo")
            foldersRemovedFrom = data.get("FoldersRemovedFrom")
            
            # doing items removed
            itemsRemoved = data.get("ItemsRemoved")
            self.logMsg("Message : Doing LibraryChanged : Items Removed : " + str(itemsRemoved), 0)
            
            # doing adds and updates
            itemsAdded = data.get("ItemsAdded")
            self.logMsg("Message : Doing LibraryChanged : Items Added : " + str(itemsAdded), 0)
            itemsUpdated = data.get("ItemsUpdated")
            self.logMsg("Message : Doing LibraryChanged : Items Updated : " + str(itemsUpdated), 0)
            itemsToUpdate = itemsAdded + itemsUpdated
            if(len(itemsToUpdate) > 0):
                self.logMsg("Message : Doing LibraryChanged : Processing Added and Updated : " + str(itemsToUpdate), 0)
                LibrarySync().MoviesSync(fullsync = False, installFirstRun = False, itemList = itemsToUpdate)
                LibrarySync().TvShowsSync(fullsync = False, installFirstRun = False, itemList = itemsToUpdate)
        
    def on_error(self, ws, error):
        self.logMsg("Error : " + str(error))
        #raise

    def on_close(self, ws):
        self.logMsg("Closed")

    def on_open(self, ws):

        clientInfo = ClientInformation()
        machineId = clientInfo.getMachineId()
        version = clientInfo.getVersion()
        messageData = {}
        messageData["MessageType"] = "Identity"
        
        addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
        deviceName = addonSettings.getSetting('deviceName')
        deviceName = deviceName.replace("\"", "_")
    
        messageData["Data"] = "Kodi|" + machineId + "|" + version + "|" + deviceName
        messageString = json.dumps(messageData)
        self.logMsg("Opened : " + str(messageString))
        ws.send(messageString)
        
        # Set Capabilities
        xbmc.log("postcapabilities_called")
        downloadUtils = DownloadUtils()
        downloadUtils.postcapabilities()
           
        
    def getWebSocketPort(self, host, port):
        
        userUrl = "http://" + host + ":" + port + "/mediabrowser/System/Info?format=json"
         
        downloadUtils = DownloadUtils()
        jsonData = downloadUtils.downloadUrl(userUrl, suppress=False, popup=1 )
        if(jsonData == ""):
            return -1
            
        result = json.loads(jsonData)
        
        wsPort = result.get("WebSocketPortNumber")
        if(wsPort != None):
            return wsPort
        else:
            return -1

    def run(self):
    
        addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
        mb3Host = addonSettings.getSetting('ipaddress')
        mb3Port = addonSettings.getSetting('port')
        
        if(self.logLevel >= 1):
            websocket.enableTrace(True)        
        '''
        wsPort = self.getWebSocketPort(mb3Host, mb3Port);
        self.logMsg("WebSocketPortNumber = " + str(wsPort))
        if(wsPort == -1):
            self.logMsg("Could not retrieve WebSocket port, can not run WebScoket Client")
            return
        '''
        # Make a call to /System/Info. WebSocketPortNumber is the port hosting the web socket.
        webSocketUrl = "ws://" +  mb3Host + ":" + mb3Port + "/mediabrowser"
        self.logMsg("WebSocket URL : " + webSocketUrl)
        self.client = websocket.WebSocketApp(webSocketUrl,
                                    on_message = self.on_message,
                                    on_error = self.on_error,
                                    on_close = self.on_close)
                                    
        self.client.on_open = self.on_open
        
        while(self.keepRunning):
            self.logMsg("Client Starting")
            self.client.run_forever()
            if(self.keepRunning):
                self.logMsg("Client Needs To Restart")
                xbmc.sleep(10000)
            
        self.logMsg("Thread Exited")
        
        
        
        