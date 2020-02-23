# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import json
import logging
import time

import requests
from six import string_types

from .exceptions import HTTPException
from helper.utils import JsonDebugPrinter

#################################################################################################

LOG = logging.getLogger('Jellyfin.' + __name__)

#################################################################################################


class HTTP(object):

    session = None
    keep_alive = False

    def __init__(self, client):

        self.client = client
        self.config = client.config

    def start_session(self):

        self.session = requests.Session()

        max_retries = self.config.data['http.max_retries']
        self.session.mount("http://", requests.adapters.HTTPAdapter(max_retries=max_retries))
        self.session.mount("https://", requests.adapters.HTTPAdapter(max_retries=max_retries))

    def stop_session(self):

        if self.session is None:
            return

        try:
            LOG.info("--<[ session/%s ]", id(self.session))
            self.session.close()
        except Exception as error:
            LOG.warning("The requests session could not be terminated: %s", error)

    def _replace_user_info(self, string):

        if '{server}' in string:
            if self.config.data.get('auth.server', None):
                string = string.replace("{server}", self.config.data['auth.server'])
            else:
                LOG.debug("Server address not set")

        if '{UserId}'in string:
            if self.config.data.get('auth.user_id', None):
                string = string.replace("{UserId}", self.config.data['auth.user_id'])
            else:
                LOG.debug("UserId is not set.")

        return string

    def REQUEST(self, url, type, params=None, json=None, session=None, \
                    headers=None, verify=None, timeout=None, retry=None):
        config = self.config.data

        data = {'url': url, 'type': type}
        if params is not None:
            data['params'] = params
        if json is not None:
            data['json'] = json
        if headers is not None:
            data['headers'] = headers
        if timeout is not None:
            data['timeout'] = timeout
        if verify is not None:
            data['verify'] = verify
        if retry is not None:
            data['retry'] = retry
        if json is not None:
            data['json'] = json
        return self.request(config, data, session)


    def get_handler_url(self, handler):
        server = self.config.data.get("auth.server", "")
        return "%s/%s" % (server, handler)


    def request(self, config, data, session=None):

        ''' Give a chance to retry the connection. Jellyfin sometimes can be slow to answer back
            data dictionary can contain:
            type: GET, POST, etc.
            url: (optional)
            handler: not considered when url is provided (optional)
            params: request parameters (optional)
            json: request body (optional)
            headers: (optional),
            verify: ssl certificate, True (verify using device built-in library) or False
        '''
        if not data:
            raise AttributeError("Request cannot be empty")

        data = self._request(config, data)
        LOG.debug("--->[ http ] %s", JsonDebugPrinter(data))
        retry = data.pop('retry', 5)

        while True:

            try:
                r = self._requests(session or self.session or requests, data.pop('type', "GET"), **data)
                r.content  # release the connection

                if not self.keep_alive and self.session is not None:
                    self.stop_session()

                r.raise_for_status()

            except requests.exceptions.ConnectionError as error:
                if retry:

                    retry -= 1
                    time.sleep(1)

                    continue

                LOG.error(error)
                self.client.callback("ServerUnreachable", {'ServerId': config['auth.server-id']})

                raise HTTPException("ServerUnreachable", error)

            except requests.exceptions.ReadTimeout as error:
                if retry:

                    retry -= 1
                    time.sleep(1)

                    continue

                LOG.error(error)

                raise HTTPException("ReadTimeout", error)

            except requests.exceptions.HTTPError as error:
                LOG.error(error)

                if r.status_code == 401:

                    if 'X-Application-Error-Code' in r.headers:
                        self.client.callback("AccessRestricted", {'ServerId': config['auth.server-id']})

                        raise HTTPException("AccessRestricted", error)
                    else:
                        self.client.callback("Unauthorized", {'ServerId': config['auth.server-id']})
                        self.client.auth.revoke_token()

                        raise HTTPException("Unauthorized", error)

                elif r.status_code == 500:  # log and ignore.
                    LOG.error("--[ 500 response ] %s", error)

                    return

                elif r.status_code == 502:
                    if retry:

                        retry -= 1
                        time.sleep(1)

                        continue

                raise HTTPException(r.status_code, error)

            except requests.exceptions.MissingSchema as error:
                LOG.error("Request missing Schema. " + str(error))
                raise HTTPException("MissingSchema", {'Id': config.get('auth.server', "None")})

            except Exception as error:
                raise

            else:
                try:
                    config['server-time'] = r.headers['Date']
                    elapsed = int(r.elapsed.total_seconds() * 1000)
                    response = r.json()
                    LOG.debug("---<[ http ][%s ms]", elapsed)
                    LOG.debug(JsonDebugPrinter(response))

                    return response
                except ValueError:
                    return

    def _request(self, config, data):

        if 'url' not in data:
            data['url'] = "%s/%s" % (config.get("auth.server", ""), data.pop('handler', ""))

        headers = self._get_header(config, data.get('headers', {}))
        data['headers'] = headers
        data['timeout'] = data.get('timeout') or config['http.timeout']
        data['verify'] = data.get('verify') or config.get('auth.ssl', False)
        data['url'] = self._replace_user_info(data['url'])
        self._process_params(data.get('params') or {})
        self._process_params(data.get('json') or {})

        return data

    def _process_params(self, params):

        for key in params:
            value = params[key]

            if isinstance(value, dict):
                self._process_params(value)

            if isinstance(value, string_types):
                params[key] = self._replace_user_info(value)

    def _get_header(self, config, headers):
        if not headers:
            headers = {
                'Content-type': "application/json",
                'Accept-Charset': "UTF-8,*",
                'Accept-encoding': "gzip",
                'User-Agent': config['http.user_agent'] or "%s/%s" % (config.get('app.name', 'Jellyfin for Kodi'), config.get('app.version', "0.0.0"))
            }

        if 'x-emby-authorization' not in headers:
            xxx = self._authorization(config)
            headers.update(xxx)

        return headers

    def _authorization(self, config):

        auth = "MediaBrowser "
        auth += "Client=%s, " % config.get('app.name', "Jellyfin for Kodi")
        auth += "Device=%s, " % config.get('app.device_name', 'Unknown Device')
        auth += "DeviceId=%s, " % config.get('app.device_id', 'Unknown Device id')
        auth += "Version=%s" % config.get('app.version', '0.0.0')


        if config.get('auth.token') and config.get('auth.user_id'):
            auth += ', UserId=%s' % config.get('auth.user_id')
            xxx = {'x-emby-authorization': auth, 'X-MediaBrowser-Token': config.get('auth.token')}
        else:
            xxx = {'x-emby-authorization': auth}
        return xxx

    def _requests(self, session, action, **kwargs):

        if action == "GET":
            return session.get(**kwargs)
        elif action == "POST":
            return session.post(**kwargs)
        elif action == "HEAD":
            return session.head(**kwargs)
        elif action == "DELETE":
            return session.delete(**kwargs)
