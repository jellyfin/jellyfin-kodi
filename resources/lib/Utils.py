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
import xml.etree.ElementTree as etree

from API import API
from PlayUtils import PlayUtils
from DownloadUtils import DownloadUtils

downloadUtils = DownloadUtils()
addon = xbmcaddon.Addon()
language = addon.getLocalizedString

 
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
    elif kodibuild.startswith("16"):
        # Jarvis
        dbVersion = "94"
    else:
        # Not a compatible build
        xbmc.log("This Kodi version is incompatible. Current version: %s" % kodibuild)

    dbPath = xbmc.translatePath("special://profile/Database/MyVideos" + dbVersion + ".db")
    
    return dbPath  

def getKodiMusicDBPath():
    if xbmc.getInfoLabel("System.BuildVersion").startswith("13"):
        #gotham
        dbVersion = "46"
    elif xbmc.getInfoLabel("System.BuildVersion").startswith("14"):
        #helix
        dbVersion = "48"
    elif xbmc.getInfoLabel("System.BuildVersion").startswith("15"):
        #isengard
        dbVersion = "52"
    elif xbmc.getInfoLabel("System.BuildVersion").startswith("16"):
        #jarvis
        dbVersion = "53"
    else: 
        # Not a compatible build
        xbmc.log("This Kodi version is incompatible. Current version: %s" % kodibuild)

    
    dbPath = xbmc.translatePath("special://profile/Database/MyMusic" + dbVersion + ".db")
    
    return dbPath   
    
def prettifyXml(elem):
    rough_string = etree.tostring(elem, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="\t")

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

    if xbmcvfs.exists(xmlpath):
        # add some way to writing dummy path to existing sources.xml
        pass
    else:
        sources = open(xmlpath, 'w')
        sources.write(
            
            '<sources>\n\t'
                '<programs>\n\t\t'
                    '<default pathversion="1"></default>\n\t'
                '</programs>\n\t'
                '<video>\n\t\t'
                    '<default pathversion="1"></default>\n\t\t'
                    '<source>\n\t\t\t'
                        '<name>Emby</name>\n\t\t\t'
                        '<path pathversion="1">smb://embydummy/dummypath1/</path>\n\t\t\t'
                        '<allowsharing>true</allowsharing>\n\t\t'
                    '</source>\n\t\t'
                    '<source>\n\t\t\t'
                        '<name>Emby</name>\n\t\t\t'
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

def pathsubstitution(add=True):

    path = xbmc.translatePath('special://userdata').decode('utf-8')
    xmlpath = "%sadvancedsettings.xml" % path
    xmlpathexists = xbmcvfs.exists(xmlpath)

    # original address
    originalServer = settings('ipaddress')
    originalPort = settings('port')
    originalHttp = settings('https') == "true"

    if originalHttp:
        originalHttp = "https"
    else:
        originalHttp = "http"

    # Process add or deletion
    if add:
        # second address
        secondServer = settings('secondipaddress')
        secondPort = settings('secondport')
        secondHttp = settings('secondhttps') == "true"

        if secondHttp:
            secondHttp = "https"
        else:
            secondHttp = "http"

        logMsg("EMBY", "Original address: %s://%s:%s, alternate is: %s://%s:%s" % (originalHttp, originalServer, originalPort, secondHttp, secondServer, secondPort), 1)

        if xmlpathexists:
            # we need to modify the file.
            try:
                xmlparse = etree.parse(xmlpath)
            except: # Document is blank
                root = etree.Element('advancedsettings')
            else:
                root = xmlparse.getroot()
            
            pathsubs = root.find('pathsubstitution')
            if pathsubs is None:
                pathsubs = etree.SubElement(root, 'pathsubstitution')
        else:
            # we need to create the file.
            root = etree.Element('advancedsettings')
            pathsubs = etree.SubElement(root, 'pathsubstitution')
        
        substitute = etree.SubElement(pathsubs, 'substitute')
        # From original address
        etree.SubElement(substitute, 'from').text = "%s://%s:%s" % (originalHttp, originalServer, originalPort)
        # To secondary address
        etree.SubElement(substitute, 'to').text = "%s://%s:%s" % (secondHttp, secondServer, secondPort)

        etree.ElementTree(root).write(xmlpath)
        settings('pathsub', "true")

    else: # delete the path substitution, we don't need it anymore.
        logMsg("EMBY", "Alternate address is disabled, removing path substitution for: %s://%s:%s" % (originalHttp, originalServer, originalPort), 1)

        xmlparse = etree.parse(xmlpath)
        root = xmlparse.getroot()
        
        iterator = root.getiterator("pathsubstitution")

        for substitutes in iterator:
            for substitute in substitutes:
                frominsert = substitute.find(".//from").text == "%s://%s:%s" % (originalHttp, originalServer, originalPort)

                if frominsert:
                    # Found a match, in case there's more than one substitution.
                    substitutes.remove(substitute)

        etree.ElementTree(root).write(xmlpath)
        settings('pathsub', "false")


def settings(setting, value = None):
    # Get or add addon setting
    addon = xbmcaddon.Addon()
    if value:
        addon.setSetting(setting, value)
    else:
        return addon.getSetting(setting)

def normalize_string(text):
    # For theme media, do not modify unless
    # modified in TV Tunes
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

    return text

def normalize_nodes(text):
    # For video nodes
    text = text.replace(":", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('|', "")
    text = text.replace('(', "")
    text = text.replace(')', "")
    text = text.strip()
    # Remove dots from the last character as windows can not have directories
    # with dots at the end
    text = text.rstrip('.')
    text = unicodedata.normalize('NFKD', unicode(text, 'utf-8')).encode('ascii', 'ignore')
    
    return text

def reloadProfile():
    # Useful to reload the add-on without restarting Kodi.
    profile = xbmc.getInfoLabel('System.ProfileName')
    xbmc.executebuiltin("LoadProfile(%s)" % profile)
   

def reset():

    WINDOW = xbmcgui.Window( 10000 )
    return_value = xbmcgui.Dialog().yesno("Warning", "Are you sure you want to reset your local Kodi database?")

    if return_value == 0:
        return

    # Because the settings dialog could be open
    # it seems to override settings so we need to close it before we reset settings.
    xbmc.executebuiltin("Dialog.Close(all,true)")
    
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

    settings('SyncInstallRunDone', "false")
    
    # Ask if user information should be deleted too.
    return_user = xbmcgui.Dialog().yesno("Warning", "Reset all Emby Addon settings?")
    if return_user == 1:
        WINDOW.setProperty('deletesettings', "true")
        addon = xbmcaddon.Addon()
        addondir = xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')
        dataPath = "%ssettings.xml" % addondir
        xbmcvfs.delete(dataPath)
        logMsg("EMBY", "Deleting: settings.xml", 1)
    
    # first stop any db sync
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
    
    if settings('enableMusicSync') == "true":
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
    #settings('SyncInstallRunDone', "false")
    #WINDOW.setProperty("SyncInstallRunDone", "false")

    dialog = xbmcgui.Dialog()
    # Reload would work instead of restart since the add-on is a service.
    #dialog.ok('Emby Reset', 'Database reset has completed, Kodi will now restart to apply the changes.')
    #WINDOW.clearProperty("SyncDatabaseShouldStop")
    #reloadProfile()
    dialog.ok('Emby Reset', 'Database reset has completed, Kodi will now restart to apply the changes.')
    xbmc.executebuiltin("RestartApp")