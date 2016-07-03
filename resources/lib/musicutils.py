# -*- coding: utf-8 -*-

#################################################################################################

import os

import xbmc
import xbmcaddon
import xbmcvfs

from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3
from mutagen import id3
import base64

import read_embyserver as embyserver
from utils import Logging, window
log = Logging('MusicTools').log

#################################################################################################

# Helper for the music library, intended to fix missing song ID3 tags on Emby

def getRealFileName(filename, isTemp=False):
    #get the filename path accessible by python if possible...
    
    if not xbmcvfs.exists(filename):
        log("File does not exist! %s" % filename, 0)
        return (False, "")
    
    #if we use os.path method on older python versions (sunch as some android builds), we need to pass arguments as string
    if os.path.supports_unicode_filenames:
        checkfile = filename
    else:
        checkfile = filename.encode("utf-8")
    
    # determine if our python module is able to access the file directly...
    if os.path.exists(checkfile):
        filename = filename
    elif os.path.exists(checkfile.replace("smb://","\\\\").replace("/","\\")):
        filename = filename.replace("smb://","\\\\").replace("/","\\")
    else:
        #file can not be accessed by python directly, we copy it for processing...
        isTemp = True
        if "/" in filename: filepart = filename.split("/")[-1]
        else: filepart = filename.split("\\")[-1]
        tempfile = "special://temp/"+filepart
        xbmcvfs.copy(filename, tempfile)
        filename = xbmc.translatePath(tempfile).decode("utf-8")
        
    return (isTemp,filename)

def getEmbyRatingFromKodiRating(rating):
    # Translation needed between Kodi/ID3 rating and emby likes/favourites:
    # 3+ rating in ID3 = emby like
    # 5+ rating in ID3 = emby favourite
    # rating 0 = emby dislike
    # rating 1-2 = emby no likes or dislikes (returns 1 in results)
    favourite = False
    deletelike = False
    like = False
    if (rating >= 3): like = True
    if (rating == 0): like = False
    if (rating == 1 or rating == 2): deletelike = True
    if (rating >= 5): favourite = True
    return(like, favourite, deletelike)

def getAdditionalSongTags(embyid, emby_rating, API, kodicursor, emby_db, enableimportsongrating, enableexportsongrating, enableupdatesongrating):
    
    emby = embyserver.Read_EmbyServer()

    previous_values = None
    filename = API.getFilePath()
    rating = 0
    emby_rating = int(round(emby_rating, 0))
    
    #get file rating and comment tag from file itself.
    if enableimportsongrating:
        file_rating, comment, hasEmbeddedCover = getSongTags(filename)
    else: 
        file_rating = 0
        comment = ""
        hasEmbeddedCover = False
        

    emby_dbitem = emby_db.getItem_byId(embyid)
    try:
        kodiid = emby_dbitem[0]
    except TypeError:
        # Item is not in database.
        currentvalue = None
    else:
        query = "SELECT rating FROM song WHERE idSong = ?"
        kodicursor.execute(query, (kodiid,))
        try:
            currentvalue = int(round(float(kodicursor.fetchone()[0]),0))
        except: currentvalue = None
    
    # Only proceed if we actually have a rating from the file
    if file_rating is None and currentvalue:
        return (currentvalue, comment, False)
    elif file_rating is None and not currentvalue:
        return (emby_rating, comment, False)
    
    log("getAdditionalSongTags --> embyid: %s - emby_rating: %s - file_rating: %s - current rating in kodidb: %s" %(embyid, emby_rating, file_rating, currentvalue))
    
    updateFileRating = False
    updateEmbyRating = False

    if currentvalue != None:
        # we need to translate the emby values...
        if emby_rating == 1 and currentvalue == 2:
            emby_rating = 2
        if emby_rating == 3 and currentvalue == 4:
            emby_rating = 4
            
        #if updating rating into file is disabled, we ignore the rating in the file...
        if not enableupdatesongrating:
            file_rating = currentvalue
        #if convert emby likes/favourites convert to song rating is disabled, we ignore the emby rating...
        if not enableexportsongrating:
            emby_rating = currentvalue
            
        if (emby_rating == file_rating) and (file_rating != currentvalue):
            #the rating has been updated from kodi itself, update change to both emby ands file
            rating = currentvalue
            updateFileRating = True
            updateEmbyRating = True
        elif (emby_rating != currentvalue) and (file_rating == currentvalue):
            #emby rating changed - update the file
            rating = emby_rating
            updateFileRating = True  
        elif (file_rating != currentvalue) and (emby_rating == currentvalue):
            #file rating was updated, sync change to emby
            rating = file_rating
            updateEmbyRating = True
        elif (emby_rating != currentvalue) and (file_rating != currentvalue):
            #both ratings have changed (corner case) - the highest rating wins...
            if emby_rating > file_rating:
                rating = emby_rating
                updateFileRating = True
            else:
                rating = file_rating
                updateEmbyRating = True
        else:
            #nothing has changed, just return the current value
            rating = currentvalue
    else:      
        # no rating yet in DB
        if enableimportsongrating:
            #prefer the file rating
            rating = file_rating
            #determine if we should also send the rating to emby server
            if enableexportsongrating:
                if emby_rating == 1 and file_rating == 2:
                    emby_rating = 2
                if emby_rating == 3 and file_rating == 4:
                    emby_rating = 4
                if emby_rating != file_rating:
                    updateEmbyRating = True
                
        elif enableexportsongrating:
            #set the initial rating to emby value
            rating = emby_rating
        
    if updateFileRating and enableupdatesongrating:
        updateRatingToFile(rating, filename)
        
    if updateEmbyRating and enableexportsongrating:
        # sync details to emby server. Translation needed between ID3 rating and emby likes/favourites:
        like, favourite, deletelike = getEmbyRatingFromKodiRating(rating)
        window("ignore-update-%s" %embyid, "true") #set temp windows prop to ignore the update from webclient update
        emby.updateUserRating(embyid, favourite)
    
    return (rating, comment, hasEmbeddedCover)
        
def getSongTags(file):
    # Get the actual ID3 tags for music songs as the server is lacking that info
    rating = 0
    comment = ""
    hasEmbeddedCover = False
    
    isTemp,filename = getRealFileName(file)
    log( "getting song ID3 tags for " + filename)
    
    try:
        ###### FLAC FILES #############
        if filename.lower().endswith(".flac"):
            audio = FLAC(filename)
            if audio.get("comment"):
                comment = audio.get("comment")[0]
            for pic in audio.pictures:
                if pic.type == 3 and pic.data:
                    #the file has an embedded cover
                    hasEmbeddedCover = True
                    break
            if audio.get("rating"):
                rating = float(audio.get("rating")[0])
                #flac rating is 0-100 and needs to be converted to 0-5 range
                if rating > 5: rating = (rating / 100) * 5
        
        ###### MP3 FILES #############
        elif filename.lower().endswith(".mp3"):
            audio = ID3(filename)
            
            if audio.get("APIC:Front Cover"):
                if audio.get("APIC:Front Cover").data:
                    hasEmbeddedCover = True
            
            if audio.get("comment"):
                comment = audio.get("comment")[0]
            if audio.get("POPM:Windows Media Player 9 Series"):
                if audio.get("POPM:Windows Media Player 9 Series").rating:
                    rating = float(audio.get("POPM:Windows Media Player 9 Series").rating)
                    #POPM rating is 0-255 and needs to be converted to 0-5 range
                    if rating > 5: rating = (rating / 255) * 5
        else:
            log( "Not supported fileformat or unable to access file: %s" %(filename))
        
        #the rating must be a round value
        rating = int(round(rating,0))
    
    except Exception as e:
        #file in use ?
        log("Exception in getSongTags %s" % e,0)
        rating = None
    
    #remove tempfile if needed....
    if isTemp: xbmcvfs.delete(filename)
        
    return (rating, comment, hasEmbeddedCover)

def updateRatingToFile(rating, file):
    #update the rating from Emby to the file
    
    f = xbmcvfs.File(file)
    org_size = f.size()
    f.close()
    
    #create tempfile
    if "/" in file: filepart = file.split("/")[-1]
    else: filepart = file.split("\\")[-1]
    tempfile = "special://temp/"+filepart
    xbmcvfs.copy(file, tempfile)
    tempfile = xbmc.translatePath(tempfile).decode("utf-8")
    
    log( "setting song rating: %s for filename: %s - using tempfile: %s" %(rating,file,tempfile))
    
    if not tempfile:
        return
    
    try:
        if tempfile.lower().endswith(".flac"):
            audio = FLAC(tempfile)
            calcrating = int(round((float(rating) / 5) * 100, 0))
            audio["rating"] = str(calcrating)
            audio.save()
        elif tempfile.lower().endswith(".mp3"):
            audio = ID3(tempfile)
            calcrating = int(round((float(rating) / 5) * 255, 0))
            audio.add(id3.POPM(email="Windows Media Player 9 Series", rating=calcrating, count=1))
            audio.save()
        else:
            log( "Not supported fileformat: %s" %(tempfile))
            
        #once we have succesfully written the flags we move the temp file to destination, otherwise not proceeding and just delete the temp
        #safety check: we check the file size of the temp file before proceeding with overwite of original file
        f = xbmcvfs.File(tempfile)
        checksum_size = f.size()
        f.close()
        if checksum_size >= org_size:
            xbmcvfs.delete(file)
            xbmcvfs.copy(tempfile,file)
        else:
            log( "Checksum mismatch for filename: %s - using tempfile: %s  -  not proceeding with file overwite!" %(rating,file,tempfile))
        
        #always delete the tempfile
        xbmcvfs.delete(tempfile)
            
    except Exception as e:
        #file in use ?
        log("Exception in updateRatingToFile %s" %e,0)
        
    
    