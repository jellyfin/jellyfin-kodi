#!/usr/bin/python
# -*- coding: utf-8 -*-

from traceback import print_exc
import xbmc
import xbmcgui
import threading
import Utils as utils
from ReadKodiDB import ReadKodiDB
from ClientInformation import ClientInformation

class LibraryMonitor(threading.Thread):
    
    event = None
    exit = False
    liPath = None
    liPathLast = None
    WINDOW = xbmcgui.Window(10000)

    clientInfo = ClientInformation()
    addonName = clientInfo.getAddonName()
    
    def __init__(self, *args):
        
        self.event =  threading.Event()
        threading.Thread.__init__(self, *args)

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))
    
    def stop(self):
        self.logMsg("LibraryMonitor - stop called",0)
        self.exit = True
        self.event.set()
    
    def run(self):
        self.logMsg("LIBRARY MONITOR running ")
        WINDOW = self.WINDOW
        lastListItemLabel = None

        while (self.exit != True):

            # monitor listitem props when videolibrary is active
            if (xbmc.getCondVisibility("[Window.IsActive(videolibrary) | Window.IsActive(movieinformation)] + !Window.IsActive(fullscreenvideo)")):

                self.liPath = xbmc.getInfoLabel("ListItem.Path")
                liLabel = xbmc.getInfoLabel("ListItem.Label")
                if ((liLabel != lastListItemLabel) and xbmc.getCondVisibility("!Container.Scrolling")):
                    
                    self.liPathLast = self.liPath
                    lastListItemLabel = liLabel
                    
                    # update the listitem stuff
                    try:
                        self.setRatingsInfo()
                    except Exception as e:
                        self.logMsg("ERROR in LibraryMonitor ! --> " + str(e), 0)
  
            else:
                #reset window props
                WINDOW.clearProperty("EmbySkinHelper.ListItemRottenTomatoes")
                WINDOW.clearProperty('EmbySkinHelper.ListItemRottenTomatoesSummary')
                WINDOW.clearProperty('EmbySkinHelper.ListItemMetaScore')
                
            xbmc.sleep(150)

    def setRatingsInfo(self):
        WINDOW = self.WINDOW

        embyId = self.liPath.split("/")[-2]
        criticrating = ReadKodiDB().getCriticRatingByEmbyId(embyId)
        if criticrating:
            WINDOW.setProperty('EmbySkinHelper.ListItemRottenTomatoes', criticrating)
        else:
            WINDOW.clearProperty('EmbySkinHelper.ListItemRottenTomatoes')

        criticratingsummary = ReadKodiDB().getCriticRatingSummaryByEmbyId(embyId)
        if criticratingsummary:
            WINDOW.setProperty('EmbySkinHelper.ListItemRottenTomatoesSummary', criticratingsummary)
        else:
            WINDOW.clearProperty('EmbySkinHelper.ListItemRottenTomatoesSummary')

        metascore = ReadKodiDB().getMetaScoreRatingByEmbyId(embyId)
        if metascore:
            WINDOW.setProperty('EmbySkinHelper.ListItemMetaScore', metascore)
        else:
            WINDOW.clearProperty('EmbySkinHelper.ListItemMetaScore')
