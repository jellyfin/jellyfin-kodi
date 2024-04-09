# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

from . import settings, LazyLogger

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class API(object):
    def __init__(self, item, server=None):

        ''' Get item information in special cases.
            server is the server address, provide if your functions requires it.
        '''
        self.item = item
        self.server = server

    def get_playcount(self, played, playcount):

        ''' Convert Jellyfin played/playcount into
            the Kodi equivalent. The playcount is tied to the watch status.
        '''
        return (playcount or 1) if played else None

    def get_naming(self):

        if self.item['Type'] == 'Episode' and 'SeriesName' in self.item:
            return "%s: %s" % (self.item['SeriesName'], self.item['Name'])

        elif self.item['Type'] == 'MusicAlbum' and 'AlbumArtist' in self.item:
            return "%s: %s" % (self.item['AlbumArtist'], self.item['Name'])

        elif self.item['Type'] == 'Audio' and self.item.get('Artists'):
            return "%s: %s" % (self.item['Artists'][0], self.item['Name'])

        return self.item['Name']

    def get_actors(self):
        cast = []

        if 'People' in self.item:
            self.get_people_artwork(self.item['People'])

            for person in self.item['People']:

                if person['Type'] == "Actor":
                    cast.append({
                        'name': person['Name'],
                        'role': person.get('Role', "Unknown"),
                        'order': len(cast) + 1,
                        'thumbnail': person['imageurl']
                    })

        return cast

    def media_streams(self, video, audio, subtitles):
        return {
            'video': video or [],
            'audio': audio or [],
            'subtitle': subtitles or []
        }

    def video_streams(self, tracks, container=None):

        if container:
            container = container.split(',')[0]

        for track in tracks:

            if "DvProfile" in track:
                track['hdrtype'] = "dolbyvision"
            elif track.get('VideoRangeType', '') in ["HDR10", "HDR10Plus"]:
                track['hdrtype'] = "hdr10"
            elif "HLG" in track.get('VideoRangeType', ''):
                track['hdrtype'] = "hlg"

            track.update({
                'hdrtype': track.get('hdrtype', "").lower(),
                'codec': track.get('Codec', "").lower(),
                'profile': track.get('Profile', "").lower(),
                'height': track.get('Height'),
                'width': track.get('Width'),
                '3d': self.item.get('Video3DFormat'),
                'aspect': 1.85
            })

            if "msmpeg4" in track['codec']:
                track['codec'] = "divx"

            elif "mpeg4" in track['codec'] and ("simple profile" in track['profile'] or not track['profile']):
                track['codec'] = "xvid"

            elif "h264" in track['codec'] and container in ('mp4', 'mov', 'm4v'):
                track['codec'] = "avc1"

            try:
                width, height = self.item.get('AspectRatio', track.get('AspectRatio', "0")).split(':')
                track['aspect'] = round(float(width) / float(height), 6)
            except (ValueError, ZeroDivisionError):

                if track['width'] and track['height']:
                    track['aspect'] = round(float(track['width'] / track['height']), 6)

            track['duration'] = self.get_runtime()

        return tracks

    def audio_streams(self, tracks):

        for track in tracks:

            track.update({
                'codec': track.get('Codec', "").lower(),
                'profile': track.get('Profile', "").lower(),
                'channels': track.get('Channels'),
                'language': track.get('Language')
            })

            if "dts-hd ma" in track['profile']:
                track['codec'] = "dtshd_ma"

            elif "dts-hd hra" in track['profile']:
                track['codec'] = "dtshd_hra"

        return tracks

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

    def validate_studio(self, studio_name):
        # Convert studio for Kodi to properly detect them
        studios = {
            'abc (us)': "ABC",
            'fox (us)': "FOX",
            'mtv (us)': "MTV",
            'showcase (ca)': "Showcase",
            'wgn america': "WGN",
            'bravo (us)': "Bravo",
            'tnt (us)': "TNT",
            'comedy central': "Comedy Central (US)"
        }
        return studios.get(studio_name.lower(), studio_name)

    def get_overview(self, overview=None):

        overview = overview or self.item.get('Overview')

        if not overview:
            return

        overview = overview.replace("\"", "\'")
        overview = overview.replace("\n", "[CR]")
        overview = overview.replace("\r", " ")
        overview = overview.replace("<br>", "[CR]")

        return overview

    def get_mpaa(self, rating=None):

        mpaa = rating or self.item.get('OfficialRating', "")

        if mpaa in ("NR", "UR"):
            # Kodi seems to not like NR, but will accept Not Rated
            mpaa = "Not Rated"

        if "FSK-" in mpaa:
            mpaa = mpaa.replace("-", " ")

        return mpaa

    def get_file_path(self, path=None):

        if path is None:
            path = self.item.get('Path')

        if not path:
            return ""

        if path.startswith('\\\\'):
            path = path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

        if 'Container' in self.item:

            if self.item['Container'] == 'dvd':
                path = "%s/VIDEO_TS/VIDEO_TS.IFO" % path
            elif self.item['Container'] == 'bluray':
                path = "%s/BDMV/index.bdmv" % path

        path = path.replace('\\\\', "\\")

        if '\\' in path:
            path = path.replace('/', "\\")

        if '://' in path:
            protocol = path.split('://')[0]
            path = path.replace(protocol, protocol.lower())

        return path

    def get_user_artwork(self, user_id):

        ''' Get jellyfin user profile picture.
        '''
        return "%s/Users/%s/Images/Primary?Format=original" % (self.server, user_id)

    def get_people_artwork(self, people):

        ''' Get people (actor, director, etc) artwork.
        '''
        for person in people:

            if 'PrimaryImageTag' in person:

                query = "&MaxWidth=400&MaxHeight=400&Index=0"
                person['imageurl'] = self.get_artwork(person['Id'], "Primary", person['PrimaryImageTag'], query)
            else:
                person['imageurl'] = None

        return people

    def get_all_artwork(self, obj, parent_info=False):

        ''' Get all artwork possible. If parent_info is True,
            it will fill missing artwork with parent artwork.

            obj is from objects.Objects().map(item, 'Artwork')
        '''
        query = ""
        all_artwork = {
            'Primary': "",
            'BoxRear': "",
            'Art': "",
            'Banner': "",
            'Logo': "",
            'Thumb': "",
            'Disc': "",
            'Backdrop': []
        }

        if settings('compressArt.bool'):
            query = "&Quality=90"

        if not settings('enableCoverArt.bool'):
            query += "&EnableImageEnhancers=false"

        art_maxheight = [360, 480, 600, 720, 1080, -1]
        maxheight = art_maxheight[int(settings('maxArtResolution') or 5)]
        if maxheight != -1:
            query += "&MaxHeight=%d" % maxheight

        all_artwork['Backdrop'] = self.get_backdrops(obj['Id'], obj['BackdropTags'] or [], query)

        for artwork in (obj['Tags'] or []):
            all_artwork[artwork] = self.get_artwork(obj['Id'], artwork, obj['Tags'][artwork], query)

        if parent_info:

            if not all_artwork['Backdrop'] and obj['ParentBackdropId']:
                all_artwork['Backdrop'] = self.get_backdrops(obj['ParentBackdropId'], obj['ParentBackdropTags'], query)

            for art in ('Logo', 'Art', 'Thumb'):
                if not all_artwork[art] and obj['Parent%sId' % art]:
                    all_artwork[art] = self.get_artwork(obj['Parent%sId' % art], art, obj['Parent%sTag' % art], query)

            if obj.get('SeriesTag'):
                all_artwork['Series.Primary'] = self.get_artwork(obj['SeriesId'], "Primary", obj['SeriesTag'], query)

                if not all_artwork['Primary']:
                    all_artwork['Primary'] = all_artwork['Series.Primary']

            elif not all_artwork['Primary'] and obj.get('AlbumId'):
                all_artwork['Primary'] = self.get_artwork(obj['AlbumId'], "Primary", obj['AlbumTag'], query)

        return all_artwork

    def get_backdrops(self, item_id, tags, query=None):

        ''' Get backdrops based of "BackdropImageTags" in the jellyfin object.
        '''
        backdrops = []

        if item_id is None:
            return backdrops

        for index, tag in enumerate(tags):

            artwork = "%s/Items/%s/Images/Backdrop/%s?Format=original&Tag=%s%s" % (self.server, item_id, index, tag, (query or ""))
            backdrops.append(artwork)

        return backdrops

    def get_artwork(self, item_id, image, tag=None, query=None):

        ''' Get any type of artwork: Primary, Art, Banner, Logo, Thumb, Disc
        '''
        if item_id is None:
            return ""

        url = "%s/Items/%s/Images/%s/0?Format=original" % (self.server, item_id, image)

        if tag is not None:
            url += "&Tag=%s" % tag

        if query is not None:
            url += query or ""

        return url
