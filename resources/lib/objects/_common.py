# -*- coding: utf-8 -*-

##################################################################################################

import logging
import os

import xbmc
import xbmcvfs

import api
import artwork
import downloadutils
import read_embyserver as embyserver
from ga_client import GoogleAnalytics
from utils import window, settings, dialog, language as lang, should_stop

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
ga = GoogleAnalytics()

##################################################################################################

def catch_except(errors=(Exception, ), default_value=False):
# Will wrap method with try/except and print parameters for easier debugging
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except errors as error:
                errStrings = ga.formatException()
                ga.sendEventData("Exception", errStrings[0], errStrings[1])
                log.exception(error)
                log.error("function: %s \n args: %s \n kwargs: %s",
                          func.__name__, args, kwargs)
                return default_value

        return wrapper
    return decorator


class Items(object):

    pdialog = None
    title = None
    count = 0
    total = 0


    def __init__(self):

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()
        self.do_url = downloadutils.DownloadUtils().downloadUrl
        self.should_stop = should_stop

        self.kodi_version = int(xbmc.getInfoLabel('System.BuildVersion')[:2])
        self.direct_path = settings('useDirectPaths') == "1"
        self.content_msg = settings('newContent') == "true"

    @classmethod
    def path_validation(cls, path):
        # Verify if direct path is accessible or not
        verify_path = path
        if not os.path.supports_unicode_filenames:
            verify_path = path.encode('utf-8')

        if window('emby_pathverified') != "true" and not xbmcvfs.exists(verify_path):
            if dialog(type_="yesno",
                      heading="{emby}",
                      line1="%s %s. %s" % (lang(33047), path, lang(33048))):

                window('emby_shouldStop', value="true")
                return False

        return True

    def content_pop(self, name):
        # It's possible for the time to be 0. It should be considered disabled in this case.
        if not self.pdialog and self.content_msg and self.new_time:
            dialog(type_="notification",
                   heading="{emby}",
                   message="%s %s" % (lang(33049), name),
                   icon="{emby}",
                   time=self.new_time,
                   sound=False)

    def update_pdialog(self):

        if self.pdialog:
            percentage = int((float(self.count) / float(self.total))*100)
            self.pdialog.update(percentage, message=self.title)

    def add_all(self, item_type, items, view=None):

        if self.should_stop():
            return False

        total = items['TotalRecordCount'] if 'TotalRecordCount' in items else len(items)
        items = items['Items'] if 'Items' in items else items

        if self.pdialog and view:
            self.pdialog.update(heading="Processing %s / %s items" % (view['name'], total))

        process = self._get_func(item_type, "added")
        if view:
            process(items, total, view)
        else:
            process(items, total)

    def process_all(self, item_type, action, items, total=None, view=None):

        log.debug("Processing %s: %s", action, items)

        process = self._get_func(item_type, action)
        self.total = total or len(items)
        self.count = 0

        for item in items:

            if self.should_stop():
                return False

            if not process:
                continue

            self.title = item.get('Name', "unknown")
            self.update_pdialog()

            process(item)
            self.count += 1

    def remove_all(self, item_type, items):

        log.debug("Processing removal: %s", items)

        process = self._get_func(item_type, "remove")
        for item in items:
            process(item)

    def added(self, items, total=None, update=True):
        # Generator for newly added content
        if update:
            self.total = total or len(items)
            self.count = 0

        for item in items:

            if self.should_stop():
                break

            self.title = item.get('Name', "unknown")

            yield item
            self.update_pdialog()

            if update:
                self.count += 1

    def compare(self, item_type, items, compare_to, view=None):

        view_name = view['name'] if view else item_type

        update_list = self._compare_checksum(items, compare_to)
        log.info("Update for %s: %s", view_name, update_list)

        if self.should_stop():
            return False

        emby_items = self.emby.getFullItems(update_list)
        total = len(update_list)

        if self.pdialog:
            self.pdialog.update(heading="Processing %s / %s items" % (view_name, total))

        # Process additions and updates
        if emby_items:
            self.process_all(item_type, "update", emby_items, total, view)
        # Process deletes
        if compare_to:
            self.remove_all(item_type, compare_to.items())

        return True

    def _compare_checksum(self, items, compare_to):

        update_list = list()

        for item in items:

            if self.should_stop():
                break

            item_id = item['Id']

            if compare_to.get(item_id) != api.API(item).get_checksum():
                # Only update if item is not in Kodi or checksum is different
                update_list.append(item_id)

            compare_to.pop(item_id, None)

        return update_list
