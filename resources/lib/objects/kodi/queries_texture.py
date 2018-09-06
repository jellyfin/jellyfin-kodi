
get_cache =     	        """	SELECT	cachedurl 
					       		FROM 	texture 
				    			WHERE 	url = ? 
			     			"""



delete_cache =  			""" DELETE FROM texture 
								WHERE 		url = ? 
							"""
