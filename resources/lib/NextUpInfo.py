
import sys
import xbmc
import xbmcgui
import xbmcaddon
import json as json
import urllib
from API import API
from PlaybackUtils import PlaybackUtils

ACTION_PLAYER_STOP = 13
    
class NextUpInfo(xbmcgui.WindowXMLDialog):

    item = None
    cancel = False
    watchnow = False
    
    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):
        self.action_exitkeys_id = [10, 13]
        
        image = API().getArtwork(self.item, "Primary2")
        clearartimage = API().getArtwork(self.item, "Art")
        overview = API().getOverview(self.item)
        name = API().getName(self.item)
        
        episodeInfo = ""
        season = str(self.item.get("ParentIndexNumber"))
        episodeNum = str(self.item.get("IndexNumber"))
        episodeInfo = season + "x" + episodeNum + "."
        
        rating = None
        if self.item.get("CommunityRating") != None and self.item.get("CommunityRating") !="":
            rating = str(self.item.get("CommunityRating"))
        year =  API().getPremiereDate(self.item)
        duration = str(int(self.item.get("RunTimeTicks", "0"))/(10000000*60))
        info = year + " " + str(duration) + " min"
        # set the dialog data
        self.getControl(3000).setLabel(name)
        self.getControl(3001).setText(overview)
        self.getControl(3002).setLabel(episodeInfo)
        self.getControl(3004).setLabel(info)
        
        self.getControl(3009).setImage(image)
        self.getControl(3006).setImage(clearartimage)
        
        if rating != None:
            self.getControl(3003).setLabel(rating)
        else:
            self.getControl(3003).setVisible(False)
        
        
    def setItem(self, item):
        self.item = item
    
    def setCancel(self, cancel):
        self.cancel = cancel
        
    def isCancel(self):
        return self.cancel
            
    def setWatchNow(self, watchnow):
        self.watchnow = watchnow
    
    def isWatchNow(self):
        return self.watchnow
    
    def onFocus(self, controlId):
        pass
        
    def doAction(self):
        pass

    def closeDialog(self):
        self.close()        
        
    def onClick(self, controlID):
        
        xbmc.log("nextup info onclick: "+str(controlID))

        if(controlID == 3012):
            # watch now
            self.setWatchNow(True)
            self.close()
        
        elif(controlID == 3013):
            #cancel
            self.setCancel(True)
            self.close()

        pass
    
    def onAction(self, action):
        
        xbmc.log("nextup info action: "+str(action.getId()))
        if action == ACTION_PLAYER_STOP:
            self.close()
     

