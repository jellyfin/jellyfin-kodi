#################################################################################################
# CreateFiles
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import os
import json

from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.etree import ElementTree
from xml.dom import minidom
import xml.etree.cElementTree as ET

from DownloadUtils import DownloadUtils
from API import API
import Utils as utils

addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
addondir = xbmc.translatePath(addon.getAddonInfo('profile'))
dataPath = os.path.join(addondir,"library")
movieLibrary = os.path.join(dataPath,'movies')
tvLibrary = os.path.join(dataPath,'tvshows')

class CreateFiles():   
    def createSTRM(self,item,parentId=None):
        
        item_type=str(item.get("Type")).encode('utf-8')
        if item_type == "Movie":
            itemPath = os.path.join(movieLibrary,item["Id"])
            strmFile = os.path.join(itemPath,item["Id"] + ".strm")

        if item_type == "MusicVideo":
            itemPath = os.path.join(musicVideoLibrary,item["Id"])
            strmFile = os.path.join(itemPath,item["Id"] + ".strm")

        if item_type == "Episode":
            itemPath = os.path.join(tvLibrary,parentId)
            if str(item.get("IndexNumber")) != None:
                filenamestr = self.CleanName(item.get("SeriesName")).encode('utf-8') + " S" + str(item.get("ParentIndexNumber")) + "E" + str(item.get("IndexNumber")) + " (" + item["Id"] + ").strm"
            else:
                filenamestr = self.CleanName(item.get("SeriesName")).encode('utf-8') + " S0E0 " + self.CleanName(item["Name"].decode('utf-8')) + " (" + item["Id"] + ").strm"
            strmFile = os.path.join(itemPath,filenamestr)

        changes = False
        if not xbmcvfs.exists(strmFile):
            changes = True
            xbmcvfs.mkdir(itemPath)
            text_file = open(strmFile, "w")
            
            playUrl = "plugin://plugin.video.mb3sync/?id=" + item["Id"] + '&mode=play'

            text_file.writelines(playUrl)
            text_file.close()
            
        return changes
            
    def createNFO(self,item, parentId=None):
        downloadUtils = DownloadUtils()
        timeInfo = API().getTimeInfo(item)
        userData=API().getUserData(item)
        people = API().getPeople(item)
        mediaStreams=API().getMediaStreams(item)
        studios = API().getStudios(item)
        userid = downloadUtils.getUserId()
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port  
        item_type=str(item.get("Type"))
        
        if item_type == "Movie":
            itemPath = os.path.join(movieLibrary,item["Id"])
            nfoFile = os.path.join(itemPath,item["Id"] + ".nfo")
            rootelement = "movie"
        if item_type == "Series":
            itemPath = os.path.join(tvLibrary,item["Id"])
            nfoFile = os.path.join(itemPath,"tvshow.nfo")
            rootelement = "tvshow"
        if item_type == "Episode":
            itemPath = os.path.join(tvLibrary,parentId)
            if str(item.get("ParentIndexNumber")) != None:
                filenamestr = self.CleanName(item.get("SeriesName")).encode('utf-8') + " S" + str(item.get("ParentIndexNumber")) + "E" + str(item.get("IndexNumber")) + " (" + item["Id"] + ").nfo"
            else:
                filenamestr = self.CleanName(item.get("SeriesName")).encode('utf-8') + " S0E0 " + self.CleanName(item["Name"].decode('utf-8')) + " (" + item["Id"] + ").nfo"
            nfoFile = os.path.join(itemPath,filenamestr)
            rootelement = "episodedetails"
            
            
        changes = False
        if not xbmcvfs.exists(nfoFile):
            changes = True
            #utils.logMsg("MB3 Syncer","creating NFO file " + nfoFile)
            xbmcvfs.mkdir(itemPath)        
            root = Element(rootelement)
            SubElement(root, "id").text = item["Id"]
            if item.get("Tag") != None:
                for tag in item.get("Tag"):
                    SubElement(root, "tag").text = tag
            
            SubElement(root, "thumb").text = API().getArtwork(item, "Primary")
            SubElement(root, "fanart").text = API().getArtwork(item, "Backdrop")
            
            
            SubElement(root, "title").text = utils.convertEncoding(item["Name"])
            SubElement(root, "originaltitle").text = utils.convertEncoding(item["Name"])
            SubElement(root, "sorttitle").text = utils.convertEncoding(item["SortName"])
            
            if item.has_key("OfficialRating"):
                SubElement(root, "mpaa").text = item["OfficialRating"]
            
            if item.get("CriticRating") != None:
                rating = int(item.get("CriticRating"))/10
                SubElement(root, "rating").text = str(rating)
            
            if item.get("DateCreated") != None:
                SubElement(root, "dateadded").text = item["DateCreated"]
            
            if userData.get("PlayCount") != None:
                SubElement(root, "playcount").text = userData.get("PlayCount")
                if int(userData.get("PlayCount")) > 0:
                    SubElement(root, "watched").text = "true"
            
            if timeInfo.get("ResumeTime") != None:
                resume_sec = int(round(float(timeInfo.get("ResumeTime"))))*60
                total_sec = int(round(float(timeInfo.get("TotalTime"))))*60
                resume = SubElement(root, "resume")
                SubElement(resume, "position").text = str(resume_sec)
                SubElement(resume, "total").text = str(total_sec)
            
            if item_type == "Episode":
                SubElement(root, "season").text = str(item.get("ParentIndexNumber"))
                SubElement(root, "episode").text = str(item.get("IndexNumber"))
                SubElement(root, "aired").text = str(item.get("ProductionYear"))
                
            SubElement(root, "year").text = str(item.get("ProductionYear"))
            if item.get("PremiereDate") != None:
                premieredatelist = (item.get("PremiereDate")).split("T")
                premieredate = premieredatelist[0]
                SubElement(root, "firstaired").text = premieredate
                SubElement(root, "premiered").text = premieredate
                
            if(timeInfo.get('Duration') != "0"):
                SubElement(root, "runtime").text = str(timeInfo.get('Duration'))
            
            SubElement(root, "plot").text = utils.convertEncoding(API().getOverview(item))
            
            if item.get("ShortOverview") != None:
                SubElement(root, "plotoutline").text = utils.convertEncoding(item.get("ShortOverview"))
            
            if item.get("TmdbCollectionName") != None:
                SubElement(root, "set").text = item.get("TmdbCollectionName")
            
            if item.get("ProviderIds") != None:
                if item.get("ProviderIds").get("Imdb") != None:
                    SubElement(root, "imdbnumber").text = item
            
            if people.get("Writer") != None:
                for writer in people.get("Writer"):
                    SubElement(root, "writer").text = utils.convertEncoding(writer)
            
            if people.get("Director") != None:
                for director in people.get("Director"):
                    SubElement(root, "director").text = utils.convertEncoding(director)
            
            if item.get("Genres") != None:
                for genre in item.get("Genres"):
                    SubElement(root, "genre").text = utils.convertEncoding(genre)
            
            if studios != None:
                for studio in studios:
                    SubElement(root, "studio").text = utils.convertEncoding(studio).replace("/", "&")
                    
            if item.get("ProductionLocations") != None:
                for country in item.get("ProductionLocations"):
                    SubElement(root, "country").text = utils.convertEncoding(country)

            #trailer link
            trailerUrl = None
            if item.get("LocalTrailerCount") != None and item.get("LocalTrailerCount") > 0:
                itemTrailerUrl = "http://" + server + "/mediabrowser/Users/" + userid + "/Items/" + item.get("Id") + "/LocalTrailers?format=json"
                jsonData = downloadUtils.downloadUrl(itemTrailerUrl, suppress=True, popup=0 )
                if(jsonData != ""):
                    trailerItem = json.loads(jsonData)
                    trailerUrl = "plugin://plugin.video.mb3sync/?id=" + trailerItem[0].get("Id") + '&mode=play'
                    SubElement(root, "trailer").text = trailerUrl
            
            #add streamdetails
            fileinfo = SubElement(root, "fileinfo")
            streamdetails = SubElement(fileinfo, "streamdetails")
            video = SubElement(streamdetails, "video")
            SubElement(video, "duration").text = str(mediaStreams.get('totaltime'))
            SubElement(video, "aspect").text = mediaStreams.get('aspectratio')
            SubElement(video, "codec").text = mediaStreams.get('videocodec')
            SubElement(video, "width").text = str(mediaStreams.get('width'))
            SubElement(video, "height").text = str(mediaStreams.get('height'))
            SubElement(video, "duration").text = str(timeInfo.get('Duration'))
            
            audio = SubElement(streamdetails, "audio")
            SubElement(audio, "codec").text = mediaStreams.get('audiocodec')
            SubElement(audio, "channels").text = mediaStreams.get('channels')
            
            #add people
            if item.get("People") != None:
                for actor in item.get("People"):
                    if(actor.get("Type") == "Actor"):
                        actor_elem = SubElement(root, "actor")
                        SubElement(actor_elem, "name").text = utils.convertEncoding(actor.get("Name"))
                        SubElement(actor_elem, "type").text = utils.convertEncoding(actor.get("Role"))
                        SubElement(actor_elem, "thumb").text = downloadUtils.imageUrl(actor.get("Id"), "Primary", 0, 400, 400)

            ET.ElementTree(root).write(nfoFile, xml_declaration=True)
        return changes
        
    def CleanName(self, name):
        name = name.replace(":", "-")
        name = name.replace("\\", "-")
        name = name.replace("/", "-")
        name = name.replace("*", "-")
        name = name.replace("?", "-")
        name = name.replace("<", "-")
        name = name.replace(">", "-")
        name = name.replace("|", "-")
        return name    
