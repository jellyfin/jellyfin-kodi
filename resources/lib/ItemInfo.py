
import sys
import xbmc
import xbmcgui
import xbmcaddon
import json as json
import urllib
from DownloadUtils import DownloadUtils
from API import API


_MODE_BASICPLAY=12
_MODE_CAST_LIST=14
_MODE_PERSON_DETAILS=15
CP_ADD_URL = 'plugin://plugin.video.couchpotato_manager/movies/add?title='
CP_ADD_VIA_IMDB = 'plugin://plugin.video.couchpotato_manager/movies/add?imdb_id='


class ItemInfo(xbmcgui.WindowXMLDialog):

    id = ""
    playUrl = ""
    trailerUrl = ""
    couchPotatoUrl = ""
    userid = ""
    server = ""
    downloadUtils = DownloadUtils()
    item= []
    isTrailer = False
    
    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
        xbmc.log("WINDOW INITIALISED")

    def onInit(self):
        self.action_exitkeys_id = [10, 13]
        url = "{server}/mediabrowser/Users/{UserId}/Items/" + self.id + "?Fields=SeriesGenres,AirTime&format=json"
        item = self.downloadUtils.downloadUrl(url)     
        self.item = item
        
        id = item.get("Id")
        WINDOW = xbmcgui.Window( 10025 )
        WINDOW.setProperty('ItemGUID', id)
        
        name = item.get("Name")
        image = API().getArtwork(item, "poster")
        fanArt = API().getArtwork(item, "BackdropNoIndicators")
        self.getControl(3001).setImage(fanArt)
        
        discart = API().getArtwork(item ,"Disc")
        logo = API().getArtwork(item ,"Logo")
        # calculate the percentage complete
        userData = item.get("UserData")
        cappedPercentage = 0
        
        if(userData != None):
            playBackTicks = float(userData.get("PlaybackPositionTicks"))
            if(playBackTicks != None and playBackTicks > 0):
                runTimeTicks = float(item.get("RunTimeTicks", "0"))
                if(runTimeTicks > 0):
                    percentage = int((playBackTicks / runTimeTicks) * 100.0)
                    cappedPercentage = percentage - (percentage % 10)
                    if(cappedPercentage == 0):
                        cappedPercentage = 10
                    if(cappedPercentage == 100):
                        cappedPercentage = 90
            
            try:
                watchedButton = self.getControl(3192)
            except:
                watchedButton = None
            if(watchedButton != None):
                if userData.get("Played") == True:
                    watchedButton.setSelected(True)
                else:
                    watchedButton.setSelected(False)
            
            try:
                dislikeButton = self.getControl(3193)
            except:
                dislikeButton = None            
            if(dislikeButton != None):
                if userData.get("Likes") != None and userData.get("Likes") == False:
                    dislikeButton.setSelected(True)
                else:
                    dislikeButton.setSelected(False)
                    
            try:
                likeButton = self.getControl(3194)
            except:
                likeButton = None                       
            if(likeButton != None):
                if userData.get("Likes") != None and userData.get("Likes") == True:
                    likeButton.setSelected(True)
                else:
                    likeButton.setSelected(False)
                    
            try:
                favouriteButton = self.getControl(3195)
            except:
                favouriteButton = None
            if(favouriteButton != None):
                if userData.get("IsFavorite") == True:
                    favouriteButton.setSelected(True)
                else:
                    favouriteButton.setSelected(False)
          
        
        episodeInfo = ""
        type = item.get("Type")
        WINDOW.setProperty('ItemType', type)
        if(type == "Episode" or type == "Season"):
            WINDOW.setProperty('ItemGUID', item.get("SeriesId"))
            name = item.get("SeriesName") + ": " + name
            season = str(item.get("ParentIndexNumber")).zfill(2)
            episodeNum = str(item.get("IndexNumber")).zfill(2)
            episodeInfo = "S" + season + "xE" + episodeNum
        elif type == "Movie":
            if item.get("Taglines") != None and item.get("Taglines") != [] and item.get("Taglines")[0] != None:
                episodeInfo = item.get("Taglines")[0]
        elif type == "ChannelVideoItem":
            if item.get("ExtraType") != None:
                if item.get('ExtraType') == "Trailer":
                    self.isTrailer = True
                
            
        self.playUrl = "plugin://plugin.video.emby/?id=%s&mode=playnow" % id
            
        try:
            trailerButton = self.getControl(3102)
            if(trailerButton != None):
                if not self.isTrailer and item.get("LocalTrailerCount") != None and item.get("LocalTrailerCount") > 0:
                    itemTrailerUrl = "{server}/mediabrowser/Users/{UserId}/Items/" + id + "/LocalTrailers?format=json"
                    jsonData = self.downloadUtils.downloadUrl(itemTrailerUrl)
                    if(jsonData != ""): 
                        trailerItem = jsonData
                        self.trailerUrl = "plugin://plugin.video.emby/trailer/?id=%s&mode=playnow" % trailerItem[0][u'Id'] 
                else:
                    trailerButton.setEnabled(False)
        except:
            pass
        
        try:
            couchPotatoButton = self.getControl(3103)
            if(couchPotatoButton != None):
                if self.isTrailer and item.get("ProviderIds") != None and item.get("ProviderIds").get("Imdb") != None:
                    self.couchPotatoUrl = CP_ADD_VIA_IMDB + item.get("ProviderIds").get("Imdb")
                elif self.isTrailer:
                    self.couchPotatoUrl = CP_ADD_URL + name
                elif not self.isTrailer:
                    couchPotatoButton.setEnabled(False)
        except:
            pass

        # all the media stream info
        mediaList = self.getControl(3220)
        
        mediaStreams = item.get("MediaStreams")
        if(mediaStreams != None):
            for mediaStream in mediaStreams:
                if(mediaStream.get("Type") == "Video"):
                    videocodec = mediaStream.get("Codec")
                    if(videocodec == "mpeg2video"):
                        videocodec = "mpeg2"
                    height = str(mediaStream.get("Height"))
                    width = str(mediaStream.get("Width"))
                    aspectratio = mediaStream.get("AspectRatio")
                    fr = mediaStream.get("RealFrameRate")
                    videoInfo = width + "x" + height + " " + videocodec + " " + str(round(fr, 2))
                    listItem = xbmcgui.ListItem("Video:", videoInfo)
                    mediaList.addItem(listItem)
                if(mediaStream.get("Type") == "Audio"):
                    audiocodec = mediaStream.get("Codec")
                    channels = mediaStream.get("Channels")
                    lang = mediaStream.get("Language")
                    audioInfo = audiocodec + " " + str(channels)
                    if(lang != None and len(lang) > 0 and lang != "und"):
                        audioInfo = audioInfo + " " + lang
                    listItem = xbmcgui.ListItem("Audio:", audioInfo)
                    mediaList.addItem(listItem)
                if(mediaStream.get("Type") == "Subtitle"):
                    lang = mediaStream.get("Language")
                    codec = mediaStream.get("Codec")
                    subInfo = codec
                    if(lang != None and len(lang) > 0 and lang != "und"):
                        subInfo = subInfo + " " + lang
                    listItem = xbmcgui.ListItem("Sub:", subInfo)
                    mediaList.addItem(listItem)

        
        #for x in range(0, 10):
        #    listItem = xbmcgui.ListItem("Test:", "Test 02 " + str(x))
        #    mediaList.addItem(listItem)
        
        # add overview
        overview = item.get("Overview")
        self.getControl(3223).setText(overview)
        
        # add people
        peopleList = self.getControl(3230)
        people = item.get("People")
        director=''
        writer=''
        for person in people:
            displayName = person.get("Name")
            if person.get("Role") != None and person.get("Role") != '':
               role = "as " + person.get("Role")
            else:
               role = ''
            id = person.get("Id")
            tag = person.get("PrimaryImageTag")
            
            baseName = person.get("Name")
            baseName = baseName.replace(" ", "+")
            baseName = baseName.replace("&", "_")
            baseName = baseName.replace("?", "_")
            baseName = baseName.replace("=", "_")
            
            actionUrl = "plugin://plugin.video.emby?mode=person&name=" + baseName
            
            if(tag != None and len(tag) > 0):
                thumbPath = self.downloadUtils.imageUrl(id, "Primary", 0, 400, 400)
                listItem = xbmcgui.ListItem(label=displayName, label2=role, iconImage=thumbPath, thumbnailImage=thumbPath)
            else:
                listItem = xbmcgui.ListItem(label=displayName, label2=role)
                
            listItem.setProperty("ActionUrl", actionUrl)
            peopleList.addItem(listItem)
            if(person.get("Type") == "Director") and director =='':
                director = displayName
                if(tag != None and len(tag) > 0):
                  thumbPath = self.downloadUtils.imageUrl(id, "Primary", 0, 580, 860)
                  directorlistItem = xbmcgui.ListItem("Director:", label2=displayName, iconImage=thumbPath, thumbnailImage=thumbPath)
                else:
                  directorlistItem = xbmcgui.ListItem("Director:", label2=displayName)
                directorlistItem.setProperty("ActionUrl", actionUrl)  
            if(person.get("Type") == "Writing") and writer == '':
                writer = person.get("Name")
                if(tag != None and len(tag) > 0):
                  thumbPath = self.downloadUtils.imageUrl(id, "Primary", 0, 580, 860)
                  writerlistItem = xbmcgui.ListItem("Writer:", label2=displayName, iconImage=thumbPath, thumbnailImage=thumbPath)
                else:
                  writerlistItem = xbmcgui.ListItem("Writer:", label2=displayName)
                writerlistItem.setProperty("ActionUrl", actionUrl) 
            if(person.get("Type") == "Writer") and writer == '':
                writer = person.get("Name")    
                if(tag != None and len(tag) > 0):
                  thumbPath = self.downloadUtils.imageUrl(id, "Primary", 0, 580, 860)
                  writerlistItem = xbmcgui.ListItem("Writer:", label2=displayName, iconImage=thumbPath, thumbnailImage=thumbPath)
                else:
                  writerlistItem = xbmcgui.ListItem("Writer:", label2=displayName)
                writerlistItem.setProperty("ActionUrl", actionUrl)
        # add general info
        infoList = self.getControl(3226)
        listItem = xbmcgui.ListItem("Year:", str(item.get("ProductionYear")))
        infoList.addItem(listItem)
        listItem = xbmcgui.ListItem("Rating:", str(item.get("CommunityRating")))
        infoList.addItem(listItem)          
        listItem = xbmcgui.ListItem("MPAA:", str(item.get("OfficialRating")))
        infoList.addItem(listItem)   
        duration = str(int(item.get("RunTimeTicks", "0"))/(10000000*60))
        listItem = xbmcgui.ListItem("RunTime:", str(duration) + " Minutes")
        infoList.addItem(listItem) 
         
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

        genrelistItem = xbmcgui.ListItem("Genre:", genre)
        genrelistItem2 = xbmcgui.ListItem("Genre:", genre)
        infoList.addItem(genrelistItem) 
        
        path = item.get('Path')
        pathlistItem = xbmcgui.ListItem("Path:", path)
        pathlistItem2 = xbmcgui.ListItem("Path:", path)  
        infoList.addItem(pathlistItem)
       
        if item.get("CriticRating") != None:
            listItem = xbmcgui.ListItem("CriticRating:", str(item.get("CriticRating")))
            infoList.addItem(listItem)
               
        # Process Studio
        studio = "" 
        if item.get("SeriesStudio") != None and item.get("SeriesStudio") != '':
            studio = item.get("SeriesStudio")
        if studio == "":        
            studios = item.get("Studios")
            if(studios != None):
                for studio_string in studios:
                    if studio=="": #Just take the first one
                        temp=studio_string.get("Name")
                        studio=temp.encode('utf-8')
        
        if studio != "":
            listItem = xbmcgui.ListItem("Studio:", studio)
            infoList.addItem(listItem)
        
        if item.get("Metascore") != None:
          listItem = xbmcgui.ListItem("Metascore:", str(item.get("Metascore")))
          infoList.addItem(listItem)
          
        playCount = 0
        if(userData != None and userData.get("Played") == True):
            playCount = 1
        listItem = xbmcgui.ListItem("PlayedCount:", str(playCount))
        infoList.addItem(listItem)
        
        if item.get("ProviderIds") != None and item.get("ProviderIds").get("Imdb") != None and type == "Movie":
            listItem = xbmcgui.ListItem("ID:", item.get("ProviderIds").get("Imdb"))
            infoList.addItem(listItem)
        elif item.get("ProviderIds") != None and item.get("ProviderIds").get("Tvdb") != None and type == "Series":
            listItem = xbmcgui.ListItem("ID:", item.get("ProviderIds").get("Tvdb"))
            infoList.addItem(listItem)
        elif (type == "Episode" or type == "Season"):
            url = "{server}/mediabrowser/Users/{UserId}/Items/" + item.get("SeriesId") + "?Fields=SeriesGenres,AirTime&format=json"
            seriesitem = self.downloadUtils.downloadUrl(url)     
        
            if seriesitem.get("ProviderIds") != None and seriesitem.get("ProviderIds").get("Tvdb") != None:
              listItem = xbmcgui.ListItem("ID:", seriesitem.get("ProviderIds").get("Tvdb"))
              infoList.addItem(listItem)
        
        # alternate list 
        try:
            alternateList = self.getControl(3291)
            if alternateList != None:
                if directorlistItem != None:
                   alternateList.addItem(directorlistItem)
                if writerlistItem != None:
                   alternateList.addItem(writerlistItem)
                alternateList.addItem(genrelistItem2)
                if item.get("ProductionLocations") !=None and item.get("ProductionLocations") != []:
                   listItem = xbmcgui.ListItem("Country:", item.get("ProductionLocations")[0])
                   alternateList.addItem(listItem)
                elif item.get("AirTime") !=None:
                   listItem = xbmcgui.ListItem("Air Time:", item.get("AirTime"))
                   alternateList.addItem(listItem)
                if(item.get("PremiereDate") != None):
                   premieredatelist = (item.get("PremiereDate")).split("T")
                   premieredate = premieredatelist[0]
                   listItem = xbmcgui.ListItem("Premiered Date:", premieredate)
                   alternateList.addItem(listItem)
                alternateList.addItem(pathlistItem2)
                
        except:
            pass     

        self.getControl(3000).setLabel(name)
        self.getControl(3003).setLabel(episodeInfo)
        
        try:
            discartImageControl = self.getControl(3091)
            artImageControl = self.getControl(3092)
            thumbImageControl = self.getControl(3093)
            logoImageControl = self.getControl(3094)
            
            if discartImageControl != None and artImageControl != None and thumbImageControl != None and logoImageControl != None:
                
                if logo != "":
                  self.getControl(3094).setImage(logo)
                else:
                  self.getControl(3000).setVisible(True)
                     
                if discart != '':
                  self.getControl(3091).setImage(discart)
                  self.getControl(3092).setVisible(False)
                  self.getControl(3093).setVisible(False)
                else:
                  self.getControl(3091).setVisible(False)
                  art = API().getArtwork(item,"Art")
                  if (artImageControl != None):
                      if art != '':
                          self.getControl(3092).setImage(art)
                          self.getControl(3093).setVisible(False)
                      else:
                          self.getControl(3092).setVisible(False)
                          if (type == "Episode"):
                              thumb = API().getArtwork(item,"Thumb3")
                          else:
                              thumb = API().getArtwork(item,"Thumb")
                          if (thumbImageControl != None):
                              if thumb != '':
                                  self.getControl(3093).setImage(thumb)
                              else:
                                  self.getControl(3093).setVisible(False)
                          
                  
        except:
            pass 
        
        if(type == "Episode"):
            # null_pointer - I have removed this in favor of letting the user chose from the setting and using the "poster" type in the above image url create
            #image = API().getArtwork(seriesitem, "Primary")
            seriesimage = API().getArtwork(item, "SeriesPrimary")
            try:
                self.getControl(3099).setImage(seriesimage)
                self.getControl(3009).setImage(image)
            
            except:
                pass
            
            if(cappedPercentage != None):
                self.getControl(3010).setImage("Progress\progress_" + str(cappedPercentage) + ".png")
        else:
            self.getControl(3011).setImage(image)
            if(cappedPercentage != None):
                self.getControl(3012).setImage("Progress\progress_" + str(cappedPercentage) + ".png")
                
        # disable play button
        if(type == "Season" or type == "Series"):
            self.setFocusId(3226)
            self.getControl(3002).setEnabled(False)                 
        
    def setId(self, id):
        self.id = id
        
    def onFocus(self, controlId):      
        pass
        
    def doAction(self):
        pass

    def closeDialog(self):
        self.close()
        
    def onClick(self, controlID):
        
        if(controlID == 3002):
           
            # close all dialogs when playing an item
            xbmc.executebuiltin("Dialog.Close(all,true)")
            
            xbmc.executebuiltin("RunPlugin(" + self.playUrl + ")")
            self.close()
            
        elif(controlID == 3102):
           
            # close all dialogs when playing an item
            xbmc.executebuiltin("Dialog.Close(all,true)")
            
            xbmc.executebuiltin("RunPlugin(" + self.trailerUrl + ")")
            self.close()
            
        elif(controlID == 3103):
           
            # close all dialogs when playing an item
            xbmc.executebuiltin("Dialog.Close(all,true)")
            xbmc.executebuiltin("RunPlugin(" + self.couchPotatoUrl + ")")
            
        elif(controlID == 3230):
        
            peopleList = self.getControl(3230)
            item = peopleList.getSelectedItem()
            action = item.getProperty("ActionUrl")
            
            xbmc.log(action)
            xbmc.executebuiltin("RunPlugin(" + action + ")")
        elif(controlID == 3291):
        
            list = self.getControl(3291)
            item = list.getSelectedItem()
            action = item.getProperty("ActionUrl")
            
            xbmc.log(action)
            xbmc.executebuiltin("RunPlugin(" + action + ")")
        elif(controlID == 3192):
            url =  '{server}/mediabrowser/Users/{UserId}/PlayedItems/' + self.id           
            button = self.getControl(3192)
            watched = button.isSelected()
            if watched == True:
                self.postUrl(url)
            else:
                self.deleteUrl(url)
            self.onInit()
        elif(controlID == 3193):
            url =     '{server}/mediabrowser/Users/{UserId}/Items/' + self.id + '/Rating'        
            dislikebutton = self.getControl(3193)
            dislike = dislikebutton.isSelected()
            if dislike == True:
                url = url + '?likes=false'
                self.postUrl(url)
            else:
                self.deleteUrl(url)
            self.onInit()
        elif(controlID == 3194):
            url =     '{server}/mediabrowser/Users/{UserId}/Items/' + self.id + '/Rating'        
            likebutton = self.getControl(3194)
            like = likebutton.isSelected()
            if like == True:
                url = url + '?likes=true'
                self.postUrl(url)
            else:
                self.deleteUrl(url)
            self.onInit()
        elif(controlID == 3195):
            url = '{server}/mediabrowser/Users/{UserId}/FavoriteItems/' + self.id           
            button = self.getControl(3195)
            favourite = button.isSelected()
            if favourite == True:
                self.postUrl(url)
            else:
                self.deleteUrl(url)
            self.onInit()
        elif(controlID == 3006):                   
            url = "{server}/mediabrowser/Users/{UserId}/PlayingItems/" + self.id + "/Progress?PositionTicks=0"
            self.postUrl(url)
            self.onInit()
        pass
    
    def postUrl (self,url):
        self.downloadUtils.downloadUrl(url, postBody="", type="POST")  
    
    def deleteUrl (self,url):
        self.downloadUtils.downloadUrl(url, type="DELETE")
        
