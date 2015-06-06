
import sys
import xbmc
import xbmcgui
import xbmcaddon
import json as json
import urllib

ACTION_BACK = 92
    
class UserPreferences(xbmcgui.WindowXMLDialog):

    configuration = None
    save = False
    name = None
    image = None
    
    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):
        self.action_exitkeys_id = [10, 13]
        # set the dialog data
        
        cinemaMode = self.configuration.get(u'EnableCinemaMode')
        self.getControl(8011).setSelected(cinemaMode)
        self.getControl(8001).setLabel(self.name)
        self.getControl(8002).setImage(self.image)
    def save(self):
        self.save = True
        
    def isSave(self):
        return self.save
    
    def setConfiguration(self, configuration):
        self.configuration = configuration
        
    def getConfiguration(self):
        return self.configuration
    
    def setName(self, name):
        self.name = name
        
    def setImage(self, image):
        self.image = image
        
    def onFocus(self, controlId):
        pass
        
    def doAction(self):
        pass

    def closeDialog(self):
        self.close()        
        
    def onClick(self, controlID):
        
        if(controlID == 8012):
            # save now
            self.save()
            self.close()
        
        elif(controlID == 8013):
            #cancel
            self.close()
            
        if(controlID == 8011):
            # cinema mode
            cinemamode = self.getControl(8011).isSelected()
            self.configuration['EnableCinemaMode'] = cinemamode

        pass
    
    def onAction(self, action):
        if action == ACTION_BACK:
            self.close()
     

