# -- coding: utf-8 --
# API.py
# This class helps translate more complex cases from the MediaBrowser API to the XBMC API

from datetime import datetime
from random import randrange
import xbmc
import xbmcgui
import xbmcaddon

class API():
    
    def getPeople(self, item):
        # Process People
        director = []
        writer = []
        cast = []

        try:
            people = item['People']
        except: pass
        else:
            
            for person in people:

                type = person['Type']
                Name = person['Name']

                if "Director" in type:
                    director.append(Name)
                elif "Writing" in type:
                    writer.append(Name)
                elif "Writer" in type:
                    writer.append(Name)
                elif "Actor" in type:
                    cast.append(Name)

        return {

            'Director': director,
            'Writer':   writer,
            'Cast':     cast
        }

    def getTimeInfo(self, item):
        # Runtime and Resume point
        tempRuntime = 0
        runtime = 0
        resume = 0

        try: # Get resume point
            userdata = item['UserData']
            playbackPosition = userdata['PlaybackPositionTicks']
            resume = playbackPosition / 10000000.0
        except: pass
        
        try: # Get total runtime
            tempRuntime = item['RunTimeTicks']
        
        except:
            try: tempRuntime = item['CumulativeRunTimeTicks']
            except: pass

        finally: 
            runtime = tempRuntime / 10000000.0


        return {

            'ResumeTime':   resume,
            'TotalTime':    runtime
        }

    def getStudios(self, item):
        # Process Studio
        studios = []

        try:
            studio = item['SeriesStudio']
            studios.append(studio)
        except:
            try:
                studioArray = item['Studios']
                for studio in studioArray:
                    studios.append(studio['Name'])
            except: pass

        return studios

    def getGenre(self,item):
        genre = ""
        genres = item.get("Genres")
        if genres != None and genres != []:
            for genre_string in genres:
                if genre == "": #Just take the first genre
                    genre = genre_string
                else:
                    genre = genre + " / " + genre_string
        elif item.get("SeriesGenres") != None and item.get("SeriesGenres") != '':
            genres = item.get("SeriesGenres")
            if genres != None and genres != []:
              for genre_string in genres:
                if genre == "": #Just take the first genre
                    genre = genre_string
                else:
                    genre = genre + " / " + genre_string
        return genre

    def getMediaStreams(self, item, mediaSources = False):

        videotracks = [] # Height, Width, Codec, AspectRatio, AspectFloat, 3D 
        audiotracks = [] # Codec, Channels, language
        subtitlelanguages = [] # Language

        if mediaSources:
            try:
                MediaStreams = item['MediaSources'][0]['MediaStreams']
            except:
                MediaStreams = None
        else:
            MediaStreams = item.get('MediaStreams')

        if MediaStreams:
            # Sort through the Video, Audio, Subtitle tracks
            for mediaStream in MediaStreams:

                type = mediaStream.get("Type", "")

                if "Video" in type:
                    videotrack = {}
                    videotrack['videocodec'] = mediaStream.get('Codec', "").lower()
                    container = item['MediaSources'][0].get('Container', "").lower()
                    if "msmpeg4" in videotrack['videocodec']:
                        videotrack['videocodec'] = "divx"
                    elif "mpeg4" in videotrack['videocodec']:
                        profile = mediaStream.get('Profile', "").lower()
                        if "simple profile" in profile or not profile:
                            videotrack['videocodec'] = "xvid"
                    elif "h264" in videotrack['videocodec']:
                        if container in ("mp4", "mov", "m4v"):
                            videotrack['videocodec'] = "avc1"
                    videotrack['height'] = mediaStream.get('Height')
                    videotrack['width'] = mediaStream.get('Width')
                    videotrack['Video3DFormat'] = item.get('Video3DFormat')
                    videotrack['aspectratio'] = mediaStream.get('AspectRatio', "0")
                    if len(videotrack['aspectratio']) >= 3:
                        try:
                            aspectwidth, aspectheight = videotrack['aspectratio'].split(':')
                            videotrack['aspectratio'] = round(float(aspectwidth) / float(aspectheight), 6)
                        except:
                            videotrack['aspectratio'] = round(float(videotrack['width'] / videotrack['height']), 6)
                    else:
                        videotrack['aspectratio'] = round(float(videotrack['width'] / videotrack['height']), 6)
                    videotracks.append(videotrack)

                elif "Audio" in type:
                    audiotrack = {}
                    audiotrack['audiocodec'] = mediaStream.get('Codec')
                    audiotrack['channels'] = mediaStream.get('Channels')
                    audiotrack['audiolanguage'] = mediaStream.get('Language')
                    audiotracks.append(audiotrack)

                elif "Subtitle" in type:
                    try:
                        subtitlelanguages.append(mediaStream['Language'])
                    except:
                        subtitlelanguages.append("Unknown")

        return {

            'videocodec'        : videotracks, 
            'audiocodec'        : audiotracks,
            'subtitlelanguage'  : subtitlelanguages
        }

    
    def getChecksum(self, item):
        # use the etags checksum for this if available
        # AND the userdata
        checksum = ""
        
        if item.get("Etag") != None:
            checksum = item.get("Etag") 
        userData = item.get("UserData")
        if(userData != None):
            checksum += str(userData.get("Played"))
            checksum += str(userData.get("IsFavorite"))
            if userData.get('UnplayedItemCount') != None:
                checksum += str(userData.get("UnplayedItemCount"))
            if userData.get('LastPlayedDate') != None:
                checksum += str(userData.get("LastPlayedDate"))
            if userData.get('PlaybackPositionTicks') != None:
                checksum += str(userData.get("PlaybackPositionTicks"))
            
        return checksum
    
    def getUserData(self, item):
        # Default
        favorite = False
        playcount = None
        lastPlayedDate = None
        userKey = ""

        try:
            userdata = item['UserData']
        
        except: # No userdata found.
            pass

        else:
            favorite = userdata['IsFavorite']
            userKey = userdata.get('Key', "")
            
            watched = userdata['Played']
            if watched:
                # Playcount is tied to the watch status
                playcount = userdata['PlayCount']
                if playcount == 0:
                    playcount = 1
            else:
                playcount = None
            
            lastPlayedDate = userdata.get('LastPlayedDate', None)
            if lastPlayedDate:
                lastPlayedDate = lastPlayedDate.split('.')[0].replace('T', " ")

        return {

            'Favorite':         favorite,
            'PlayCount':        playcount,
            'LastPlayedDate':   lastPlayedDate,
            'Key':              userKey
        }

        
    def getRecursiveItemCount(self, item):
        if item.get("RecursiveItemCount") != None:
            return str(item.get("RecursiveItemCount"))
        else:
            return "0"     
        
    def getOverview(self, item):

        overview = ""

        try:
            overview = item['Overview']
            overview = overview.replace("\"", "\'")
            overview = overview.replace("\n", " ")
            overview = overview.replace("\r", " ")
        except: pass

        return overview
        
    def getTVInfo(self, item, userData):
        TotalSeasons     = 0 if item.get("ChildCount")==None else item.get("ChildCount")
        TotalEpisodes    = 0 if item.get("RecursiveItemCount")==None else item.get("RecursiveItemCount")
        WatchedEpisodes  = 0 if userData.get("UnplayedItemCount")==None else TotalEpisodes-int(userData.get("UnplayedItemCount"))
        UnWatchedEpisodes = 0 if userData.get("UnplayedItemCount")==None else int(userData.get("UnplayedItemCount"))
        NumEpisodes      = TotalEpisodes
        tempEpisode = ""
        if (item.get("IndexNumber") != None):
            episodeNum = item.get("IndexNumber")
            if episodeNum < 10:
                tempEpisode = "0" + str(episodeNum)
            else:
                tempEpisode = str(episodeNum)
                
        tempSeason = ""
        if (str(item.get("ParentIndexNumber")) != None):
            tempSeason = str(item.get("ParentIndexNumber"))
            if item.get("ParentIndexNumber") < 10:
                tempSeason = "0" + tempSeason
        if item.get("SeriesName") != None:
            temp=item.get("SeriesName")
            SeriesName=temp.encode('utf-8')
        else:
            SeriesName=''
        return  {'TotalSeasons'     :   str(TotalSeasons),
                 'TotalEpisodes'    :   str(TotalEpisodes),
                 'WatchedEpisodes'  :   str(WatchedEpisodes),
                 'UnWatchedEpisodes':   str(UnWatchedEpisodes),
                 'NumEpisodes'      :   str(NumEpisodes),
                 'Season'           :   tempSeason,
                 'Episode'          :   tempEpisode,
                 'SeriesName'       :   SeriesName
                 }
    
    def getDateCreated(self, item):

        dateadded = None

        try:
            dateadded = item['DateCreated']
            dateadded = dateadded.split('.')[0].replace('T', " ")
        except: pass

        return dateadded

    def getPremiereDate(self, item):

        premiere = None

        try:
            premiere = item['PremiereDate']
            premiere = premiere.split('.')[0].replace('T', " ")
        except: pass

        return premiere

    def getTagline(self, item):

        tagline = None

        try:
            tagline = item['Taglines'][0]
        except: pass

        return tagline

    def getProvider(self, item, providername):
        # Provider Name: imdb or tvdb
        provider = None

        try:
            if "imdb" in providername:
                provider = item['ProviderIds']['Imdb']
            elif "tvdb" in providername:
                provider = item['ProviderIds']['Tvdb']
            elif "musicBrainzArtist" in providername:
                provider = item['ProviderIds']['MusicBrainzArtist']
            elif "musicBrainzAlbum" in providername:
                provider = item['ProviderIds']['MusicBrainzAlbum']
            elif "musicBrainzTrackId" in providername:
                provider = item['ProviderIds']['MusicBrainzTrackId']
        except: pass

        return provider

    def getCountry(self, item):

        country = None

        try:
            country = item['ProductionLocations'][0]
        except: pass

        return country

    def getArtworks(self, data, type, mediaType = "", index = "0", getAll = False):

        """
                Get all artwork, it will return an empty string
                for the artwork type not found.

                Index only matters when getAll is False.

                mediaType:      movie, boxset, tvshow, episode, season

                Artwork type:   Primary, Banner, Logo, Art, Thumb,
                                Disc Backdrop
                                                                            """
        id = data['Id']

        maxHeight = 10000
        maxWidth = 10000
        imageTag = "e3ab56fe27d389446754d0fb04910a34" # Place holder tag
        

        if getAll:

            allartworks = {

                'Primary': "",
                'Banner': "",
                'Logo': "",
                'Art': "",
                'Thumb': "",
                'Disc': "",
                'Backdrop': ""
            }

            for keytype in allartworks:
                type = keytype
                url = ""

                allartworks[keytype] = url


            return allartworks

        else: pass

    def getArtwork(self, data, type, mediaType = "", index = "0", userParentInfo = False):

        addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
        id = data.get("Id")
        getSeriesData = False
        userData = data.get("UserData") 

        if type == "tvshow.poster": # Change the Id to the series to get the overall series poster
            if data.get("Type") == "Season" or data.get("Type")== "Episode":
                id = data.get("SeriesId")
                getSeriesData = True
        elif type == "poster" and data.get("Type") == "Episode" and addonSettings.getSetting('useSeasonPoster')=='true': # Change the Id to the Season to get the season poster
            id = data.get("SeasonId")
        if type == "poster" or type == "tvshow.poster": # Now that the Ids are right, change type to MB3 name
            type="Primary"
        if data.get("Type") == "Season":  # For seasons: primary (poster), thumb and banner get season art, rest series art
            if type != "Primary" and type != "Primary2" and type != "Primary3" and type != "Primary4" and type != "Thumb" and type != "Banner" and type!="Thumb3":
                id = data.get("SeriesId")
                getSeriesData = True
        if data.get("Type") == "Episode":  # For episodes: primary (episode thumb) gets episode art, rest series art. 
            if type != "Primary" and type != "Primary2" and type != "Primary3" and type != "Primary4":
                id = data.get("SeriesId")
                getSeriesData = True
            if type =="Primary2" or type=="Primary3" or type=="Primary4":
                id = data.get("SeasonId")
                getSeriesData = True
                if  data.get("SeasonUserData") != None:
                    userData = data.get("SeasonUserData")
        if id == None:
            id=data.get("Id")
                
        imageTag = "e3ab56fe27d389446754d0fb04910a34" # a place holder tag, needs to be in this format
        originalType = type
        if type == "Primary2" or type == "Primary3" or type == "Primary4" or type=="SeriesPrimary":
            type = "Primary"
        if type == "Backdrop2" or type=="Backdrop3" or type=="BackdropNoIndicators":
            type = "Backdrop"
        if type == "Thumb2" or type=="Thumb3":
            type = "Thumb"
        if(data.get("ImageTags") != None and data.get("ImageTags").get(type) != None):
            imageTag = data.get("ImageTags").get(type)   

        if (data.get("Type") == "Episode" or data.get("Type") == "Season") and type=="Logo":
            imageTag = data.get("ParentLogoImageTag")
        if (data.get("Type") == "Episode" or data.get("Type") == "Season") and type=="Art":
            imageTag = data.get("ParentArtImageTag")
        if (data.get("Type") == "Episode" and originalType=="Thumb3"):
            imageTag = data.get("SeriesThumbImageTag")
        if (data.get("Type") == "Season" and originalType=="Thumb3" and imageTag=="e3ab56fe27d389446754d0fb04910a34"):
            imageTag = data.get("ParentThumbImageTag")
            id = data.get("SeriesId")
            
        # for music we return the parent art if no image exists
        if (data.get("Type") == "MusicAlbum" or data.get("Type") == "Audio") and type=="Backdrop" and not data.get("BackdropImageTags"):
            data["BackdropImageTags"] = data.get("ParentBackdropImageTags")
            id = data.get("ParentBackdropItemId")
        if (data.get("Type") == "MusicAlbum" or data.get("Type") == "Audio") and type=="Logo" and (not imageTag or imageTag == "e3ab56fe27d389446754d0fb04910a34"):
            imageTag = data.get("ParentLogoImageTag")
            id = data.get("ParentLogoItemId")
        if (data.get("Type") == "MusicAlbum" or data.get("Type") == "Audio") and type=="Art" and (not imageTag or imageTag == "e3ab56fe27d389446754d0fb04910a34"):
            imageTag = data.get("ParentArtImageTag")
            id = data.get("ParentArtItemId")
     
        query = ""
        maxHeight = "10000"
        maxWidth = "10000"
        height = ""
        width = ""
        played = "0"
        totalbackdrops = 0

        if addonSettings.getSetting('coverArtratio') == "true":
            if mediaType in ("movie","boxset","tvshow"):
                if "Primary" in type:
                    # Only force ratio for cover art for main covers
                    aspectratio = data.get("PrimaryImageAspectRatio")
                    width = "&Width=1000"
                    height = "&Height=1480"

        if originalType =="BackdropNoIndicators" and index == "0" and data.get("BackdropImageTags") != None:
            totalbackdrops = len(data.get("BackdropImageTags"))
            if totalbackdrops != 0:
                index = str(randrange(0,totalbackdrops))
        # use the local image proxy server that is made available by this addons service
        # Load user information set by UserClient
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        server = WINDOW.getProperty('server%s' % username)

        if addonSettings.getSetting('compressArt')=='true':
            query = query + "&Quality=90"
        
        if imageTag == None:
            imageTag = "e3ab56fe27d389446754d0fb04910a34"
            
        artwork = "%s/mediabrowser/Items/%s/Images/%s/%s?MaxWidth=%s&MaxHeight=%s%s%s&Format=original&Tag=%s%s" % (server, id, type, index, maxWidth, maxHeight, height, width, imageTag, query)
        #artwork = "%s/mediabrowser/Items/%s/Images/%s/%s/%s/original/%s/%s/%s?%s" % (server, id, type, index, imageTag, width, height, played, query) <- broken
        if addonSettings.getSetting('disableCoverArt')=='true':
            artwork = artwork + "&EnableImageEnhancers=false"
        
        # do not return non-existing images
        if (    (type!="Backdrop" and imageTag=="e3ab56fe27d389446754d0fb04910a34") |  #Remember, this is the placeholder tag, meaning we didn't find a valid tag
                (type=="Backdrop" and data.get("BackdropImageTags") != None and len(data.get("BackdropImageTags")) == 0) | 
                (type=="Backdrop" and data.get("BackdropImageTag") != None and len(data.get("BackdropImageTag")) == 0)                
                ):
            if type != "Backdrop" or (type=="Backdrop" and getSeriesData==True and data.get("ParentBackdropImageTags") == None) or (type=="Backdrop" and getSeriesData!=True):
                artwork=''        
        
        return artwork

    def imageUrl(self, id, type, index, width, height):

        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        server = WINDOW.getProperty('server%s' % username)
        # For people image - actors, directors, writers
        return "%s/mediabrowser/Items/%s/Images/%s?MaxWidth=%s&MaxHeight=%s&Index=%s" % (server, id, type, width, height, index)
    
    def getUserArtwork(self, data, type, index = "0"):

        # Load user information set by UserClient
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        server = WINDOW.getProperty('server%s' % username)
        id = data.get("Id")

        artwork = "%s/mediabrowser/Users/%s/Images/%s?Format=original" % (server, id, type)
       
        return artwork  
        