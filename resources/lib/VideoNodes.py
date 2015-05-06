#################################################################################################
# VideoNodes - utils to create video nodes listings in kodi for the emby addon
#################################################################################################


import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import os
import shutil
from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.etree import ElementTree
from xml.dom import minidom
import xml.etree.cElementTree as ET

import Utils as utils

from ReadEmbyDB import ReadEmbyDB
WINDOW = xbmcgui.Window(10000)

addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
language = addonSettings.getLocalizedString

class VideoNodes():   
       
   
    def buildVideoNodeForView(self, tagname, type, windowPropId):
        #this method will build a video node for a particular Emby view (= tag in kodi)
        #we set some window props here to for easy future reference and to be used in skins (for easy access only)
        
        libraryPath = xbmc.translatePath("special://profile/library/video/Emby - %s/" %tagname)
        
        #create tag node - index
        xbmcvfs.mkdir(libraryPath)
        nodefile = os.path.join(libraryPath, "index.xml")
        root = Element("node", {"order":"0"})
        SubElement(root, "label").text = "Emby - " + tagname
        SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
        path = "library://video/Emby - %s/"%tagname
        WINDOW.setProperty("Emby.nodes.%s.index" %str(windowPropId),path)
        try:
            ET.ElementTree(root).write(nodefile, xml_declaration=True)
        except:
            ET.ElementTree(root).write(nodefile)
        
        #create tag node - all items
        nodefile = os.path.join(libraryPath, tagname + "_all.xml")
        root = Element("node", {"order":"1", "type":"filter"})
        SubElement(root, "label").text = tagname
        SubElement(root, "match").text = "all"
        SubElement(root, "content").text = type
        SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
        SubElement(root, "order", {"direction":"ascending"}).text = "sorttitle"
        Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
        WINDOW.setProperty("Emby.nodes.%s.title" %str(windowPropId),tagname)
        path = "library://video/Emby - %s/%s_all.xml"%(tagname,tagname)
        WINDOW.setProperty("Emby.nodes.%s.path" %str(windowPropId),"ActivateWindow(Video,%s,return)"%path)
        WINDOW.setProperty("Emby.nodes.%s.content" %str(windowPropId),path)
        WINDOW.setProperty("Emby.nodes.%s.type" %str(windowPropId),type)
        SubElement(Rule, "value").text = tagname
        try:
            ET.ElementTree(root).write(nodefile, xml_declaration=True)
        except:
            ET.ElementTree(root).write(nodefile)
        
        #create tag node - recent items
        nodefile = os.path.join(libraryPath, tagname + "_recent.xml")
        root = Element("node", {"order":"2", "type":"filter"})
        if type == "tvshows":
            label = tagname + " - " + language(30170)
        else:
            label = tagname + " - " + language(30174)
        SubElement(root, "label").text = label
        SubElement(root, "match").text = "all"
        SubElement(root, "content").text = type
        SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
        Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
        SubElement(Rule, "value").text = tagname
        SubElement(root, "order", {"direction":"descending"}).text = "dateadded"
        #set limit to 25 --> currently hardcoded --> TODO: add a setting for this ?
        SubElement(root, "limit").text = "25"
        #exclude watched items --> currently hardcoded --> TODO: add a setting for this ?
        Rule2 = SubElement(root, "rule", {"field":"playcount","operator":"is"})
        SubElement(Rule2, "value").text = "0"
        WINDOW.setProperty("Emby.nodes.%s.recent.title" %str(windowPropId),label)
        path = "library://video/Emby - %s/%s_recent.xml"%(tagname,tagname)
        WINDOW.setProperty("Emby.nodes.%s.recent.path" %str(windowPropId),"ActivateWindow(Video,%s,return)"%path)
        WINDOW.setProperty("Emby.nodes.%s.recent.content" %str(windowPropId),path)
        try:
            ET.ElementTree(root).write(nodefile, xml_declaration=True)
        except:
            ET.ElementTree(root).write(nodefile)
        
        #create tag node - inprogress items
        nodefile = os.path.join(libraryPath, tagname + "_progress.xml")
        root = Element("node", {"order":"3", "type":"filter"})
        if type == "tvshows":
            label = tagname + " - " + language(30171)
        else:
            label = tagname + " - " + language(30177)
        SubElement(root, "label").text = label
        SubElement(root, "match").text = "all"
        SubElement(root, "content").text = type
        SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
        Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
        SubElement(Rule, "value").text = tagname
        #set limit to 25 --> currently hardcoded --> TODO: add a setting for this ?
        SubElement(root, "limit").text = "25"
        Rule2 = SubElement(root, "rule", {"field":"inprogress","operator":"true"})
        WINDOW.setProperty("Emby.nodes.%s.inprogress.title" %str(windowPropId),label)
        path = "library://video/Emby - %s/%s_progress.xml"%(tagname,tagname)
        WINDOW.setProperty("Emby.nodes.%s.inprogress.path" %str(windowPropId),"ActivateWindow(Video,%s,return)"%path)
        WINDOW.setProperty("Emby.nodes.%s.inprogress.content" %str(windowPropId),path)
        try:
            ET.ElementTree(root).write(nodefile, xml_declaration=True)
        except:
            ET.ElementTree(root).write(nodefile)
        
        #create tag node - add unwatched movies node for movies
        if type == "movies":
            nodefile = os.path.join(libraryPath, tagname + "_unwatched.xml")
            root = Element("node", {"order":"4", "type":"filter"})
            label = tagname + " - " + language(30189)
            SubElement(root, "label").text = label
            SubElement(root, "match").text = "all"
            SubElement(root, "content").text = "movies"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
            SubElement(Rule, "value").text = tagname
            Rule = SubElement(root, "rule", {"field":"playcount","operator":"is"})
            SubElement(Rule, "value").text = "0"
            SubElement(root, "order", {"direction":"ascending"}).text = "sorttitle"
            #set limit to 25 --> currently hardcoded --> TODO: add a setting for this ?
            SubElement(root, "limit").text = "25"
            #exclude watched items --> currently hardcoded --> TODO: add a setting for this ?
            Rule2 = SubElement(root, "rule", {"field":"playcount","operator":"is"})
            SubElement(Rule2, "value").text = "0"
            WINDOW.setProperty("Emby.nodes.%s.unwatched.title" %str(windowPropId),label)
            path = "library://video/Emby - %s/%s_unwatched.xml"%(tagname,tagname)
            WINDOW.setProperty("Emby.nodes.%s.unwatched.path" %str(windowPropId),"ActivateWindow(Video,%s,return)"%path)
            WINDOW.setProperty("Emby.nodes.%s.unwatched.content" %str(windowPropId),path)
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
                              
        
        #add some additional nodes for episodes
        if type == "tvshows":
            #create tag node - recent episodes
            nodefile = os.path.join(libraryPath, tagname + "_recent_episodes.xml")
            root = Element("node", {"order":"3", "type":"filter"})
            label = tagname + " - " + language(30175)
            SubElement(root, "label").text = label
            SubElement(root, "match").text = "all"
            SubElement(root, "content").text = "episodes"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
            SubElement(Rule, "value").text = tagname
            SubElement(root, "order", {"direction":"descending"}).text = "dateadded"
            #set limit to 25 --> currently hardcoded --> TODO: add a setting for this ?
            SubElement(root, "limit").text = "25"
            #exclude watched items --> currently hardcoded --> TODO: add a setting for this ?
            Rule2 = SubElement(root, "rule", {"field":"playcount","operator":"is"})
            SubElement(Rule2, "value").text = "0"
            WINDOW.setProperty("Emby.nodes.%s.recentepisodes.title" %str(windowPropId),label)
            path = "library://video/Emby - %s/%s_recent_episodes.xml"%(tagname,tagname)
            WINDOW.setProperty("Emby.nodes.%s.recentepisodes.path" %str(windowPropId),"ActivateWindow(Video,%s,return)"%path)
            WINDOW.setProperty("Emby.nodes.%s.recentepisodes.content" %str(windowPropId),path)
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
            
            #create tag node - inprogress items
            nodefile = os.path.join(libraryPath, tagname + "_progress_episodes.xml")
            root = Element("node", {"order":"4", "type":"filter"})
            label = tagname + " - " + language(30178)
            SubElement(root, "label").text = label
            SubElement(root, "match").text = "all"
            SubElement(root, "content").text = "episodes"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
            SubElement(Rule, "value").text = tagname
            #set limit to 25 --> currently hardcoded --> TODO: add a setting for this ?
            SubElement(root, "limit").text = "25"
            Rule2 = SubElement(root, "rule", {"field":"inprogress","operator":"true"})
            WINDOW.setProperty("Emby.nodes.%s.inprogressepisodes.title" %str(windowPropId),label)
            path = "library://video/Emby - %s/%s_progress_episodes.xml"%(tagname,tagname)
            WINDOW.setProperty("Emby.nodes.%s.inprogressepisodes.path" %str(windowPropId),"ActivateWindow(Video,%s,return)"%path)
            WINDOW.setProperty("Emby.nodes.%s.inprogressepisodes.content" %str(windowPropId),path)
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
                
            #create tag node - nextup items
            nodefile = os.path.join(libraryPath, tagname + "_nextup_episodes.xml")
            root = Element("node", {"order":"4", "type":"folder"})
            label = tagname + " - " + language(30179)
            SubElement(root, "label").text = label
            SubElement(root, "content").text = "episodes"
            path = "plugin://plugin.video.emby/?id=%s&mode=nextup&limit=25" %tagname
            SubElement(root, "path").text = path
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            WINDOW.setProperty("Emby.nodes.%s.nextepisodes.title" %str(windowPropId),label)
            path = "library://video/Emby - %s/%s_nextup_episodes.xml"%(tagname,tagname)
            WINDOW.setProperty("Emby.nodes.%s.nextepisodes.path" %str(windowPropId),"ActivateWindow(Video,%s,return)"%path)
            WINDOW.setProperty("Emby.nodes.%s.nextepisodes.content" %str(windowPropId),path)        
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
    
    def buildVideoNodesListing(self):
            
        try:
        
            # the library path doesn't exist on all systems
            if not xbmcvfs.exists("special://profile/library/"):
                xbmcvfs.mkdir("special://profile/library") 
            if not xbmcvfs.exists("special://profile/library/video/"):
                #we need to copy over the default items
                shutil.copytree(xbmc.translatePath("special://xbmc/system/library/video"), xbmc.translatePath("special://profile/library/video"))
            
            #always cleanup existing Emby video nodes first because we don't want old stuff to stay in there
            path = "special://profile/library/video/"
            if xbmcvfs.exists(path):
                allDirs, allFiles = xbmcvfs.listdir(path)
                for dir in allDirs:
                    if dir.startswith("Emby "):
                        shutil.rmtree(xbmc.translatePath("special://profile/library/video/" + dir))
                for file in allFiles:
                    if file.startswith("emby"):
                        xbmcvfs.delete(path + file)
            
            #we build up a listing and set window props for all nodes we created
            #the window props will be used by the main entry point to quickly build up the listing and can be used in skins (like titan) too for quick reference
            #comment marcelveldt: please leave the window props as-is because I will be referencing them in titan skin...
            totalNodesCount = 0
            
            #build the listing for all views
            views_movies = ReadEmbyDB().getCollections("movies")
            if views_movies:
                for view in views_movies:
                    self.buildVideoNodeForView(view.get('title'), "movies", totalNodesCount)
                    totalNodesCount +=1
                    
            views_shows = ReadEmbyDB().getCollections("tvshows")
            if views_shows:
                for view in views_shows:
                    self.buildVideoNodeForView(view.get('title'), "tvshows", totalNodesCount)
                    totalNodesCount +=1

            #create tag node for emby channels
            nodefile = os.path.join(xbmc.translatePath("special://profile/library/video"), "emby_channels.xml")
            root = Element("node", {"order":"1", "type":"folder"})
            label = "Emby  - " + language(30173)
            SubElement(root, "label").text = label
            SubElement(root, "content").text = "movies"
            SubElement(root, "path").text = "plugin://plugin.video.emby/?id=0&mode=channels"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            WINDOW.setProperty("Emby.nodes.%s.title" %str(totalNodesCount),label)
            WINDOW.setProperty("Emby.nodes.%s.type" %str(totalNodesCount),"channels")
            path = "library://video/emby_channels.xml"
            WINDOW.setProperty("Emby.nodes.%s.path" %str(totalNodesCount),"ActivateWindow(Video,%s,return)"%path)
            WINDOW.setProperty("Emby.nodes.%s.content" %str(totalNodesCount),path)
            totalNodesCount +=1        
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
                   
            #create tag node - favorite shows
            nodefile = os.path.join(xbmc.translatePath("special://profile/library/video"),"emby_favorite_shows.xml")
            root = Element("node", {"order":"1", "type":"filter"})
            label = "Emby - " + language(30181)
            SubElement(root, "label").text = label
            SubElement(root, "match").text = "all"
            SubElement(root, "content").text = "tvshows"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            SubElement(root, "order", {"direction":"ascending"}).text = "sorttitle"
            Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
            SubElement(Rule, "value").text = "Favorite tvshows" #do not localize the tagname itself
            WINDOW.setProperty("Emby.nodes.%s.title" %str(totalNodesCount),label)
            WINDOW.setProperty("Emby.nodes.%s.type" %str(totalNodesCount),"favourites")
            path = "library://video/emby_favorite_shows.xml"
            WINDOW.setProperty("Emby.nodes.%s.path" %str(totalNodesCount),"ActivateWindow(Video,%s,return)"%path)
            WINDOW.setProperty("Emby.nodes.%s.content" %str(totalNodesCount),path)
            totalNodesCount +=1
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
            
            #create tag node - favorite movies
            nodefile = os.path.join(xbmc.translatePath("special://profile/library/video"),"emby_favorite_movies.xml")
            root = Element("node", {"order":"1", "type":"filter"})
            label = "Emby - " + language(30180)
            SubElement(root, "label").text = label
            SubElement(root, "match").text = "all"
            SubElement(root, "content").text = "movies"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            SubElement(root, "order", {"direction":"ascending"}).text = "sorttitle"
            Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
            SubElement(Rule, "value").text = "Favorite movies" #do not localize the tagname itself
            WINDOW.setProperty("Emby.nodes.%s.title" %str(totalNodesCount),label)
            WINDOW.setProperty("Emby.nodes.%s.type" %str(totalNodesCount),"favourites")
            path = "library://video/emby_favorite_movies.xml"
            WINDOW.setProperty("Emby.nodes.%s.path" %str(totalNodesCount),"ActivateWindow(Video,%s,return)"%path)
            WINDOW.setProperty("Emby.nodes.%s.content" %str(totalNodesCount),path)
            totalNodesCount +=1
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
            
            WINDOW.setProperty("Emby.nodes.total", str(totalNodesCount))               
                
        except Exception as e:
            utils.logMsg("Emby addon","Error while creating videonodes listings, restart required ?")
            print e
        