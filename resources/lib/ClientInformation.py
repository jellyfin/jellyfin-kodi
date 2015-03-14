from uuid import uuid4 as uuid4
import xbmc
import xbmcaddon
import xbmcgui
import os
from Lock import Lock

class ClientInformation():

    def getMachineId(self):
    
        WINDOW = xbmcgui.Window( 10000 )
        
        clientId = WINDOW.getProperty("client_id")
        if(clientId != None and clientId != ""):
            return clientId
            
        # we need to load and or generate a client machine id    
        __addon__ = xbmcaddon.Addon(id='plugin.video.mb3sync')
        __addondir__ = xbmc.translatePath( __addon__.getAddonInfo('path'))
        machine_guid_lock_path = os.path.join(__addondir__, "machine_guid.lock")
        machine_guid_path = os.path.join(__addondir__, "machine_guid")
        clientId = ""
        
        try:
            lock = Lock(machine_guid_lock_path)
            locked = lock.acquire()
            
            if(locked == True):
            
                fd = os.open(machine_guid_path, os.O_CREAT|os.O_RDWR)
                clientId = os.read(fd, 256)
                
                if(len(clientId) == 0):
                    uuid = uuid4()
                    clientId = str("%012X" % uuid)
                    xbmc.log("CLIENT_ID - > Client ID saved to FILE : " + clientId)                    
                    os.write(fd, clientId)
                    os.fsync(fd)
                    
                os.close(fd)
                
                xbmc.log("CLIENT_ID - > Client ID saved to WINDOW : " + clientId)
                WINDOW.setProperty("client_id", clientId)
                 
        finally: 
            lock.release()
                
        return clientId
        
    def getVersion(self):
        version = xbmcaddon.Addon(id="plugin.video.mb3sync").getAddonInfo("version")
        return version
        
        
    def getPlatform(self):

        if xbmc.getCondVisibility('system.platform.osx'):
            return "OSX"
        elif xbmc.getCondVisibility('system.platform.atv2'):
            return "ATV2"
        elif xbmc.getCondVisibility('system.platform.ios'):
            return "iOS"
        elif xbmc.getCondVisibility('system.platform.windows'):
            return "Windows"
        elif xbmc.getCondVisibility('system.platform.linux'):
            return "Linux/RPi"
        elif xbmc.getCondVisibility('system.platform.android'): 
            return "Linux/Android"

        return "Unknown"
