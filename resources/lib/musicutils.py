# -*- coding: utf-8 -*-

#################################################################################################

import os
import xbmc, xbmcaddon, xbmcvfs
import utils
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen import id3

#################################################################################################

# Helper for the music library, intended to fix missing song ID3 tags on Emby

def logMsg(msg, lvl=1):
    utils.logMsg("%s %s" % ("Emby", "musictools"), msg, lvl)

def getRealFileName(filename):
    #get the filename path accessible by python if possible...
    isTemp = False
    
    if not xbmcvfs.exists(filename):
        logMsg( "File does not exist! %s" %(filename), 0)
        return (False, "")
    
    # determine if our python module is able to access the file directly...
    if os.path.exists(filename):
        filename = filename
    elif os.path.exists(filename.replace("smb://","\\\\").replace("/","\\")):
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
    
def getSongTags(file):
    # Get the actual ID3 tags for music songs as the server is lacking that info
    rating = None
    comment = ""
    
    isTemp,filename = getRealFileName(file)
    logMsg( "getting song ID3 tags for " + filename)
    
    try:
        if filename.lower().endswith(".flac"):
            audio = FLAC(filename)
            if audio.get("comment"):
                comment = audio.get("comment")[0]
            if audio.get("rating"):
                rating = float(audio.get("rating")[0])
                #flac rating is 0-100 and needs to be converted to 0-5 range
                if rating > 5: rating = (rating / 100) * 5
        elif filename.lower().endswith(".mp3"):
            audio = ID3(filename)
            if audio.get("comment"):
                comment = audio.get("comment")[0]
            if audio.get("POPM:Windows Media Player 9 Series"):
                if audio.get("POPM:Windows Media Player 9 Series").rating:
                    rating = float(audio.get("POPM:Windows Media Player 9 Series").rating)
                    #POPM rating is 0-255 and needs to be converted to 0-5 range
                    if rating > 5: rating = (rating / 255) * 5
        else:
            logMsg( "Not supported fileformat or unable to access file: %s" %(filename))
        rating = int(round(rating,0))
    
    except Exception as e:
        #file in use ?
        logMsg("Exception in getSongTags %s" %e,0)
        
    #remove tempfile if needed....
    if isTemp: xbmcvfs.delete(filename)
        
    return (rating, comment)

def updateRatingToFile(rating, file):
    #update the rating from Emby to the file
    
    isTemp,filename = getRealFileName(file)
    logMsg( "setting song rating: %s for filename: %s" %(rating,filename))
    
    if not filename:
        return
    
    try:
        if filename.lower().endswith(".flac"):
            audio = FLAC(filename)
            calcrating = int(round((float(rating) / 5) * 100, 0))
            audio["rating"] = str(calcrating)
            audio.save()
        elif filename.lower().endswith(".mp3"):
            audio = ID3(filename)
            calcrating = int(round((float(rating) / 5) * 255, 0))
            audio.add(id3.POPM(email="Windows Media Player 9 Series", rating=calcrating, count=1))
            audio.save()
        else:
            logMsg( "Not supported fileformat: %s" %(filename))
            
        #remove tempfile if needed....
        if isTemp:
            xbmcvfs.delete(file)
            xbmcvfs.copy(filename,file)
            xbmcvfs.delete(filename)
            
    except Exception as e:
        #file in use ?
        logMsg("Exception in updateRatingToFile %s" %e,0)
        
    
    