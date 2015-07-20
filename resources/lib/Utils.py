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


from API import API
from PlayUtils import PlayUtils
from DownloadUtils import DownloadUtils
downloadUtils = DownloadUtils()
addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
language = addonSettings.getLocalizedString

 
def logMsg(title, msg, level = 1):
    
    WINDOW = xbmcgui.Window(10000)
    # Get the logLevel set in UserClient
    logLevel = int(WINDOW.getProperty('getLogLevel'))
    
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
          
def KodiSQL(type="video"):
    
    if type == "music":
        dbPath = getKodiMusicDBPath()
    elif type == "texture":
        dbPath = xbmc.translatePath("special://database/Textures13.db")
    else:
        dbPath = getKodiVideoDBPath()
    
    connection = sqlite3.connect(dbPath)
    
    return connection

def getKodiVideoDBPath():

    kodibuild = xbmc.getInfoLabel("System.BuildVersion")

    if kodibuild.startswith("13"):
        # Gotham
        dbVersion = "78"
    elif kodibuild.startswith("14"):
        # Helix
        dbVersion = "90"
    elif kodibuild.startswith("15"):
        # Isengard
        dbVersion = "93"
    else:
        # Not a compatible build
        xbmc.log("This Kodi version is incompatible. Current version: %s" % kodibuild)

    dbPath = xbmc.translatePath("special://profile/Database/MyVideos" + dbVersion + ".db")
    
    return dbPath  

def getKodiMusicDBPath():
    if xbmc.getInfoLabel("System.BuildVersion").startswith("13"):
        #gotham
        dbVersion = "46"
    elif xbmc.getInfoLabel("System.BuildVersion").startswith("15"):
        #isengard
        dbVersion = "52"
    else: 
        #helix
        dbVersion = "48"
    
    dbPath = xbmc.translatePath("special://profile/Database/MyMusic" + dbVersion + ".db")
    
    return dbPath   
    
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

def createSources():
    # To make Master lock compatible
    path = xbmc.translatePath("special://profile/").decode("utf-8")
    xmlpath = "%ssources.xml" % path

    sources = open(xmlpath, 'w')
    sources.write(
        
        '<sources>\n\t'
            '<programs>\n\t\t'
                '<default pathversion="1"></default>\n\t'
            '</programs>\n\t'
            '<video>\n\t\t'
                '<default pathversion="1"></default>\n\t\t'
                '<source>\n\t\t\t'
                    '<name>dummy one</name>\n\t\t\t'
                    '<path pathversion="1">smb://embydummy/dummypath1/</path>\n\t\t\t'
                    '<allowsharing>true</allowsharing>\n\t\t'
                '</source>\n\t\t'
                '<source>\n\t\t\t'
                    '<name>dummy two</name>\n\t\t\t'
                    '<path pathversion="1">smb://embydummy/dummypath2/</path>\n\t\t\t'
                    '<allowsharing>true</allowsharing>\n\t\t'
                '</source>\n\t'
            '</video>\n\t'
            '<music>\n\t\t'
                '<default pathversion="1"></default>\n\t'
            '</music>\n\t'
            '<pictures>\n\t\t'
                '<default pathversion="1"></default>\n\t'
            '</pictures>\n\t'
            '<files>\n\t\t'
                '<default pathversion="1"></default>\n\t'
            '</files>\n'
        '</sources>'
    )

def CleanName(filename):
    validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
    return ''.join(c for c in cleanedFilename if c in validFilenameChars)

def normalize_string(text):
    try:
        text = text.replace(":", "")
        text = text.replace("/", "-")
        text = text.replace("\\", "-")
        text = text.replace("<", "")
        text = text.replace(">", "")
        text = text.replace("*", "")
        text = text.replace("?", "")
        text = text.replace('|', "")
        text = text.strip()
        # Remove dots from the last character as windows can not have directories
        # with dots at the end
        text = text.rstrip('.')
        text = unicodedata.normalize('NFKD', unicode(text, 'utf-8')).encode('ascii', 'ignore')
    except:
        pass
    return text
   
        
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
       
    # delete video db table data
    print "Doing Video DB Reset"
    connection = KodiSQL("video")
    cursor = connection.cursor( )
    cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
    rows = cursor.fetchall()
    for row in rows:
        tableName = row[0]
        if(tableName != "version"):
            cursor.execute("DELETE FROM " + tableName)
    connection.commit()
    cursor.close()
    
    if addonSettings.getSetting("enableMusicSync") == "true":
        # delete video db table data
        print "Doing Music DB Reset"
        connection = KodiSQL("music")
        cursor = connection.cursor( )
        cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
        rows = cursor.fetchall()
        for row in rows:
            tableName = row[0]
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
