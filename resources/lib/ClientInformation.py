from uuid import uuid4 as uuid4
import xbmc
import xbmcaddon
import xbmcgui


class ClientInformation():

    def getMachineId(self):
    
        WINDOW = xbmcgui.Window( 10000 )
        
        clientId = WINDOW.getProperty("client_id")
        self.addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
        if(clientId == None or clientId == ""):
            xbmc.log("CLIENT_ID - > No Client ID in WINDOW")
            clientId = self.addonSettings.getSetting('client_id')
        
            if(clientId == None or clientId == ""):
                xbmc.log("CLIENT_ID - > No Client ID in SETTINGS")
                uuid = uuid4()
                clientId = str("%012X" % uuid)
                WINDOW.setProperty("client_id", clientId)
                self.addonSettings.setSetting('client_id', clientId)
                xbmc.log("CLIENT_ID - > New Client ID : " + clientId)
            else:
                WINDOW.setProperty('client_id', clientId)
                xbmc.log("CLIENT_ID - > Client ID saved to WINDOW from Settings : " + clientId)
                
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
