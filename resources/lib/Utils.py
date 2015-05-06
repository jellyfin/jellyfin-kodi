#################################################################################################
# utils 
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import os
import cProfile
import pstats
import time
import inspect
import sqlite3
import string
import unicodedata
from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.etree import ElementTree
from xml.dom import minidom
import xml.etree.cElementTree as ET

from API import API
from PlayUtils import PlayUtils
from DownloadUtils import DownloadUtils
downloadUtils = DownloadUtils()
addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
language = addonSettings.getLocalizedString

 
def logMsg(title, msg, level = 1):
    logLevel = int(addonSettings.getSetting("logLevel"))
    WINDOW = xbmcgui.Window(10000)
    WINDOW.setProperty('logLevel', str(logLevel))
    if(logLevel >= level):
        if(logLevel == 2): # inspect.stack() is expensive
            try:
                xbmc.log(title + " -> " + inspect.stack()[1][3] + " : " + str(msg))
            except UnicodeEncodeError:
                xbmc.log(title + " -> " + inspect.stack()[1][3] + " : " + str(msg.encode('utf-8')))
        else:
            try:
                xbmc.log(title + " -> " + str(msg))
            except UnicodeEncodeError:
                xbmc.log(title + " -> " + str(msg.encode('utf-8')))

def convertEncoding(data):
    #nasty hack to make sure we have a unicode string
    try:
        return data.decode('utf-8')
    except:
        return data
          
def KodiSQL():
    connection = sqlite3.connect(getKodiDBPath())
    
    return connection

def getKodiDBPath():
    if xbmc.getInfoLabel("System.BuildVersion").startswith("13"):
        #gotham
        dbVersion = "78"
    if xbmc.getInfoLabel("System.BuildVersion").startswith("15"):
        #isengard
        dbVersion = "92"
    else: 
        #helix
        dbVersion = "90"
    
    dbPath = xbmc.translatePath("special://profile/Database/MyVideos" + dbVersion + ".db")
    
    return dbPath  

def checkAuthentication():
    #check authentication
    if addonSettings.getSetting('username') != "" and addonSettings.getSetting('ipaddress') != "":
        try:
            downloadUtils.authenticate()
        except Exception, e:
            logMsg("Emby authentication failed",e)
            pass
    
def prettifyXml(elem):
    rough_string = etree.tostring(elem, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="\t")        
    
def get_params( paramstring ):
    xbmc.log("Parameter string: " + paramstring)
    param={}
    if len(paramstring)>=2:
        params=paramstring

        if params[0] == "?":
            cleanedparams=params[1:]
        else:
            cleanedparams=params

        if (params[len(params)-1]=='/'):
                params=params[0:len(params)-2]

        pairsofparams=cleanedparams.split('&')
        for i in range(len(pairsofparams)):
                splitparams={}
                splitparams=pairsofparams[i].split('=')
                if (len(splitparams))==2:
                        param[splitparams[0]]=splitparams[1]
                elif (len(splitparams))==3:
                        param[splitparams[0]]=splitparams[1]+"="+splitparams[2]
    return param

def startProfiling():
    pr = cProfile.Profile()
    pr.enable()
    return pr
    
def stopProfiling(pr, profileName):
    pr.disable()
    ps = pstats.Stats(pr)
    
    addondir = xbmc.translatePath(xbmcaddon.Addon(id='plugin.video.emby').getAddonInfo('profile'))    
    
    fileTimeStamp = time.strftime("%Y-%m-%d %H-%M-%S")
    tabFileNamepath = os.path.join(addondir, "profiles")
    tabFileName = os.path.join(addondir, "profiles" , profileName + "_profile_(" + fileTimeStamp + ").tab")
    
    if not xbmcvfs.exists(tabFileNamepath):
        xbmcvfs.mkdir(tabFileNamepath)
    
    f = open(tabFileName, 'wb')
    f.write("NumbCalls\tTotalTime\tCumulativeTime\tFunctionName\tFileName\r\n")
    for (key, value) in ps.stats.items():
        (filename, count, func_name) = key
        (ccalls, ncalls, total_time, cumulative_time, callers) = value
        try:
            f.write(str(ncalls) + "\t" + "{:10.4f}".format(total_time) + "\t" + "{:10.4f}".format(cumulative_time) + "\t" + func_name + "\t" + filename + "\r\n")
        except ValueError:
            f.write(str(ncalls) + "\t" + "{0}".format(total_time) + "\t" + "{0}".format(cumulative_time) + "\t" + func_name + "\t" + filename + "\r\n")
    f.close()

def CleanName(filename):
    validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
    return ''.join(c for c in cleanedFilename if c in validFilenameChars)
   
        
def reset():

    return_value = xbmcgui.Dialog().yesno("Warning", "Are you sure you want to reset your local Kodi database?")

    if return_value == 0:
        return

    #cleanup video nodes
    import shutil
    path = "special://profile/library/video/"
    if xbmcvfs.exists(path):
        allDirs, allFiles = xbmcvfs.listdir(path)
        for dir in allDirs:
            if dir.startswith("Emby "):
                shutil.rmtree(xbmc.translatePath("special://profile/library/video/" + dir))
        for file in allFiles:
                if file.startswith("emby"):
                    xbmcvfs.delete(path + file)
    
    # Ask if user information should be deleted too.
    return_user = xbmcgui.Dialog().yesno("Warning", "Reset all Emby Addon settings?")

    delete_settings = False
    if return_user == 1:
        delete_settings = True
    
    # first stop any db sync
    WINDOW = xbmcgui.Window( 10000 )
    WINDOW.setProperty("SyncDatabaseShouldStop", "true")
    
    count = 0
    while(WINDOW.getProperty("SyncDatabaseRunning") == "true"):
        xbmc.log("Sync Running, will wait : " + str(count))
        count += 1
        if(count > 10):
            dialog = xbmcgui.Dialog()
            dialog.ok('Warning', 'Could not stop DB sync, you should try again.')
            return
        xbmc.sleep(1000)
       
    # delete db table data
    print "Doing DB Reset"
    connection = KodiSQL()
    cursor = connection.cursor( )
    cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
    rows = cursor.fetchall()
    for row in rows:
        tableName = row[0]
        print tableName
        if(tableName != "version"):
            cursor.execute("DELETE FROM " + tableName)
    connection.commit()
    cursor.close()
    
    # reset the install run flag
    WINDOW.setProperty("SyncInstallRunDone", "false")

    if (delete_settings == True):
        addondir = xbmc.translatePath(addonSettings.getAddonInfo('profile'))
        dataPath = os.path.join(addondir + "settings.xml")
        xbmcvfs.delete(dataPath)
        xbmc.log("Deleting : settings.xml")

    dialog = xbmcgui.Dialog()
    dialog.ok('Emby Reset', 'Database reset has completed, Kodi will now restart to apply the changes.')
    xbmc.executebuiltin("RestartApp")


def buildVideoNodeForView(tagname, type):
    #this method will build a video node for a particular Emby view (= tag in kodi)
    
    libraryPath = xbmc.translatePath("special://profile/library/video/Emby - %s/" %tagname)
    
    if not xbmcvfs.exists(libraryPath):
        #create tag node - index
        xbmcvfs.mkdir(libraryPath)
        nodefile = os.path.join(libraryPath, "index.xml")
        root = Element("node", {"order":"1"})
        SubElement(root, "label").text = "Emby - " + tagname
        SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
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
        SubElement(Rule, "value").text = tagname
        try:
            ET.ElementTree(root).write(nodefile, xml_declaration=True)
        except:
            ET.ElementTree(root).write(nodefile)
        
        #create tag node - recent items
        nodefile = os.path.join(libraryPath, tagname + "_recent.xml")
        root = Element("node", {"order":"2", "type":"filter"})
        if type == "tvshows":
            SubElement(root, "label").text = tagname + " - " + language(30170)
        else:
            SubElement(root, "label").text = tagname + " - " + language(30174)
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
        
        try:
            ET.ElementTree(root).write(nodefile, xml_declaration=True)
        except:
            ET.ElementTree(root).write(nodefile)
        
        #create tag node - inprogress items
        nodefile = os.path.join(libraryPath, tagname + "_progress.xml")
        root = Element("node", {"order":"3", "type":"filter"})
        if type == "tvshows":
            SubElement(root, "label").text = tagname + " - " + language(30171)
        else:
            SubElement(root, "label").text = tagname + " - " + language(30177)
        SubElement(root, "match").text = "all"
        SubElement(root, "content").text = type
        SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
        Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
        SubElement(Rule, "value").text = tagname
        #set limit to 25 --> currently hardcoded --> TODO: add a setting for this ?
        SubElement(root, "limit").text = "25"
        Rule2 = SubElement(root, "rule", {"field":"inprogress","operator":"true"})
        
        try:
            ET.ElementTree(root).write(nodefile, xml_declaration=True)
        except:
            ET.ElementTree(root).write(nodefile)
        
        #create tag node - add unwatched movies node for movies
        if type == "movies":
            nodefile = os.path.join(libraryPath, tagname + "_unwatched.xml")
            root = Element("node", {"order":"4", "type":"filter"})
            SubElement(root, "label").text = tagname + " - " + language(30189)
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
            
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
                              
        
        #add some additional nodes for episodes
        if type == "tvshows":
            #create tag node - recent episodes
            nodefile = os.path.join(libraryPath, tagname + "_recent_episodes.xml")
            root = Element("node", {"order":"3", "type":"filter"})
            SubElement(root, "label").text = tagname + " - " + language(30175)
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
            
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
            
            #create tag node - inprogress items
            nodefile = os.path.join(libraryPath, tagname + "_progress_episodes.xml")
            root = Element("node", {"order":"4", "type":"filter"})
            SubElement(root, "label").text = tagname + " - " + language(30178)
            SubElement(root, "match").text = "all"
            SubElement(root, "content").text = "episodes"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
            SubElement(Rule, "value").text = tagname
            #set limit to 25 --> currently hardcoded --> TODO: add a setting for this ?
            SubElement(root, "limit").text = "25"
            Rule2 = SubElement(root, "rule", {"field":"inprogress","operator":"true"})
            
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
                
            #create tag node - nextup items
            nodefile = os.path.join(libraryPath, tagname + "_nextup_episodes.xml")
            root = Element("node", {"order":"4", "type":"folder"})
            SubElement(root, "label").text = tagname + " - " + language(30179)
            SubElement(root, "content").text = "episodes"
            SubElement(root, "path").text = "plugin://plugin.video.emby/?id=%s&mode=nextup&limit=25" %tagname
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"             
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
    
def buildVideoNodesListing():
        
    import shutil
    from ReadEmbyDB import ReadEmbyDB
    
    try:
    
        # the library path doesn't exist on all systems
        if not xbmcvfs.exists("special://profile/library/"):
            xbmcvfs.mkdir("special://profile/library") 
        if not xbmcvfs.exists("special://profile/library/video/"):
            #we need to copy over the default items
            import shutil
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
        
        #create tag node for emby channels
        nodefile = os.path.join(xbmc.translatePath("special://profile/library/video"), "emby_channels.xml")
        if not xbmcvfs.exists(nodefile):
            root = Element("node", {"order":"1", "type":"folder"})
            SubElement(root, "label").text = "Emby  - " + language(30173)
            SubElement(root, "content").text = "movies"
            SubElement(root, "path").text = "plugin://plugin.video.emby/?id=0&mode=channels"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"               
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
               
        #create tag node - favorite shows
        nodefile = os.path.join(xbmc.translatePath("special://profile/library/video"),"emby_favorite_shows.xml")
        if not xbmcvfs.exists(nodefile):
            root = Element("node", {"order":"1", "type":"filter"})
            SubElement(root, "label").text = "Emby - " + language(30181)
            SubElement(root, "match").text = "all"
            SubElement(root, "content").text = "tvshows"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            SubElement(root, "order", {"direction":"ascending"}).text = "sorttitle"
            Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
            SubElement(Rule, "value").text = "Favorite tvshows" #do not localize the tagname itself
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
        
        #create tag node - favorite movies
        nodefile = os.path.join(xbmc.translatePath("special://profile/library/video"),"emby_favorite_movies.xml")
        if not xbmcvfs.exists(nodefile):
            root = Element("node", {"order":"1", "type":"filter"})
            SubElement(root, "label").text = "Emby - " + language(30180)
            SubElement(root, "match").text = "all"
            SubElement(root, "content").text = "movies"
            SubElement(root, "icon").text = "special://home/addons/plugin.video.emby/icon.png"
            SubElement(root, "order", {"direction":"ascending"}).text = "sorttitle"
            Rule = SubElement(root, "rule", {"field":"tag","operator":"is"})
            SubElement(Rule, "value").text = "Favorite movies" #do not localize the tagname itself
            try:
                ET.ElementTree(root).write(nodefile, xml_declaration=True)
            except:
                ET.ElementTree(root).write(nodefile)
        
        #build the listing for all views
        views_movies = ReadEmbyDB().getCollections("movies")
        if views_movies:
            for view in views_movies:
                buildVideoNodeForView(view.get('title'), "movies")
                
        views_shows = ReadEmbyDB().getCollections("tvshows")
        if views_shows:
            for view in views_shows:
                buildVideoNodeForView(view.get('title'), "tvshows")        
            
    except:
        logMsg("Emby addon","Error while creating videonodes listings, restart required ?")
            