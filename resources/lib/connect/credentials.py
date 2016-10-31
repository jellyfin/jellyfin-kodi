# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os
import time
from datetime import datetime

#################################################################################################

log = logging.getLogger("EMBY."+__name__.split('.')[-1])

#################################################################################################


class Credentials(object):

    _shared_state = {} # Borg
    credentials = None
    path = ""
    

    def __init__(self):
        self.__dict__ = self._shared_state

    def setPath(self, path):
        # Path to save persistant data.txt
        self.path = path

    def _ensure(self):
        
        if self.credentials is None:
            try:
                with open(os.path.join(self.path, 'data.txt')) as infile:
                    self.credentials = json.load(infile)

                if not isinstance(self.credentials, dict):
                    raise ValueError("invalid credentials format")

            except Exception as e: # File is either empty or missing
                log.warn(e)
                self.credentials = {}

            log.info("credentials initialized with: %s" % self.credentials)
            self.credentials['Servers'] = self.credentials.setdefault('Servers', [])

    def _get(self):

        self._ensure()
        return self.credentials

    def _set(self, data):

        if data:
            self.credentials = data
            # Set credentials to file
            with open(os.path.join(self.path, 'data.txt'), 'w') as outfile:
                for server in data['Servers']:
                    server['Name'] = server['Name'].encode('utf-8')
                json.dump(data, outfile, ensure_ascii=False)
        else:
            self._clear()

        log.info("credentialsupdated")

    def _clear(self):

        self.credentials = None
        # Remove credentials from file
        with open(os.path.join(self.path, 'data.txt'), 'w'): pass

    def getCredentials(self, data=None):

        if data is not None:
            self._set(data)

        return self._get()

    def addOrUpdateServer(self, list_, server):

        if server.get('Id') is None:
            raise KeyError("Server['Id'] cannot be null or empty")

        # Add default DateLastAccessed if doesn't exist.
        server.setdefault('DateLastAccessed', "2001-01-01T00:00:00Z")

        for existing in list_:
            if existing['Id'] == server['Id']:
                
                # Merge the data
                if server.get('DateLastAccessed'):
                    if self._dateObject(server['DateLastAccessed']) > self._dateObject(existing['DateLastAccessed']):
                        existing['DateLastAccessed'] = server['DateLastAccessed']

                if server.get('UserLinkType'):
                    existing['UserLinkType'] = server['UserLinkType']

                if server.get('AccessToken'):
                    existing['AccessToken'] = server['AccessToken']
                    existing['UserId'] = server['UserId']

                if server.get('ExchangeToken'):
                    existing['ExchangeToken'] = server['ExchangeToken']

                if server.get('RemoteAddress'):
                    existing['RemoteAddress'] = server['RemoteAddress']

                if server.get('ManualAddress'):
                    existing['ManualAddress'] = server['ManualAddress']

                if server.get('LocalAddress'):
                    existing['LocalAddress'] = server['LocalAddress']

                if server.get('Name'):
                    existing['Name'] = server['Name']

                if server.get('WakeOnLanInfos'):
                    existing['WakeOnLanInfos'] = server['WakeOnLanInfos']

                if server.get('LastConnectionMode') is not None:
                    existing['LastConnectionMode'] = server['LastConnectionMode']

                if server.get('ConnectServerId'):
                    existing['ConnectServerId'] = server['ConnectServerId']

                return existing
        else:
            list_.append(server)
            return server

    def addOrUpdateUser(self, server, user):

        for existing in server.setdefault('Users', []):
            if existing['Id'] == user['Id']:
                # Merge the data
                existing['IsSignedInOffline'] = True
                break
        else:
            server['Users'].append(user)

    def _dateObject(self, date):
        # Convert string to date
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
        except (ImportError, TypeError):
            # TypeError: attribute of type 'NoneType' is not callable
            # Known Kodi/python error
            date_obj = datetime(*(time.strptime(date, "%Y-%m-%dT%H:%M:%SZ")[0:6]))
        
        return date_obj