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
          

def checkKodiSources():
    addon       = xbmcaddon.Addon(id='plugin.video.emby')
    addondir   = xbmc.translatePath( addon.getAddonInfo('profile') )
    dataPath = os.path.join(addondir,"library")
    movieLibrary        = os.path.join(dataPath,'movies')
    tvLibrary           = os.path.join(dataPath,'tvshows')
    musicvideoLibrary = os.path.join(dataPath,'musicvideos')
    
    # If no folder exists at the time, create it.
    if xbmcvfs.exists(addondir) == False:
        xbmcvfs.mkdir(addondir)
        xbmc.log("Manually created %s" % addondir)
    
    if not xbmcvfs.exists(dataPath + os.sep):
        xbmcvfs.mkdir(dataPath)
    if not xbmcvfs.exists(movieLibrary + os.sep):
        xbmcvfs.mkdir(movieLibrary)
        addKodiSource("mediabrowser_movies",movieLibrary,"movies")
    if not xbmcvfs.exists(tvLibrary + os.sep):
        xbmcvfs.mkdir(tvLibrary)
        addKodiSource("mediabrowser_tvshows",tvLibrary,"tvshows")
    if not xbmcvfs.exists(musicvideoLibrary + os.sep):
        xbmcvfs.mkdir(musicvideoLibrary)
        addKodiSource("mediabrowser_musicvideos",musicvideoLibrary,"musicvideos")
    
    KodiAdvancedSettingsCheck()
    
    return True
    
    ''' To be deleted once fully tested - Angel
    rebootRequired = False
    
    if not xbmcvfs.exists(dataPath + os.sep):
        xbmcvfs.mkdir(dataPath)
    if not xbmcvfs.exists(movieLibrary + os.sep):
        xbmcvfs.mkdir(movieLibrary)
        rebootRequired = True
        addKodiSource("mediabrowser_movies",movieLibrary,"movies")
    if not xbmcvfs.exists(tvLibrary + os.sep):
        xbmcvfs.mkdir(tvLibrary)
        rebootRequired = True
        addKodiSource("mediabrowser_tvshows",tvLibrary,"tvshows")
    if not xbmcvfs.exists(musicvideoLibrary + os.sep):
        xbmcvfs.mkdir(musicvideoLibrary)
        rebootRequired = True
        addKodiSource("mediabrowser_musicvideos",musicvideoLibrary,"musicvideos")
    
    rebootRequired = KodiAdvancedSettingsCheck()
    
    if rebootRequired:
        ret = xbmcgui.Dialog().yesno(heading="Emby Sync service", line1="A restart of Kodi is needed to apply changes.", line2="Synchronisation will not start before the restart.", line3="Do you want to restart now?")
        if ret:
            xbmc.executebuiltin("RestartApp")
        else:
            return False
    
    return True'''

def KodiSQL():
    if xbmc.getInfoLabel("System.BuildVersion").startswith("13"):
        #gotham
        dbVersion = "78"
    if xbmc.getInfoLabel("System.BuildVersion").startswith("15"):
        #isengard
        dbVersion = "91"
    else: 
        #helix
        dbVersion = "90"
    
    dbPath = xbmc.translatePath("special://userdata/Database/MyVideos" + dbVersion + ".db")
    connection = sqlite3.connect(dbPath)

    return connection
        
        
def addKodiSource(name, path, type):
    #add new source to database, common way is to add it directly to the Kodi DB. Fallback to adding it to the sources.xml
    #return boolean wether a manual reboot is required.
    #todo: Do feature request with Kodi team to get support for adding a source by the json API
    
    error = False
    try:
        connection = KodiSQL()
        cursor = connection.cursor( )
        cursor.execute("select coalesce(max(idPath),0) as pathId from path")
        pathId =  cursor.fetchone()[0]
        pathId = pathId + 1
        pathsql="insert into path(idPath, strPath, strContent, strScraper, strHash, scanRecursive) values(?, ?, ?, ?, ?, ?)"
        cursor.execute(pathsql, (pathId,path + os.sep,type,"metadata.local",None,2147483647))
        connection.commit()
        cursor.close()
    except:
        error = True

    # add it to sources.xml
    sourcesFile = xbmc.translatePath( "special://profile/sources.xml" )
    
    # add an empty sources file to work with
    if xbmcvfs.exists(sourcesFile) == False:
        sources = Element("sources")
        video = SubElement(sources, "video")
        ET.ElementTree(sources).write(sourcesFile)
    
    if xbmcvfs.exists(sourcesFile):
        tree = ET.ElementTree(file=sourcesFile)
        root = tree.getroot()
        videosources = root.find("video")
        #remove any existing entries for this path
        allsources = videosources.findall("source")
        if allsources != None:
            for source in allsources:
                if source.find("name").text == name:
                    videosources.remove(source)
        # add the new source
        source = SubElement(videosources,'source')
        SubElement(source, "name").text = name
        SubElement(source, "path").text = path
        tree.write(sourcesFile)
       
def KodiAdvancedSettingsCheck():
    #setting that kodi should import watched state and resume points from the nfo files
    settingsFile = xbmc.translatePath( "special://profile/advancedsettings.xml" )
    # add an empty sources file to work with
    if xbmcvfs.exists(settingsFile) == False:
        sources = Element("advancedsettings")
        video = SubElement(sources, "videolibrary")
        ET.ElementTree(sources).write(settingsFile)
    
    writeNeeded = False
    if xbmcvfs.exists(settingsFile):
        tree = ET.ElementTree(file=settingsFile)
        root = tree.getroot()
        video = root.find("videolibrary")
        if video == None:
            video = SubElement(root, "videolibrary")
        # add the settings
        if video.find("importwatchedstate") == None:
            writeNeeded = True
            SubElement(video, "importwatchedstate").text = "true"
        if video.find("importresumepoint") == None:
            writeNeeded = True
            SubElement(video, "importresumepoint").text = "true"
        
        if writeNeeded:
            tree.write(settingsFile)
            return True
        else:
            return False
       
def checkAuthentication():
    #check authentication
    if addonSettings.getSetting('username') != "" and addonSettings.getSetting('ipaddress') != "":
        try:
            downloadUtils.authenticate()
        except Exception, e:
            logMsg("MB3 Syncer authentication failed",e)
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


   
 
