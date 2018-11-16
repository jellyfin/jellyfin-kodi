# -*- coding: utf-8 -*-

#################################################################################################

client = None

#################################################################################################

def _http(action, url, request={}):
    request.update({'type': action, 'handler': url})

    return  client.request(request)

def _get(handler, params=None):
    return  _http("GET", handler, {'params': params})

def _post(handler, json=None, params=None):
    return  _http("POST", handler, {'params': params, 'json': json})

def _delete(handler, params=None):
    return  _http("DELETE", handler, {'params': params})

def emby_url(handler):
    return  "%s/emby/%s" % (client.config['auth.server'], handler)

def basic_info():
    return  "Etag"

def info():
    return  (
                "Path,Genres,SortName,Studios,Writer,Taglines,LocalTrailerCount,"
                "OfficialRating,CumulativeRunTimeTicks,ItemCounts,"
                "Metascore,AirTime,DateCreated,People,Overview,"
                "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
                "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,"
                "MediaSources,VoteCount,RecursiveItemCount,PrimaryImageAspectRatio"
            )

def music_info():
    return  (
                "Etag,Genres,SortName,Studios,Writer,"
                "OfficialRating,CumulativeRunTimeTicks,Metascore,"
                "AirTime,DateCreated,MediaStreams,People,ProviderIds,Overview,ItemCounts"
            )

#################################################################################################

# Bigger section of the Emby api

#################################################################################################

def try_server():
    return  _get("System/Info/Public")

def sessions(handler="", action="GET", params=None, json=None):

    if action == "POST":
        return  _post("Sessions%s" % handler, json, params)
    elif action == "DELETE":
        return  _delete("Sessions%s" % handler, params)
    else:
        return  _get("Sessions%s" % handler, params)

def users(handler="", action="GET", params=None, json=None):

    if action == "POST":
        return  _post("Users/{UserId}%s" % handler, json, params)
    elif action == "DELETE":
        return  _delete("Users/{UserId}%s" % handler, params)
    else:
        return  _get("Users/{UserId}%s" % handler, params)

def items(handler="", action="GET", params=None, json=None):
    
    if action == "POST":
        return  _post("Items%s" % handler, json, params)
    elif action == "DELETE":
        return  _delete("Items%s" % handler, params)
    else:
        return  _get("Items%s" % handler, params)

def user_items(handler="", params=None):
    return  users("/Items%s" % handler, params=params)

def shows(handler, params):
    return  _get("Shows%s" % handler, params)

def videos(handler):
    return  _get("Videos%s" % handler)

def artwork(item_id, art, max_width, ext="jpg", index=None):

    if index is None:
        return  emby_url("Items/%s/Images/%s?MaxWidth=%s&format=%s" % (item_id, art, max_width, ext))

    return emby_url("Items/%s/Images/%s/%s?MaxWidth=%s&format=%s" % (item_id, art, index, max_width, ext))

#################################################################################################

# More granular api

#################################################################################################

def get_users():
    return  _get("Users")

def get_public_users():
    return  _get("Users/Public")

def get_user(user_id=None):
    return  users() if user_id is None else _get("Users/%s" % user_id)

def get_views():
    return  users("/Views")

def get_media_folders():
    return  users("/Items")

def get_item(item_id):
    return  users("/Items/%s" % item_id)

def get_items(item_ids):
    return  users("/Items", params={
                'Ids': ','.join(str(x) for x in item_ids),
                'Fields': info()
            })

def get_sessions():
    return  sessions(params={'ControllableByUserId': "{UserId}"})

def get_device(device_id):
    return  sessions(params={'DeviceId': device_id})

def post_session(session_id, url, params=None, data=None):
    return  sessions("/%s/%s" % (session_id, url), "POST", params, data)

def get_images(item_id):
    return  items("/%s/Images" % item_id)

def get_suggestion(media="Movie,Episode", limit=1):
    return  users("/Suggestions", {
                'Type': media,
                'Limit': limit
            })

def get_recently_added(media=None, parent_id=None, limit=20):
    return  user_items("/Latest", {
                'Limit': limit,
                'UserId': "{UserId}",
                'IncludeItemTypes': media,
                'ParentId': parent_id,
                'Fields': info()
            })

def get_next(index=None, limit=1):
    return  shows("/NextUp", {
                'Limit': limit,
                'UserId': "{UserId}",
                'StartIndex': None if index is None else int(index)
            })

def get_adjacent_episodes(show_id, item_id):
    return  shows("/%s/Episodes" % show_id, {
                'UserId': "{UserId}",
                'AdjacentTo': item_id,
                'Fields': "Overview"
            })

def get_genres(parent_id=None):
    return  _get("Genres", {
                'ParentId': parent_id,
                'UserId': "{UserId}",
                'Fields': info()
            })

def get_recommendation(parent_id=None, limit=20):
    return  _get("Movies/Recommendations", {
                'ParentId': parent_id,
                'UserId': "{UserId}",
                'Fields': info(),
                'Limit': limit
            })

def get_items_by_letter(parent_id=None, media=None, letter=None):
    return  user_items(params={
                'ParentId': parent_id,
                'NameStartsWith': letter,
                'Fields': info(),
                'Recursive': True,
                'IncludeItemTypes': media
            })

def get_channels():
    return  _get("LiveTv/Channels", {
                'UserId': "{UserId}",
                'EnableImages': True,
                'EnableUserData': True
            })

def get_intros(item_id):
    return  user_items("/%s/Intros" % item_id)

def get_additional_parts(item_id):
    return  videos("/%s/AdditionalParts" % item_id)

def delete_item(item_id):
    return  items("/%s" % item_id, "DELETE")

def get_local_trailers(item_id):
    return  user_items("/%s/LocalTrailers" % item_id)

def get_transcode_settings():
    return  _get('System/Configuration/encoding')

def get_ancestors(item_id):
    return  items("/%s/Ancestors" % item_id, params={
                'UserId': "{UserId}"
            })

def get_items_theme_video(parent_id):
    return  users("/Items", params={
                'HasThemeVideo': True,
                'ParentId': parent_id
            })

def get_themes(item_id):
    return  items("/%s/ThemeMedia" % item_id, params={
                'UserId': "{UserId}",
                'InheritFromParent': True
            })

def get_items_theme_song(parent_id):
    return  users("/Items", params={
                'HasThemeSong': True,
                'ParentId': parent_id
            })

def get_plugins():
    return  _get("Plugins")

def get_seasons(show_id):
    return  shows("/%s/Seasons" % show_id, params={
                'UserId': "{UserId}",
                'EnableImages': True,
                'Fields': info()
            })

def get_date_modified(date, parent_id, media=None):
    return  users("/Items", params={
                'ParentId': parent_id,
                'Recursive': False,
                'IsMissing': False,
                'IsVirtualUnaired': False,
                'IncludeItemTypes': media or None,
                'MinDateLastSaved': date,
                'Fields': info()
            })

def get_userdata_date_modified(date, parent_id, media=None):
    return  users("/Items", params={
                'ParentId': parent_id,
                'Recursive': True,
                'IsMissing': False,
                'IsVirtualUnaired': False,
                'IncludeItemTypes': media or None,
                'MinDateLastSavedForUser': date,
                'Fields': info()
            })

def refresh_item(item_id):
    return  items("/%s/Refresh" % item_id, "POST", json={
                'Recursive': True,
                'ImageRefreshMode': "FullRefresh",
                'MetadataRefreshMode': "FullRefresh",
                'ReplaceAllImages': False,
                'ReplaceAllMetadata': True
            })

def favorite(item_id, option=True):
    return  users("/FavoriteItems/%s" % item_id, "POST" if option else "DELETE")

def get_system_info():
    return  _get("System/Configuration")

def post_capabilities(data):
    return  sessions("/Capabilities/Full", "POST", json=data)

def session_add_user(session_id, user_id, option=True):
    return  sessions("/%s/Users/%s" % (session_id, user_id), "POST" if option else "DELETE")

def session_playing(data):
    return  sessions("/Playing", "POST", json=data)

def session_progress(data):
    return  sessions("/Playing/Progress", "POST", json=data)

def session_stop(data):
    return  sessions("/Playing/Stopped", "POST", json=data)

def item_played(item_id, watched):
    return  users("/PlayedItems/%s" % item_id, "POST" if watched else "DELETE")

def get_sync_queue(date, filters=None):
    return  _get("Emby.Kodi.SyncQueue/{UserId}/GetItems", params={
                'LastUpdateDT': date,
                'filter': filters or None
            })

def get_server_time():
    return  _get("Emby.Kodi.SyncQueue/GetServerDateTime")

def get_play_info(item_id, profile):
    return  items("/%s/PlaybackInfo" % item_id, "POST", json={
                'UserId': "{UserId}",
                'DeviceProfile': profile,
                'AutoOpenLiveStream': True
            })

def get_live_stream(item_id, play_id, token, profile):
    return  _post("LiveStreams/Open", json={
                'UserId': "{UserId}",
                'DeviceProfile': profile,
                'OpenToken': token,
                'PlaySessionId': play_id,
                'ItemId': item_id
            })

def close_live_stream(live_id):
    return  _post("LiveStreams/Close", json={
                'LiveStreamId': live_id
            })

def close_transcode(device_id):
    return  _delete("Videos/ActiveEncodings", params={
                'DeviceId': device_id
            })

def delete_item(item_id):
    return  items("/%s" % item_id, "DELETE")
