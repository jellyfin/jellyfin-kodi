# -*- coding: utf-8 -*-

#################################################################################################

import os
import sys
import urlparse

import xbmc
import xbmcaddon
import xbmcgui

#################################################################################################

addon_ = xbmcaddon.Addon(id='plugin.video.emby')
addon_path = addon_.getAddonInfo('path').decode('utf-8')
base_resource = xbmc.translatePath(os.path.join(addon_path, 'resources', 'lib')).decode('utf-8')
sys.path.append(base_resource)

#################################################################################################

import entrypoint
import utils
from utils import Logging, window

#################################################################################################

log = Logging('Default').log
enableProfiling = False

class Main:


    # MAIN ENTRY POINT
    def __init__(self):

        # Parse parameters
        base_url = sys.argv[0]
        params = urlparse.parse_qs(sys.argv[2][1:])
        xbmc.log("Parameter string: %s" % sys.argv[2])
        try:
            mode = params['mode'][0]
            itemid = params.get('id')
            if itemid:
                itemid = itemid[0]
        except:
            params = {}
            mode = ""


        modes = {

            'reset': utils.reset,
            'resetauth': entrypoint.resetAuth,
            'play': entrypoint.doPlayback,
            'passwords': utils.passwordsXML,
            'adduser': entrypoint.addUser,
            'thememedia': entrypoint.getThemeMedia,
            'channels': entrypoint.BrowseChannels,
            'channelsfolder': entrypoint.BrowseChannels,
            'browsecontent': entrypoint.BrowseContent,
            'getsubfolders': entrypoint.GetSubFolders,
            'nextup': entrypoint.getNextUpEpisodes,
            'inprogressepisodes': entrypoint.getInProgressEpisodes,
            'recentepisodes': entrypoint.getRecentEpisodes,
            'refreshplaylist': entrypoint.refreshPlaylist,
            'deviceid': entrypoint.resetDeviceId,
            'delete': entrypoint.deleteItem
        }
        
        if "/extrafanart" in sys.argv[0]:
            embypath = sys.argv[2][1:]
            embyid = params.get('id',[""])[0]
            entrypoint.getExtraFanArt(embyid,embypath)
            
        if "/Extras" in sys.argv[0] or "/VideoFiles" in sys.argv[0]:
            embypath = sys.argv[2][1:]
            embyid = params.get('id',[""])[0]
            entrypoint.getVideoFiles(embyid,embypath)

        if modes.get(mode):
            # Simple functions
            if mode == "play":
                dbid = params.get('dbid')
                modes[mode](itemid, dbid)

            elif mode in ("nextup", "inprogressepisodes", "recentepisodes"):
                limit = int(params['limit'][0])
                modes[mode](itemid, limit)
            
            elif mode in ["channels","getsubfolders"]:
                modes[mode](itemid)
                
            elif mode == "browsecontent":
                modes[mode]( itemid, params.get('type',[""])[0], params.get('folderid',[""])[0] )

            elif mode == "channelsfolder":
                folderid = params['folderid'][0]
                modes[mode](itemid, folderid)
            
            else:
                modes[mode]()
        else:
            # Other functions
            if mode == "settings":
                xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')
            elif mode in ("manualsync", "fastsync", "repair"):
                if window('emby_online') != "true":
                    # Server is not online, do not run the sync
                    xbmcgui.Dialog().ok(heading="Emby for Kodi",
                                        line1=("Unable to run the sync, the add-on is not "
                                               "connected to the Emby server."))
                    log("Not connected to the emby server.", 1)
                    return
                    
                if window('emby_dbScan') != "true":
                    import librarysync
                    lib = librarysync.LibrarySync()
                    if mode == "manualsync":
                        librarysync.ManualSync().sync(dialog=True)
                    elif mode == "fastsync":
                        lib.startSync()
                    else:
                        lib.fullSync(repair=True)
                else:
                    log("Database scan is already running.", 1)
                    
            elif mode == "texturecache":
                import artwork
                artwork.Artwork().FullTextureCacheSync()
            else:
                entrypoint.doMainListing()

                      
if ( __name__ == "__main__" ):
    log('plugin.video.emby started', 1)

    if enableProfiling:
        import cProfile
        import pstats
        import random
        from time import gmtime, strftime
        addonid      = addon_.getAddonInfo('id').decode( 'utf-8' )
        datapath     = os.path.join( xbmc.translatePath( "special://profile/" ).decode( 'utf-8' ), "addon_data", addonid )
        
        filename = os.path.join( datapath, strftime( "%Y%m%d%H%M%S",gmtime() ) + "-" + str( random.randrange(0,100000) ) + ".log" )
        cProfile.run( 'Main()', filename )
        
        stream = open( filename + ".txt", 'w')
        p = pstats.Stats( filename, stream = stream )
        p.sort_stats( "cumulative" )
        p.print_stats()
    
    else:
        Main()
    
    log('plugin.video.emby stopped', 1)