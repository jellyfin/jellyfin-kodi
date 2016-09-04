# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys
import urlparse

import xbmc
import xbmcaddon
import xbmcgui

#################################################################################################

_addon = xbmcaddon.Addon(id='plugin.video.emby')
_addon_path = _addon.getAddonInfo('path').decode('utf-8')
_base_resource = xbmc.translatePath(os.path.join(_addon_path, 'resources', 'lib')).decode('utf-8')
sys.path.append(_base_resource)

#################################################################################################

import entrypoint
import utils
from utils import window, language as lang

#################################################################################################

import loghandler

loghandler.config()
log = logging.getLogger("EMBY.default")

#################################################################################################


class Main():


    # MAIN ENTRY POINT
    #@utils.profiling()
    def __init__(self):

        # Parse parameters
        base_url = sys.argv[0]
        params = urlparse.parse_qs(sys.argv[2][1:])
        log.warn("Parameter string: %s" % sys.argv[2])
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
            'delete': entrypoint.deleteItem,
            'connect': entrypoint.emby_connect
        }
        
        if "/extrafanart" in sys.argv[0]:
            embypath = sys.argv[2][1:]
            embyid = params.get('id',[""])[0]
            entrypoint.getExtraFanArt(embyid,embypath)
            return
            
        if "/Extras" in sys.argv[0] or "/VideoFiles" in sys.argv[0]:
            embypath = sys.argv[2][1:]
            embyid = params.get('id',[""])[0]
            entrypoint.getVideoFiles(embyid, embypath)
            return

        if modes.get(mode):
            # Simple functions
            if mode == "play":
                dbid = params.get('dbid')
                modes[mode](itemid, dbid)

            elif mode in ("nextup", "inprogressepisodes", "recentepisodes"):
                limit = int(params['limit'][0])
                modes[mode](itemid, limit)
            
            elif mode in ("channels","getsubfolders"):
                modes[mode](itemid)
                
            elif mode == "browsecontent":
                modes[mode](itemid, params.get('type',[""])[0], params.get('folderid',[""])[0])

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
                    xbmcgui.Dialog().ok(heading=lang(29999),
                                        line1=lang(33034))
                    log.warn("Not connected to the emby server.")
                    return
                    
                if window('emby_dbScan') != "true":
                    import librarysync
                    lib = librarysync.LibrarySync()
                    if mode == "manualsync":
                        librarysync.ManualSync().sync()
                    elif mode == "fastsync":
                        lib.startSync()
                    else:
                        lib.fullSync(repair=True)
                else:
                    log.warn("Database scan is already running.")
                    
            elif mode == "texturecache":
                import artwork
                artwork.Artwork().fullTextureCacheSync()
            
            else:
                entrypoint.doMainListing()

           
if __name__ == "__main__":
    log.info('plugin.video.emby started')
    Main()
    log.info('plugin.video.emby stopped')