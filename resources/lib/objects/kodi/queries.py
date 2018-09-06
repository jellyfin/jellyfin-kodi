
''' Queries for the Kodi database. obj reflect key/value to retrieve from emby items.
    Some functions require additional information, therefore obj do not always reflect
    the Kodi database query values.
'''
create_path =   		"""	SELECT	coalesce(max(idPath), 0) 
							FROM 	path 
						"""
create_file =   		"""	SELECT	coalesce(max(idFile), 0) 
							FROM	files 
						"""
create_person =      	""" SELECT 	coalesce(max(actor_id), 0) 
						 	FROM	actor 
					 	"""
create_genre =  		"""	SELECT	coalesce(max(genre_id), 0) 
							FROM	genre 
						"""
create_studio =     	"""	SELECT	coalesce(max(studio_id), 0) 
							FROM	studio 
						"""
create_bookmark =   	"""	SELECT	coalesce(max(idBookmark), 0) 
							FROM	bookmark 
						"""
create_tag =    		"""	SELECT	coalesce(max(tag_id), 0) 
							FROM	tag 
						"""
create_unique_id =  	"""	SELECT	coalesce(max(uniqueid_id), 0) 
							FROM	uniqueid 
						"""
create_rating =     	"""	SELECT	coalesce(max(rating_id), 0) 
							FROM	rating 
						"""
create_movie =  		"""	SELECT	coalesce(max(idMovie), 0) 
							FROM	movie 
						"""
create_set =    		"""	SELECT	coalesce(max(idSet), 0) 
							FROM	sets 
						"""
create_country =    	"""	SELECT	coalesce(max(country_id), 0) 
							FROM	country 
						"""
create_musicvideo = 	""" SELECT	coalesce(max(idMVideo), 0) 
							FROM	musicvideo 
						"""
create_tvshow =     	"""	SELECT	coalesce(max(idShow), 0) 
							FROM	tvshow 
						"""
create_season =     	"""	SELECT	coalesce(max(idSeason), 0) 
							FROM	seasons 
						"""
create_episode =    	"""	SELECT	coalesce(max(idEpisode), 0) 
							FROM	episode 
						"""


get_path =  			"""	SELECT	idPath 
							FROM	path 
							WHERE	strPath = ? 
						"""
get_path_obj =              [   "{Path}"
                            ]
get_file =  			"""	SELECT	idFile 
							FROM	files 
							WHERE	idPath = ? 
							AND		strFilename = ? 
						"""
get_file_obj =              [   "{FileId}"
                            ]
get_filename =  		"""	SELECT	strFilename 
							FROM	files 
							WHERE	idFile = ? 
						"""
get_person =    		"""	SELECT	actor_id 
							FROM	actor 
							WHERE	name = ? 
							COLLATE NOCASE 
						"""
get_genre =     		"""	SELECT	genre_id 
							FROM	genre 
							WHERE	name = ? 
							COLLATE NOCASE 
						"""
get_studio =    		""" SELECT	studio_id 
							FROM	studio 
							WHERE 	name = ? 
							COLLATE NOCASE 
						"""
get_tag =   			"""	SELECT	tag_id 
							FROM	tag 
							WHERE	name = ? 
							COLLATE NOCASE 
						"""
get_tag_movie_obj =         [   "{MovieId}", "Favorite movies", "movie"
                            ]
get_tag_mvideo_obj =        [   "{MvideoId}", "Favorite musicvideos", "musicvideo"
                            ]
get_tag_episode_obj =       [   "{KodiId}", "Favorite tvshows", "tvshow"
                            ]
get_art =   			"""	SELECT	url 
							FROM	art 
							WHERE 	media_id = ? 
							AND 	media_type = ? 
							AND 	type = ? 
						"""
get_movie =     		"""	SELECT	* 
							FROM	movie 
							WHERE	idMovie = ? 
						"""
get_movie_obj =             [   "{MovieId}"
                            ]
get_rating =    		"""	SELECT 	rating_id 
							FROM 	rating 
							WHERE 	media_type = ? 
							AND 	media_id = ? 
						"""
get_rating_movie_obj =      [   "movie","{MovieId}"
                            ]
get_rating_episode_obj =    [   "episode","{EpisodeId}"
                            ]
get_unique_id =     	"""	SELECT 	uniqueid_id 
							FROM 	uniqueid 
							WHERE 	media_type = ? 
							AND 	media_id = ? 
						"""
get_unique_id_movie_obj =   [   "movie","{MovieId}"
                            ]
get_unique_id_tvshow_obj =  [   "tvshow","{ShowId}"
                            ]
get_unique_id_episode_obj = [   "episode","{EpisodeId}"
                            ]
get_country =   		"""	SELECT	country_id 
							FROM 	country 
							WHERE 	name = ? 
							COLLATE NOCASE 
						"""
get_set =   			"""	SELECT 	idSet 
							FROM 	sets 
							WHERE 	strSet = ? 
							COLLATE NOCASE 
						"""
get_musicvideo =    	"""	SELECT 	* 
							FROM 	musicvideo 
							WHERE 	idMVideo = ? 
						"""
get_musicvideo_obj =        [   "{MvideoId}"
                            ]
get_tvshow =    		"""	SELECT 	* 
							FROM	tvshow 
							WHERE 	idShow = ? 
						"""
get_tvshow_obj =            [   "{ShowId}"
                            ]
get_episode =   		"""	SELECT 	* 
							FROM 	episode 
							WHERE 	idEpisode = ? 
						"""
get_episode_obj =           [   "{EpisodeId}"
                            ]
get_season =    		"""	SELECT 	idSeason 
            				FROM 	seasons
            				WHERE 	idShow = ? 
            				AND 	season = ? 
            			"""
get_season_obj =            [   "{Title}","{ShowId}","{Index}"
                            ]
get_season_special_obj =    [   None,"{ShowId}",-1
                            ]
get_season_episode_obj =    [   None,"{ShowId}","{Season}"
                            ]
get_backdrops =     	"""	SELECT	url 
    						FROM	art 
    						WHERE 	media_id = ? 
    						AND 	media_type = ? 
    						AND 	type LIKE ?
    					"""
get_art =   			"""	SELECT 	url 
   							FROM 	art 
   							WHERE 	media_id = ? 
   							AND 	media_type = ? 
   							AND 	type = ? 
   						"""
get_art_url =   		""" SELECT 	url, type 
   							FROM	art 
   							WHERE	media_id = ? 
   							AND 	media_type = ? 
   						"""
get_show_by_unique_id = """ SELECT  idShow 
                            FROM    tvshow_view 
                            WHERE   uniqueid_value = ? 
                        """

get_total_episodes =    """ SELECT  totalCount 
                            FROM    tvshowcounts 
                            WHERE   idShow = ?
                        """
get_total_episodes_obj =    [   "{ParentId}"
                            ]



add_path =  			"""	INSERT INTO	path(idPath, strPath) 
							VALUES		(?, ?) 
						"""
add_path_obj =              [   "{Path}"
                            ]
add_file =  			"""	INSERT INTO	files(idFile, idPath, strFilename) 
							VALUES		(?, ?, ?) 
						"""
add_file_obj =              [   "{PathId}","{Filename}"
                            ]
add_person =    		""" INSERT INTO	actor(actor_id, name) 
							VALUES		(?, ?) 
						"""
add_people_movie_obj =      [   "{People}","{MovieId}","movie"
                            ]
add_people_mvideo_obj =     [   "{People}","{MvideoId}","musicvideo"
                            ]
add_people_tvshow_obj =     [   "{People}","{ShowId}","tvshow"
                            ]
add_people_episode_obj =    [   "{People}","{EpisodeId}","episode"
                            ]
add_actor_link =    	"""	INSERT INTO	actor_link(actor_id, media_id, media_type, role, cast_order) 
							VALUES		(?, ?, ?, ?, ?) 
						"""
add_link =  			"""	INSERT INTO	{LinkType}(actor_id, media_id, media_type) 
							VALUES		(?, ?, ?) 
						"""
add_genre =     		"""	INSERT INTO	genre(genre_id, name) 
							VALUES		(?, ?) 
						"""
add_genres_movie_obj =      [   "{Genres}","{MovieId}","movie"
                            ]
add_genres_mvideo_obj =     [   "{Genres}","{MvideoId}","musicvideo"
                            ]
add_genres_tvshow_obj =     [   "{Genres}","{ShowId}","tvshow"
                            ]
add_studio =    		"""	INSERT INTO	studio(studio_id, name) 
							VALUES		(?, ?) 
						"""
add_studios_movie_obj =     [   "{Studios}","{MovieId}","movie"
                            ]
add_studios_mvideo_obj =    [   "{Studios}","{MvideoId}","musicvideo"
                            ]
add_studios_tvshow_obj =    [   "{Studios}","{ShowId}","tvshow"
                            ]
add_bookmark =  		"""	INSERT INTO	bookmark(idBookmark, idFile, timeInSeconds, totalTimeInSeconds, player, type)
							VALUES		(?, ?, ?, ?, ?, ?)
						"""
add_bookmark_obj =          [   "{FileId}","{PlayCount}","{DatePlayed}","{Resume}","{Runtime}","DVDPlayer",1
                            ]
add_streams_obj =           [   "{FileId}","{Streams}","{Runtime}"
                            ]
add_stream_video =  	"""	INSERT INTO	streamdetails(idFile, iStreamType, strVideoCodec, fVideoAspect, iVideoWidth,
													  iVideoHeight, iVideoDuration, strStereoMode)
							VALUES		(?, ?, ?, ?, ?, ?, ?, ?)
						"""
add_stream_video_obj =      [   "{FileId}",0,"{codec}","{aspect}","{width}","{height}","{Runtime}","{3d}"
                            ]
add_stream_audio =  	"""	INSERT INTO	streamdetails(idFile, iStreamType, strAudioCodec, iAudioChannels, strAudioLanguage)
							VALUES		(?, ?, ?, ?, ?)
						"""
add_stream_audio_obj =      [   "{FileId}",1,"{codec}","{channels}","{language}"
                            ]
add_stream_sub =    	"""	INSERT INTO streamdetails(idFile, iStreamType, strSubtitleLanguage)
							VALUES		(?, ?, ?)
						"""
add_stream_sub_obj =        [   "{FileId}",2,"{language}"
                            ]
add_tag =   			"""	INSERT INTO tag(tag_id, name) 
							VALUES		(?, ?)
						"""
add_tags_movie_obj =        [   "{Tags}","{MovieId}","movie"
                            ]
add_tags_mvideo_obj =       [   "{Tags}","{MvideoId}","musicvideo"
                            ]
add_tags_tvshow_obj =       [   "{Tags}","{ShowId}","tvshow"
                            ]
add_art =   			"""	INSERT INTO	art(media_id, media_type, type, url) 
							VALUES		(?, ?, ?, ?) 
						"""
add_movie =     		"""	INSERT INTO	movie(idMovie, idFile, c00, c01, c02, c03, c04, c05, c06, c07,
                							  c09, c10, c11, c12, c14, c15, c16, c18, c19, c21, premiered) 
                			VALUES 		(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
                		"""
add_movie_obj =             [   "{MovieId}","{FileId}","{Title}","{Plot}","{ShortPlot}","{Tagline}",
                                "{Votes}","{RatingId}","{Writers}","{Year}","{Unique}","{SortTitle}",
                                "{Runtime}","{Mpaa}","{Genre}","{Directors}","{Title}","{Studio}",
                                "{Trailer}","{Country}","{Year}"
                            ]
add_rating =    		"""	INSERT INTO rating(rating_id, media_id, media_type, rating_type, rating, votes) 
    						VALUES 		(?, ?, ?, ?, ?, ?) 
    					"""
add_rating_movie_obj =      [   "{RatingId}","{MovieId}","movie","default","{Rating}","{Votes}"
                            ]
add_rating_tvshow_obj =     [   "{RatingId}","{ShowId}","tvshow","default","{Rating}","{Votes}"
                            ]
add_rating_episode_obj =    [   "{RatingId}","{EpisodeId}","episode","default","{Rating}","{Votes}"
                            ]
add_unique_id =     	"""	INSERT INTO	uniqueid(uniqueid_id, media_id, media_type, value, type) 
    						VALUES 		(?, ?, ?, ?, ?)
    					"""
add_unique_id_movie_obj =   [   "{Unique}","{MovieId}","movie","{UniqueId}","{ProviderName}"
                            ]
add_unique_id_tvshow_obj =  [   "{Unique}","{ShowId}","tvshow","{UniqueId}","{ProviderName}"
                            ]
add_unique_id_episode_obj = [   "{Unique}","{EpisodeId}","episode","{UniqueId}","{ProviderName}"
                            ]
add_country =   		"""	INSERT INTO country(country_id, name) 
   							VALUES		(?, ?) 
   						"""
add_set =   			"""	INSERT INTO sets(idSet, strSet, strOverview) 
   							VALUES 		(?, ?, ?) 
   						"""
add_set_obj =               [   "{Title}","{Overview}"
                            ]
add_musicvideo =    	"""	INSERT INTO musicvideo(idMVideo,idFile, c00, c04, c05, c06, c07, c08, c09, c10, 
   												   c11, c12, premiered) 
            				VALUES 		(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
            			"""
add_musicvideo_obj =        [   "{MvideoId}","{FileId}","{Title}","{Runtime}","{Directors}","{Studio}","{Year}",
                                "{Plot}","{Album}","{Artists}","{Genre}","{Index}","{Premiere}"
                            ]
add_tvshow =    		""" INSERT INTO	tvshow(idShow, c00, c01, c04, c05, c08, c09, c12, c13, c14, c15) 
            				VALUES 		(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
            			"""
add_tvshow_obj =            [   "{ShowId}","{Title}","{Plot}","{RatingId}","{Premiere}","{Genre}","{Title}",
                                "{Unique}","{Mpaa}","{Studio}","{SortTitle}"
                            ]
add_season =    		"""	INSERT INTO seasons(idSeason, idShow, season) 
    						VALUES 		(?, ?, ?) 
    					"""
add_episode =   		"""	INSERT INTO episode(idEpisode, idFile, c00, c01, c03, c04, c05, c09, c10, c12, c13, c14,
                								idShow, c15, c16, idSeason) 
                			VALUES 		(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
                		"""
add_episode_obj =           [   "{EpisodeId}","{FileId}","{Title}","{Plot}","{RatingId}","{Writers}","{Premiere}","{Runtime}",
                                "{Directors}","{Season}","{Index}","{Title}","{ShowId}","{AirsBeforeSeason}",
                                "{AirsBeforeEpisode}","{SeasonId}"
                            ]                        
add_art =   			"""	INSERT INTO art(media_id, media_type, type, url) 
    						VALUES 		(?, ?, ?, ?) 
    					"""



update_path =   		"""	UPDATE 	path 
							SET 	strPath = ?, strContent = ?, strScraper = ?, noUpdate = ? 
							WHERE	idPath = ? 
						"""
update_path_movie_obj =     [   "{Path}","movies","metadata.local",1,"{PathId}"
                            ]
update_path_toptvshow_obj = [   "{TopLevel}","tvshows","metadata.local",1,"{TopPathId}"
                            ]
update_path_tvshow_obj =    [   "{Path}",None,None,1,"{PathId}"
                            ]
update_path_episode_obj =   [   "{Path}",None,None,1,"{PathId}"
                            ]
update_path_mvideo_obj =    [   "{Path}","musicvideos","metadata.local",1,"{PathId}"
                            ]
update_file =   		"""	UPDATE 	files 
							SET 	idPath = ?, strFilename = ?, dateAdded = ? 
							WHERE 	idFile = ? 
						"""
update_file_obj =           [   "{PathId}","{Filename}","{DateAdded}","{FileId}"
                            ]
update_genres =     	"""	INSERT OR REPLACE INTO	genre_link(genre_id, media_id, media_type) 
							VALUES					(?, ?, ?) 
						"""
update_studios =    	"""	INSERT OR REPLACE INTO	studio_link(studio_id, media_id, media_type) 
							VALUES					(?, ?, ?) 
						"""
update_playcount =  	"""	UPDATE 	files 
							SET 	playCount = ?, lastPlayed = ? 
							WHERE 	idFile = ? 
						"""
update_tag =    		"""	INSERT OR REPLACE INTO	tag_link(tag_id, media_id, media_type)
							VALUES					(?, ?, ?)
						"""
update_art =    		"""	UPDATE 	art 
							SET 	url = ? 
							WHERE 	media_id = ? 
							AND 	media_type = ? 
							AND 	type = ? 
						"""
update_actor =  		"""	INSERT OR REPLACE INTO	actor_link(actor_id, media_id, media_type, role, cast_order) 
							VALUES					(?, ?, ?, ?, ?) 
						"""

update_link =   		""" INSERT OR REPLACE INTO	{LinkType}(actor_id, media_id, media_type) 
							VALUES					(?, ?, ?)
						"""
update_movie =  		"""	UPDATE 	movie 
							SET 	c00 = ?, c01 = ?, c02 = ?, c03 = ?, c04 = ?, c05 = ?, c06 = ?,
                					c07 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c14 = ?, c15 = ?,
                					c16 = ?, c18 = ?, c19 = ?, c21 = ?, premiered = ? 
                			WHERE 	idMovie = ? 
                		"""
update_movie_obj =          [   "{Title}","{Plot}","{ShortPlot}","{Tagline}","{Votes}","{RatingId}",
                                "{Writers}","{Year}","{Unique}","{SortTitle}","{Runtime}",
                                "{Mpaa}","{Genre}","{Directors}","{Title}","{Studio}","{Trailer}",
                                "{Country}","{Year}","{MovieId}"
                            ]
update_rating =     	"""	UPDATE 	rating 
    						SET 	media_id = ?, media_type = ?, rating_type = ?, rating = ?, votes = ? 
    						WHERE 	rating_id = ?
    					"""
update_rating_movie_obj =   [   "{MovieId}","movie","default","{Rating}","{Votes}","{RatingId}"
                            ]
update_rating_tvshow_obj =  [   "{ShowId}","tvshow","default","{Rating}","{Votes}","{RatingId}"
                            ]
update_rating_episode_obj = [   "{EpisodeId}","episode","default","{Rating}","{Votes}","{RatingId}"
                            ]
update_unique_id =  	"""	UPDATE 	uniqueid 
    						SET 	media_id = ?, media_type = ?, value = ?, type = ? 
    						WHERE 	uniqueid_id = ? 
    					"""
update_unique_id_movie_obj =    [   "{MovieId}","movie","{UniqueId}","{ProviderName}","{Unique}"
                                ]
update_unique_id_tvshow_obj =   [   "{ShowId}","tvshow","{UniqueId}","{ProviderName}","{Unique}"
                                ]
update_unique_id_episode_obj =  [   "{EpisodeId}","episode","{UniqueId}","{ProviderName}","{Unique}"
                                ]
update_country =    	"""	INSERT OR REPLACE INTO 	country_link(country_id, media_id, media_type) 
   							VALUES					(?, ?, ?)
   						"""
update_country_obj =        [   "{Countries}","{MovieId}","movie"
                            ]
update_set =    		"""	UPDATE 	sets 
   							SET 	strSet = ?, strOverview = ?  
   							WHERE 	idSet = ? 
   						"""
update_set_obj =            [   "{Title}", "{Overview}", "{SetId}"
                            ]
update_movie_set =  	"""	UPDATE 	movie 
   							SET 	idSet = ? 
   							WHERE 	idMovie = ? 
   						"""
update_movie_set_obj =      [   "{SetId}","{MovieId}"
                            ]
update_musicvideo = 	""" UPDATE 	musicvideo 
            				SET 	c00 = ?, c04 = ?, c05 = ?, c06 = ?, c07 = ?, c08 = ?, c09 = ?, c10 = ?, 
                					c11 = ?, c12 = ?, premiered = ? 
            				WHERE 	idMVideo = ? 
            			"""
update_musicvideo_obj =     [   "{Title}","{Runtime}","{Directors}","{Studio}","{Year}","{Plot}","{Album}",
                                "{Artists}","{Genre}","{Index}","{Premiere}","{MvideoId}"
                            ]
update_tvshow =     	""" UPDATE 	tvshow 
            				SET 	c00 = ?, c01 = ?, c04 = ?, c05 = ?, c08 = ?, c09 = ?, 
                					c12 = ?, c13 = ?, c14 = ?, c15 = ? 
            				WHERE 	idShow = ? 
            			"""
update_tvshow_obj =         [   "{ShowId}","{Title}","{Plot}","{RatingId}","{Premiere}","{Genre}","{Title}",
                                "{Unique}","{Mpaa}","{Studio}","{SortTitle}"
                            ]
update_tvshow_link =   	"""	INSERT OR REPLACE INTO	tvshowlinkpath(idShow, idPath) 
    						VALUES 					(?, ?) 
    					"""
update_tvshow_link_obj =    [   "{ShowId}","{PathId}"
                            ]
update_season =     	"""	UPDATE 	seasons 
    						SET 	name = ? 
    						WHERE 	idSeason = ? 
    					"""
update_episode =    	""" UPDATE 	episode 
            				SET 	c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?, 
                					c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, idSeason = ?, idShow = ? 
            				WHERE 	idEpisode = ? 
            			"""
update_episode_obj =        [   "{Title}","{Plot}","{RatingId}","{Writers}","{Premiere}","{Runtime}","{Directors}",
                                "{Season}","{Index}","{Title}","{AirsBeforeSeason}","{AirsBeforeEpisode}","{SeasonId}",
                                "{ShowId}","{EpisodeId}"
                            ]



delete_path =   		"""	DELETE FROM	path 
							WHERE		idPath = ? 
						"""
delete_path_obj =           [   "{PathId}"
                            ]
delete_file =   		"""	DELETE FROM	files 
							WHERE		idFile = ? 
						"""
delete_file_obj =           [   "{Path}","{Filename}"
                            ]
delete_file_by_path =	"""	DELETE FROM	files 
							WHERE		idPath = ? 
							AND			strFileName = ? 
						"""
delete_genres =     	"""	DELETE FROM	genre_link 
							WHERE		media_id = ? 
							AND 		media_type = ?
						"""
delete_bookmark =   	"""	DELETE FROM	bookmark 
							WHERE 		idFile = ?
						"""
delete_streams =    	"""	DELETE FROM	streamdetails
							WHERE		idFile = ?
						"""
delete_tags =   		"""	DELETE FROM	tag_link 
							WHERE		media_id = ? 
							AND 		media_type = ? 
						"""
delete_tag =    		"""	DELETE FROM	tag_link 
							WHERE		tag_id = ?
							AND 		media_type = ? 
							AND 		media_id = ?
						"""
delete_tag_movie_obj =      [   "{MovieId}","Favorite movies","movie"
                            ]
delete_tag_mvideo_obj =     [   "{MvideoId}","Favorite musicvideos","musicvideo"
                            ]
delete_tag_episode_obj =    [   "{KodiId}","Favorite tvshows","tvshow"
                            ]
delete_movie =  		"""	DELETE FROM	movie 
							WHERE		idMovie = ? 
						"""
delete_movie_obj =          [   "{KodiId}","{FileId}"
                            ]
delete_set =    		"""	DELETE FROM	sets 
							WHERE 		idSet = ? 
						"""
delete_set_obj =            [   "{KodiId}"
                            ]
delete_movie_set =  	"""	UPDATE 	movie 
							SET 	idSet = null 
							WHERE 	idMovie = ? 
						"""
delete_movie_set_obj =      [   "{MovieId}"
                            ]
delete_musicvideo = 	"""	DELETE FROM	musicvideo 
							WHERE 		idMVideo = ? 
						"""
delete_musicvideo_obj =     [   "{MvideoId}", "{FileId}"
                            ]
delete_tvshow =     	""" DELETE FROM	tvshow 
							WHERE 		idShow = ? 
						"""
delete_season =     	""" DELETE FROM seasons 
							WHERE 		idSeason = ? 
						"""
delete_episode =    	"""	DELETE FROM	episode 
							WHERE 		idEpisode = ? 
						"""
delete_backdrops =  	"""	DELETE FROM	art 
							WHERE 		media_id = ? 
							AND 		media_type = ? 
							AND 		type LIKE ? 
						"""
