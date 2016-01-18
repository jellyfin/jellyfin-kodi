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

#################################################################################################

enableProfiling = False

class Main:


    # MAIN ENTRY POINT
    def __init__(self):

        # Parse parameters
        base_url = sys.argv[0]
        addon_handle = int(sys.argv[1])
        print sys.argv[2]
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
            'extrafanart': entrypoint.getExtraFanArt,
            'play': entrypoint.doPlayback,
            'passwords': utils.passwordsXML,
            'adduser': entrypoint.addUser,
            'thememedia': entrypoint.getThemeMedia,
            'channels': entrypoint.BrowseChannels,
            'channelsfolder': entrypoint.BrowseChannels,
            'browsecontent': entrypoint.BrowseContent,
            'nextup': entrypoint.getNextUpEpisodes,
            'inprogressepisodes': entrypoint.getInProgressEpisodes,
            'recentepisodes': entrypoint.getRecentEpisodes,
            'refreshplaylist': entrypoint.refreshPlaylist
        }
        
        if "extrafanart" in sys.argv[0]:
            entrypoint.getExtraFanArt()

        if modes.get(mode):
            # Simple functions
            if mode == "play":
                dbid = params.get('dbid')
                modes[mode](itemid, dbid)

            elif mode in ("nextup", "inprogressepisodes", "recentepisodes"):
                limit = int(params['limit'][0])
                modes[mode](itemid, limit)
            
            elif mode == "channels":
                modes[mode](itemid)
                
            elif mode == "browsecontent":
                modes[mode]( itemid, params.get('type',[""])[0], params.get('folderid',[""])[0], params.get('filter',[""])[0] )

            elif mode == "channelsfolder":
                folderid = params['folderid'][0]
                modes[mode](itemid, folderid)
            
            else:
                modes[mode]()
        else:
            # Other functions
            if mode == "settings":
                xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')
            elif mode in ("manualsync", "repair"):
                if utils.window('emby_dbScan') != "true":
                    import librarysync
                    lib = librarysync.LibrarySync()
                    if mode == "manualsync":
                        lib.fullSync(manualrun=True)
                    else:
                        lib.fullSync(repair=True)
                else:
                    utils.logMsg("EMBY", "Database scan is already running.", 1)
                    
            elif mode == "texturecache":
                import artwork
                artwork.Artwork().FullTextureCacheSync()
            else:
                entrypoint.doMainListing()

                      
if ( __name__ == "__main__" ):
    xbmc.log('plugin.video.emby started')

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
    
    xbmc.log('plugin.video.emby stopped')