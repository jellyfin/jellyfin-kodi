
get_item =              """ SELECT  kodi_id, kodi_fileid, kodi_pathid, parent_id, media_type, 
						            emby_type, media_folder, emby_parent_id  
				            FROM	emby 
				            WHERE 	emby_id = ? 
			            """
get_item_obj =              [   "{Id}"
                            ]
get_item_series_obj =       [   "{SeriesId}"
                            ]
get_item_song_obj =         [   "{SongAlbumId}"
                            ]
get_item_id_by_parent =	""" SELECT 	emby_id, kodi_id 
							FROM 	emby 
							WHERE 	parent_id = ? 
							AND 	media_type = ? 
						"""
get_item_id_by_parent_boxset_obj =  [   "{SetId}","movie"
                                    ]
get_item_by_parent =    """ SELECT  emby_id, kodi_id, kodi_fileid
                            FROM    emby 
                            WHERE   parent_id = ? 
                            AND     media_type = ? 
                        """
get_item_by_media_folder =  """ SELECT  emby_id, emby_type 
                                FROM    emby 
                                WHERE   media_folder = ? 
                            """
get_item_by_parent_movie_obj =  [   "{KodiId}","movie"
                                ]
get_item_by_parent_tvshow_obj = [   "{ParentId}","tvshow"
                                ]
get_item_by_parent_season_obj = [   "{ParentId}","season"
                                ]
get_item_by_parent_episode_obj =    [   "{ParentId}","episode"
                                    ]
get_item_by_parent_album_obj =  [   "{ParentId}","album"
                                ]
get_item_by_parent_song_obj =   [   "{ParentId}","song"
                                ]
get_item_by_wild =      """	SELECT 	kodi_id, media_type 
							FROM 	emby 
							WHERE 	emby_id LIKE ? 
						"""
get_item_by_wild_obj =          [   "{Id}"
                                ]
get_item_by_kodi =	    """	SELECT 	emby_id, parent_id, media_folder, emby_type, checksum 
							FROM 	emby 
							WHERE 	kodi_id = ? 
							AND 	media_type = ? 
						"""
get_checksum =	     	"""	SELECT 	emby_id, checksum 
							FROM 	emby 
							WHERE 	emby_type = ? 
						"""
get_view_name =         """ SELECT  view_name 
                            FROM    view 
                            WHERE   view_id = ? 
                        """
get_media_by_id =       """ SELECT  emby_type 
                            FROM    emby 
                            WHERE   emby_id = ? 
                        """
get_media_by_parent_id =    """ SELECT  emby_id, emby_type, kodi_id, kodi_fileid  
                                FROM    emby 
                                WHERE   emby_parent_id = ?
                            """
get_view =              """ SELECT  view_name, media_type 
                            FROM    view 
                            WHERE   view_id = ?
                        """
get_views =             """ SELECT  *
                            FROM    view
                        """
get_views_by_media =    """ SELECT  * 
                            FROM    view 
                            WHERE   media_type = ? 
                        """
get_items_by_media =    """ SELECT  emby_id 
                            FROM    emby 
                            WHERE   media_type = ?
                        """
get_version =           """ SELECT  idVersion 
                            FROM    version
                        """



add_reference =	        """	INSERT OR REPLACE INTO	emby(emby_id, kodi_id, kodi_fileid, kodi_pathid, emby_type, 
														 media_type, parent_id, checksum, media_folder, emby_parent_id) 
                			VALUES 					(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
                		"""
add_reference_movie_obj =   [   "{Id}","{MovieId}","{FileId}","{PathId}","Movie","movie", None,"{Checksum}","{LibraryId}",
                                "{EmbyParentId}"
                            ]
add_reference_boxset_obj =  [   "{Id}","{SetId}",None,None,"BoxSet","set",None,"{Checksum}",None,None
                            ]
add_reference_tvshow_obj =  [   "{Id}","{ShowId}",None,"{PathId}","Series","tvshow",None,"{Checksum}","{LibraryId}",
                                "{EmbyParentId}"
                            ]
add_reference_season_obj =  [   "{Id}","{SeasonId}",None,None,"Season","season","{ShowId}",None,None,None
                            ]
add_reference_pool_obj =    [   "{SeriesId}","{ShowId}",None,"{PathId}","Series","tvshow",None,"{Checksum}","{LibraryId}",None
                            ]
add_reference_episode_obj = [   "{Id}","{EpisodeId}","{FileId}","{PathId}","Episode","episode","{SeasonId}","{Checksum}",
                                None,"{EmbyParentId}"
                            ]
add_reference_mvideo_obj =  [   "{Id}","{MvideoId}","{FileId}","{PathId}","MusicVideo","musicvideo",None,"{Checksum}",
                                "{LibraryId}","{EmbyParentId}"
                            ]
add_reference_artist_obj =  [   "{Id}","{ArtistId}",None,None,"{ArtistType}","artist",None,"{Checksum}","{LibraryId}",
                                "{EmbyParentId}"
                            ]
add_reference_album_obj =   [   "{Id}","{AlbumId}",None,None,"MusicAlbum","album",None,"{Checksum}",None,"{EmbyParentId}"
                            ]
add_reference_song_obj =    [   "{Id}","{SongId}",None,"{PathId}","Audio","song","{AlbumId}","{Checksum}",
                                None,"{EmbyParentId}"
                            ]
add_view =              """ INSERT OR REPLACE INTO  view(view_id, view_name, media_type)
                            VALUES                  (?, ?, ?)
                        """
add_version =           """ INSERT OR REPLACE INTO  version(idVersion) 
                            VALUES                  (?)
                        """


update_reference =      """	UPDATE 	emby 
    						SET 	checksum = ? 
    						WHERE 	emby_id = ?
    					"""
update_reference_obj =      [   "{Checksum}", "{Id}"
                            ]
update_parent =     	"""	UPDATE 	emby 
    						SET 	parent_id = ? 
    						WHERE 	emby_id = ? 
    					"""
update_parent_movie_obj =  [   "{SetId}","{Id}"
                            ]
update_parent_episode_obj =  [   "{SeasonId}","{Id}"
                            ]
update_parent_album_obj =   [   "{ArtistId}","{AlbumId}"]



delete_item =		    """	DELETE FROM emby 
    						WHERE 		emby_id = ? 
    					"""
delete_item_obj =           [   "{Id}"
                            ]
delete_item_by_parent =	""" DELETE FROM	emby 
    						WHERE 		parent_id = ? 
    						AND 		media_type = ?
    					"""
delete_item_by_parent_tvshow_obj =  [   "{ParentId}","tvshow"
                                    ]
delete_item_by_parent_season_obj =  [   "{ParentId}","season"
                                    ]
delete_item_by_parent_episode_obj = [   "{ParentId}","episode"
                                    ]
delete_item_by_parent_song_obj =    [   "{ParentId}","song"
                                    ]
delete_item_by_parent_artist_obj =  [   "{ParentId}","artist"
                                    ]
delete_item_by_parent_album_obj =   [   "{KodiId}","album"
                                    ]
delete_item_by_kodi =	"""	DELETE FROM	emby 
    						WHERE 		kodi_id = ? 
    						AND 		media_type = ?
    					"""
delete_item_by_wild =	"""	DELETE FROM emby 
    						WHERE 		emby_id LIKE ? 
    					"""
delete_view =           """ DELETE FROM view 
                            WHERE       view_id = ?
                        """
delete_parent_boxset_obj = [    None, "{Movie}"
                           ]
delete_media_by_parent_id = """ DELETE FROM emby 
                                WHERE       emby_parent_id = ? 
                            """
delete_version =        """ DELETE FROM version
                        """
