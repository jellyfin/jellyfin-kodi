#################################################################################################
# utils 
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import os

import sqlite3
import inspect
from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.etree import ElementTree
from xml.dom import minidom
import xml.etree.cElementTree as ET

from API import API
from PlayUtils import PlayUtils
from DownloadUtils import DownloadUtils
downloadUtils = DownloadUtils()
addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
language = addonSettings.getLocalizedString   
 
def logMsg(title, msg, level = 1):
    
    #todo --> get this from a setting
    logLevel = 1
    
    if(logLevel >= level):
        if(logLevel == 1):
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
    addon       = xbmcaddon.Addon(id='plugin.video.mb3sync')
    addondir   = xbmc.translatePath( addon.getAddonInfo('profile') )
    dataPath = os.path.join(addondir,"library")
    movieLibrary        = os.path.join(dataPath,'movies')
    tvLibrary           = os.path.join(dataPath,'tvshows')
    
    rebootRequired = False
    if not xbmcvfs.exists(dataPath + os.sep):
        xbmcvfs.mkdir(dataPath)
    if not xbmcvfs.exists(movieLibrary + os.sep):
        xbmcvfs.mkdir(movieLibrary)
        rebootRequired = addKodiSource("mediabrowser_movies",movieLibrary,"movies")
    if not xbmcvfs.exists(tvLibrary + os.sep):
        xbmcvfs.mkdir(tvLibrary)
        rebootRequired = addKodiSource("mediabrowser_tvshows",tvLibrary,"tvshows")
       
    if rebootRequired:
        ret = xbmcgui.Dialog().yesno(heading="MediaBrowser Sync service", line1="A restart of Kodi is needed to apply changes. After the reboot you need to manually assign the MediaBrowser sources to your library. See documentation. Do you want to reboot now ?")
        if ret:
            xbmc.executebuiltin("RestartApp")
        
def addKodiSource(name, path, type):
    #add new source to database, common way is to add it directly to the Kodi DB. Fallback to adding it to the sources.xml
    #return boolean wether a manual reboot is required.
    #todo: Do feature request with Kodi team to get support for adding a source by the json API
    dbPath = xbmc.translatePath("special://userdata/Database/MyVideos90.db")
    
    error = False
    if xbmcvfs.exists(dbPath):
        try:
            connection = sqlite3.connect(dbPath)
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
    else:
        error = True
    
    # add it to sources.xml
    sourcesFile = xbmc.translatePath( "special://profile/sources.xml" )
    
    # add an emply sources file to work with
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
        #return bool that reboot is needed and manual add of path to kodi
        return KodiAdvancedSettingsCheck()
       
def KodiAdvancedSettingsCheck():
    #setting that kodi should import watched state and resume points from the nfo files
    settingsFile = xbmc.translatePath( "special://profile/advancedsettings.xml" )
    # add an empty sources file to work with
    if xbmcvfs.exists(settingsFile) == False:
        sources = Element("advancedsettings")
        video = SubElement(sources, "videolibrary")
        ET.ElementTree(sources).write(settingsFile)
    
    if xbmcvfs.exists(settingsFile):
        tree = ET.ElementTree(file=settingsFile)
        root = tree.getroot()
        video = root.find("videolibrary")
        if video == None:
            video = SubElement(sources, "videolibrary")
        # add the settings
        SubElement(video, "importwatchedstate").text = "true"
        SubElement(video, "importresumepoint").text = "true"
        tree.write(settingsFile)
        #return bool that reboot is needed and manual add of path to kodi
        return True
       
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
    
def doKodiCleanup():
    #remove old testdata and remove missing files
    json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"properties" : ["file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libMovies"}')
    jsonobject = json.loads(json_response.decode('utf-8','replace'))  
    if(jsonobject.has_key('result')):
        result = jsonobject['result']
        if(result.has_key('movies')):
            movies = result['movies']
            for movie in movies:
                if (xbmcvfs.exists(movie["file"]) == False) or ("plugin.video.xbmb3c" in movie["file"]):
                    xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.RemoveMovie", "params": { "movieid": %i}, "id": 1 }' %(movie["movieid"]))
   
    
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

 