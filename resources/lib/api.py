# -*- coding: utf-8 -*-

# Read an api response and convert more complex cases

##################################################################################################

import logging
from utils import settings

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class API(object):

    def __init__(self, item):
        # item is the api response
        self.item = item

    def get_userdata(self):
        # Default
        favorite = False
        likes = None
        playcount = None
        played = False
        last_played = None
        resume = 0

        try:
            userdata = self.item['UserData']
        except KeyError: # No userdata found.
            pass
        else:
            favorite = userdata['IsFavorite']
            likes = userdata.get('Likes')

            last_played = userdata.get('LastPlayedDate')
            if last_played:
                last_played = last_played.split('.')[0].replace('T', " ")

            if userdata['Played']:
                # Playcount is tied to the watch status
                played = True
                playcount = userdata['PlayCount']
                if playcount == 0:
                    playcount = 1

                if last_played is None:
                    last_played = self.get_date_created()

            playback_position = userdata.get('PlaybackPositionTicks')
            if playback_position:
                resume = playback_position / 10000000.0

        return {

            'Favorite': favorite,
            'Likes': likes,
            'PlayCount': playcount,
            'Played': played,
            'LastPlayedDate': last_played,
            'Resume': resume
        }

    def get_people(self):
        # Process People
        director = []
        writer = []
        cast = []

        try:
            people = self.item['People']
        except KeyError:
            pass
        else:
            for person in people:

                type_ = person['Type']
                name = person['Name']

                if type_ == 'Director':
                    director.append(name)
                elif type_ == 'Actor':
                    cast.append(name)
                elif type_ in ('Writing', 'Writer'):
                    writer.append(name)

        return {

            'Director': director,
            'Writer': writer,
            'Cast': cast
        }

    def get_media_streams(self):

        video_tracks = []
        audio_tracks = []
        subtitle_languages = []

        try:
            media_streams = self.item['MediaSources'][0]['MediaStreams']

        except KeyError:
            if not self.item.get("MediaStreams"):
                return None
            media_streams = self.item['MediaStreams']

        for media_stream in media_streams:
            # Sort through Video, Audio, Subtitle
            stream_type = media_stream['Type']

            if stream_type == "Video":
                self._video_stream(video_tracks, media_stream)

            elif stream_type == "Audio":
                self._audio_stream(audio_tracks, media_stream)

            elif stream_type == "Subtitle":
                subtitle_languages.append(media_stream.get('Language', "Unknown"))

        return {

            'video': video_tracks,
            'audio': audio_tracks,
            'subtitle': subtitle_languages
        }

    def _video_stream(self, video_tracks, stream):

        codec = stream.get('Codec', "").lower()
        profile = stream.get('Profile', "").lower()

        # Height, Width, Codec, AspectRatio, AspectFloat, 3D
        track = {

            'codec': codec,
            'height': stream.get('Height'),
            'width': stream.get('Width'),
            'video3DFormat': self.item.get('Video3DFormat'),
            'aspect': 1.85
        }

        try:
            container = self.item['MediaSources'][0]['Container'].lower()
        except Exception:
            container = ""

        # Sort codec vs container/profile
        if "msmpeg4" in codec:
            track['codec'] = "divx"
        elif "mpeg4" in codec:
            if "simple profile" in profile or not profile:
                track['codec'] = "xvid"
        elif "h264" in codec:
            if container in ("mp4", "mov", "m4v"):
                track['codec'] = "avc1"

        # Aspect ratio
        if 'AspectRatio' in self.item:
            # Metadata AR
            aspect = self.item['AspectRatio']
        else: # File AR
            aspect = stream.get('AspectRatio', "0")

        try:
            aspect_width, aspect_height = aspect.split(':')
            track['aspect'] = round(float(aspect_width) / float(aspect_height), 6)

        except (ValueError, ZeroDivisionError):

            width = track.get('width')
            height = track.get('height')

            if width and height:
                track['aspect'] = round(float(width / height), 6)
            else:
                track['aspect'] = 1.85

        if 'RunTimeTicks' in self.item:
            track['duration'] = self.get_runtime()

        video_tracks.append(track)

    def _audio_stream(self, audio_tracks, stream):

        codec = stream.get('Codec', "").lower()
        profile = stream.get('Profile', "").lower()
        # Codec, Channels, language
        track = {

            'codec': codec,
            'channels': stream.get('Channels'),
            'language': stream.get('Language')
        }

        if "dca" in codec and "dts-hd ma" in profile:
            track['codec'] = "dtshd_ma"

        audio_tracks.append(track)

    def get_runtime(self):

        try:
            runtime = self.item['RunTimeTicks'] / 10000000.0

        except KeyError:
            runtime = self.item.get('CumulativeRunTimeTicks', 0) / 10000000.0

        return runtime

    @classmethod
    def adjust_resume(cls, resume_seconds):

        resume = 0
        if resume_seconds:
            resume = round(float(resume_seconds), 6)
            jumpback = int(settings('resumeJumpBack'))
            if resume > jumpback:
                # To avoid negative bookmark
                resume = resume - jumpback

        return resume

    def get_studios(self):
        # Process Studios
        studios = []
        try:
            studio = self.item['SeriesStudio']
            studios.append(self.verify_studio(studio))

        except KeyError:
            for studio in self.item['Studios']:

                name = studio['Name']
                studios.append(self.verify_studio(name))

        return studios

    @classmethod
    def verify_studio(cls, studio_name):
        # Convert studio for Kodi to properly detect them
        studios = {

            'abc (us)': "ABC",
            'fox (us)': "FOX",
            'mtv (us)': "MTV",
            'showcase (ca)': "Showcase",
            'wgn america': "WGN"
        }

        return studios.get(studio_name.lower(), studio_name)

    def get_checksum(self):
        # Use the etags checksum and userdata
        userdata = self.item['UserData']

        checksum = "%s%s%s%s%s%s%s" % (

            self.item['Etag'],
            userdata['Played'],
            userdata['IsFavorite'],
            userdata.get('Likes', ""),
            userdata['PlaybackPositionTicks'],
            userdata.get('UnplayedItemCount', ""),
            userdata.get('LastPlayedDate', "")
        )

        return checksum

    def get_genres(self):
        all_genres = ""
        genres = self.item.get('Genres', self.item.get('SeriesGenres'))

        if genres:
            all_genres = " / ".join(genres)

        return all_genres

    def get_date_created(self):

        try:
            date_added = self.item['DateCreated']
            date_added = date_added.split('.')[0].replace('T', " ")
        except KeyError:
            date_added = None

        return date_added

    def get_premiere_date(self):

        try:
            premiere = self.item['PremiereDate']
            premiere = premiere.split('.')[0].replace('T', " ")
        except KeyError:
            premiere = None

        return premiere

    def get_overview(self):

        try:
            overview = self.item['Overview']
            overview = overview.replace("\"", "\'")
            overview = overview.replace("\n", " ")
            overview = overview.replace("\r", " ")
        except KeyError:
            overview = ""

        return overview

    def get_tagline(self):

        try:
            tagline = self.item['Taglines'][0]
        except IndexError:
            tagline = None

        return tagline

    def get_provider(self, name):

        try:
            provider = self.item['ProviderIds'][name]
        except KeyError:
            provider = None

        return provider

    def get_mpaa(self):
        # Convert more complex cases
        mpaa = self.item.get('OfficialRating', "")

        if mpaa in ("NR", "UR"):
            # Kodi seems to not like NR, but will accept Not Rated
            mpaa = "Not Rated"

        if "FSK-" in mpaa:
            mpaa = mpaa.replace("-", " ")

        return mpaa

    def get_country(self):

        try:
            country = self.item['ProductionLocations'][0]
        except (IndexError, KeyError):
            country = None

        return country

    def get_file_path(self):

        try:
            filepath = self.item['Path']

        except KeyError:
            filepath = ""

        else:
            if "\\\\" in filepath:
                # append smb protocol
                filepath = filepath.replace("\\\\", "smb://")
                filepath = filepath.replace("\\", "/")

            if self.item.get('VideoType'):
                videotype = self.item['VideoType']
                # Specific format modification
                if 'Dvd'in videotype:
                    filepath = "%s/VIDEO_TS/VIDEO_TS.IFO" % filepath
                elif 'BluRay' in videotype:
                    filepath = "%s/BDMV/index.bdmv" % filepath

            if "\\" in filepath:
                # Local path scenario, with special videotype
                filepath = filepath.replace("/", "\\")

        return filepath
