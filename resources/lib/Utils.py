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
        dbVersion = "91"
    else: 
        #helix
        dbVersion = "90"
    
    dbPath = xbmc.translatePath("special://userdata/Database/MyVideos" + dbVersion + ".db")
    
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
   

def removeDirectory(path):
    if xbmcvfs.exists(path):
        allDirs, allFiles = xbmcvfs.listdir(path)
        for dir in allDirs:
            xbmcvfs.rmdir(os.path.join(path,dir))
        for file in allFiles:
            xbmcvfs.delete(os.path.join(path,file))
        
        xbmcvfs.rmdir(path)
        
def reset():

    return_value = xbmcgui.Dialog().yesno("Warning", "Are you sure you want to reset your local database?")
    if return_value == 0:
        return
    
    # first stop any db sync
    WINDOW = xbmcgui.Window( 10000 )
    WINDOW.setProperty("SyncDatabaseShouldStop", "true")
    
    count = 0
    while(WINDOW.getProperty("SyncDatabaseRunning") == "true"):
        count += 1
        if(count > 10):
            dialog = xbmcgui.Dialog()
            dialog.ok('Warning', 'Could not stop DB sync, you should try again.')
            return
        xbmc.sleep(1000)
    
    # delete db
    deletecount = 0
    deleted = False
    while(deleted == False):
        try:
            xbmcvfs.delete(getKodiDBPath())
            deleted = True
        except:
            deletecount += 1
            if(deletecount > 10):
                dialog = xbmcgui.Dialog()
                dialog.ok('Warning', 'Could not delete Database, please try again later')
                return
            xbmc.sleep(1000)
    
    # remove from addon data directory
    addon = xbmcaddon.Addon(id='plugin.video.emby')
    addondir = xbmc.translatePath(addon.getAddonInfo('profile'))
    dataPath = os.path.join(addondir + os.sep)
    removeDirectory(dataPath)
    
    # remove old entries from sources.xml
    
    dialog = xbmcgui.Dialog()
    dialog.ok('Emby Reset', 'Reset of Emby has completed, kodi will now restart to apply the changes.')
    xbmc.executebuiltin("RestartApp")
     
