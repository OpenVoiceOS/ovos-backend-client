import json
import os
from io import BytesIO, StringIO
import time
import requests
from ovos_config import Configuration
from ovos_utils import timed_lru_cache
from ovos_utils.log import LOG
from requests.exceptions import HTTPError

from selene_api.identity import IdentityManager, identity_lock


class BaseApi:
    def __init__(self, url=None, version="v1", identity_file=None):

        if not url:
            config = Configuration()
            config_server = config.get("server") or {}
            url = config_server.get("url")
            version = config_server.get("version") or version

        self._identity_file = identity_file
        self.backend_url = url or "https://api.mycroft.ai"
        self.backend_version = version
        self.url = url

    @property
    def identity(self):
        if self._identity_file:
            # this is helpful if copying over the identity to a non-mycroft device
            # eg, selene call out proxy in local backend
            IdentityManager.set_identity_file(self._identity_file)
        return IdentityManager.get()

    @property
    def uuid(self):
        return self.identity.uuid

    @property
    def headers(self):
        return {"Content-Type": "application/json",
                "Device": self.identity.uuid,
                "Authorization": f"Bearer {self.identity.access}"}

    def check_token(self):
        if self.identity.is_expired():
            self.refresh_token()

    def refresh_token(self):
        LOG.debug('Refreshing token')
        if identity_lock.acquire(blocking=False):
            try:
                data = requests.get(self.backend_url + f"/{self.backend_version}/auth/token",
                                    headers=self.headers).json()
                IdentityManager.save(data, lock=False)
                LOG.debug('Saved credentials')
            except HTTPError as e:
                if e.response.status_code == 401:
                    LOG.error('Could not refresh token, invalid refresh code.')
                else:
                    raise

            finally:
                identity_lock.release()

    def get(self, url=None, *args, **kwargs):
        url = url or self.url
        headers = kwargs.get("headers", {})
        headers.update(self.headers)
        self.check_token()
        return requests.get(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def post(self, url=None, *args, **kwargs):
        url = url or self.url
        headers = kwargs.get("headers", {})
        headers.update(self.headers)
        self.check_token()
        return requests.post(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def put(self, url=None, *args, **kwargs):
        url = url or self.url
        headers = kwargs.get("headers", {})
        headers.update(self.headers)
        self.check_token()
        return requests.put(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def patch(self, url=None, *args, **kwargs):
        url = url or self.url
        headers = kwargs.get("headers", {})
        headers.update(self.headers)
        self.check_token()
        return requests.patch(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)


class AdminApi(BaseApi):
    def __init__(self, admin_key, url=None, version="v1", identity_file=None):
        self.admin_key = admin_key
        super().__init__(url, version, identity_file)
        self.url = f"{self.backend_url}/{self.backend_version}/admin"

    @property
    def headers(self):
        return {"Content-Type": "application/json",
                "Device": self.identity.uuid,
                "Authorization": f"Bearer {self.admin_key}"}

    def pair(self, uuid):
        identity = self.get(f"{self.url}/{uuid}/pair")
        # save identity file
        self.identity.save(identity)
        return identity

    def set_device_location(self, uuid, loc):
        """
        loc = {
            "city": {
                "code": "Lawrence",
                "name": "Lawrence",
                "state": {
                    "code": "KS",
                    "name": "Kansas",
                    "country": {
                        "code": "US",
                        "name": "United States"
                    }
                }
            },
            "coordinate": {
                "latitude": 38.971669,
                "longitude": -95.23525
            },
            "timezone": {
                "code": "America/Chicago",
                "name": "Central Standard Time",
                "dstOffset": 3600000,
                "offset": -21600000
            }
        }
        """
        return self.put(f"{self.url}/{uuid}/location",
                        json=loc)

    def set_device_prefs(self, uuid, prefs):
        """
        prefs = {"time_format": "full",
                "date_format": "DMY",
                "system_unit": "metric",
                "lang": "en-us"}
        """
        return self.put(f"{self.url}/{uuid}/prefs",
                        json=prefs)

    def set_device_info(self, uuid, info):
        """
        info = {"opt_in": True,
                "name": "my_device",
                "device_location": "kitchen",
                "email": "notifications@me.com",
                "isolated_skills": False,
                "lang": "en-us"}
        """
        return self.put(f"{self.url}/{uuid}/device",
                        json=info)


class DeviceApi(BaseApi):
    def __init__(self, url=None, version="v1", identity_file=None):
        super().__init__(url, version, identity_file)
        self.url = f"{self.backend_url}/{self.backend_version}/device"

    def get(self, url=None, *args, **kwargs):
        """ Retrieve all device information from the web backend """
        url = url or self.url
        return super().get(url + "/" + self.uuid).json()

    def get_skill_settings_v1(self):
        """ old style deprecated bidirectional skill settings api, still available! """
        return super().get(self.url + "/" + self.uuid + "/skill").json()

    def put_skill_settings_v1(self, data):
        """ old style deprecated bidirectional skill settings api, still available! """
        return super().put(self.url + "/" + self.uuid + "/skill", json=data).json()

    def get_settings(self):
        """ Retrieve device settings information from the web backend

        Returns:
            str: JSON string with user configuration information.
        """
        return super().get(self.url + "/" + self.uuid + "/setting").json()

    def get_code(self, state=None):
        state = state or self.uuid
        return super().get(self.url + "/code", params={"state": state}).json()

    def activate(self, state, token,
                 core_version="unknown",
                 platform="unknown",
                 platform_build="unknown",
                 enclosure_version="unknown"):
        data = {"state": state,
                "token": token,
                "coreVersion": core_version,
                "platform": platform,
                "platform_build": platform_build,
                "enclosureVersion": enclosure_version}
        return self.post(self.url + "/activate", json=data).json()

    def update_version(self,
                       core_version="unknown",
                       platform="unknown",
                       platform_build="unknown",
                       enclosure_version="unknown"):
        data = {"coreVersion": core_version,
                "platform": platform,
                "platform_build": platform_build,
                "enclosureVersion": enclosure_version}
        return self.patch(self.url + "/" + self.uuid, json=data)

    def report_metric(self, name, data):
        return self.post(self.url + "/" + self.uuid + "/metric/" + name,
                         json=data)

    def get_location(self):
        """ Retrieve device location information from the web backend

        Returns:
            str: JSON string with user location.
        """
        return super().get(self.url + "/" + self.uuid + "/location").json()

    def get_subscription(self):
        """
            Get information about type of subscription this unit is connected
            to.

            Returns: dictionary with subscription information
        """
        return super().get(self.url + "/" + self.uuid + "/subscription").json()

    @property
    def is_subscriber(self):
        """
            status of subscription. True if device is connected to a paying
            subscriber.
        """
        try:
            return self.get_subscription().get('@type') != 'free'
        except Exception:
            # If can't retrieve, assume not paired and not a subscriber yet
            return False

    def get_subscriber_voice_url(self, voice=None, arch=None):
        archs = {'x86_64': 'x86_64', 'armv7l': 'arm', 'aarch64': 'arm'}
        arch = arch or archs.get(os.uname()[4])
        if arch:
            path = '/' + self.uuid + '/voice?arch=' + arch
            return super().get(self.url + path).json().get('link')

    def get_oauth_token(self, dev_cred):
        """
            Get Oauth token for dev_credential dev_cred.

            Argument:
                dev_cred:   development credentials identifier

            Returns:
                json string containing token and additional information
        """
        return super().get(self.url + "/" + self.uuid + "/token/" + str(dev_cred)).json()

    # cached for 30 seconds because often 1 call per skill is done in quick succession
    @timed_lru_cache(seconds=30)
    def get_skill_settings(self):
        """Get the remote skill settings for all skills on this device."""
        return super().get(self.url + "/" + self.uuid + "/skill/settings").json()

    def send_email(self, title, body, sender):
        return self.put(self.url + "/" + self.uuid + "/message",
                        json={"title": title,
                              "body": body,
                              "sender": sender}).json()

    def upload_skill_metadata(self, settings_meta):
        """Upload skill metadata.

        Args:
            settings_meta (dict): skill info and settings in JSON format
        """
        return self.put(url=self.url + "/" + self.uuid + "/settingsMeta",
                        json=settings_meta)

    def upload_skills_data(self, data):
        """ Upload skills.json file. This file contains a manifest of installed
        and failed installations for use with the Marketplace.

        Args:
             data: dictionary with skills data from msm
        """
        if not isinstance(data, dict):
            raise ValueError('data must be of type dict')

        _data = dict(data)  # Make sure the input data isn't modified
        # Strip the skills.json down to the bare essentials
        to_send = {'skills': []}
        if 'blacklist' in _data:
            to_send['blacklist'] = _data['blacklist']
        else:
            LOG.warning('skills manifest lacks blacklist entry')
            to_send['blacklist'] = []

        # Make sure skills doesn't contain duplicates (keep only last)
        if 'skills' in _data:
            skills = {s['name']: s for s in _data['skills']}
            to_send['skills'] = [skills[key] for key in skills]
        else:
            LOG.warning('skills manifest lacks skills entry')
            to_send['skills'] = []

        for s in to_send['skills']:
            # Remove optional fields backend objects to
            if 'update' in s:
                s.pop('update')

            # Finalize skill_gid with uuid if needed
            s['skill_gid'] = s.get('skill_gid', '').replace('@|', f'@{self.uuid}|')
        return self.put(url=self.url + "/" + self.uuid + "/skillJson",
                        json=to_send)

    def upload_wake_word_v1(self, audio, params):
        """ upload precise wake word V1 endpoint - DEPRECATED"""
        url = f"{self.backend_url}/precise/upload"
        return self.post(url, files={
                'audio': BytesIO(audio.get_wav_data()),
                'metadata': StringIO(json.dumps(params))
            })

    def upload_wake_word(self, audio, params):
        """ upload precise wake word V2 endpoint """
        url = f"{self.url}/{self.uuid}/wake-word-file"
        request_data = dict(
            wake_word=params['name'],
            engine=params.get('engine_name') or params.get('engine'),
            timestamp=params.get('timestamp') or params.get('time') or str(int(1000 * time.time())),
            model=params['model']
        )

        return self.post(url, files={
                'audio': BytesIO(audio.get_wav_data()),
                'metadata': StringIO(json.dumps(request_data))
            })


class STTApi(BaseApi):
    def __init__(self, url=None, version="v1", identity_file=None):
        super().__init__(url, version, identity_file)
        self.url = f"{self.backend_url}/{self.backend_version}/stt"

    @property
    def headers(self):
        return {"Content-Type": "audio/x-flac",
                "Device": self.identity.uuid,
                "Authorization": f"Bearer {self.identity.access}"}

    def stt(self, audio, language="en-us", limit=1):
        """ Web API wrapper for performing Speech to Text (STT)

        Args:
            audio (bytes): The recorded audio, as in a FLAC file
            language (str): A BCP-47 language code, e.g. "en-US"
            limit (int): Maximum minutes to transcribe(?)

        Returns:
            dict: JSON structure with transcription results
        """
        data = self.post(data=audio, params={"lang": language, "limit": limit})
        if data.status_code == 200:
            return data.json()
        raise RuntimeError(f"STT api failed, status_code {data.status_code}")


class GeolocationApi(BaseApi):
    """Web API wrapper for performing geolocation lookups."""

    def __init__(self, url=None, version="v1", identity_file=None):
        super().__init__(url, version, identity_file)
        self.url = f"{self.backend_url}/{self.backend_version}/geolocation"

    def get_geolocation(self, location):
        """Call the geolocation endpoint.

        Args:
            location (str): the location to lookup (e.g. Kansas City Missouri)

        Returns:
            str: JSON structure with lookup results
        """
        response = self.get(params={"location": location}).json()
        return response['data']


class WolframAlphaApi(BaseApi):

    def __init__(self, url=None, version="v1", identity_file=None):
        super().__init__(url, version, identity_file)
        self.url = f"{self.backend_url}/{self.backend_version}/wolframAlpha"

    # cached to save api calls, wolfram answer wont change often
    @timed_lru_cache(seconds=60 * 30)
    def spoken(self, query, units="metric", lat_lon=None, optional_params=None):
        optional_params = optional_params or {}
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi(url=self.backend_url, version=self.backend_version).get_location()
            lat_lon = (loc['coordinate']['latitude'], loc['coordinate']['longitude'])
        url = f"{self.url}Spoken"
        params = {'i': query,
                  'units': units,
                  "geolocation": "{},{}".format(*lat_lon),
                  **optional_params}
        data = self.get(url=url, params=params)
        return data.text

    @timed_lru_cache(seconds=60 * 30)
    def simple(self, query, units="metric", lat_lon=None, optional_params=None):
        optional_params = optional_params or {}
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi(url=self.backend_url, version=self.backend_version).get_location()
            lat_lon = (loc['coordinate']['latitude'], loc['coordinate']['longitude'])
        url = f"{self.url}Simple"
        params = {'i': query,
                  'units': units,
                  "geolocation": "{},{}".format(*lat_lon),
                  **optional_params}
        data = self.get(url=url, params=params)
        return data.text

    @timed_lru_cache(seconds=60 * 30)
    def full_results(self, query, units="metric", lat_lon=None, optional_params=None):
        """Wrapper for the WolframAlpha Full Results v2 API.
            https://products.wolframalpha.com/api/documentation/
            Pods of interest
            - Input interpretation - Wolfram's determination of what is being asked about.
            - Name - primary name of
            """
        optional_params = optional_params or {}
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi(url=self.backend_url, version=self.backend_version).get_location()
            lat_lon = (loc['coordinate']['latitude'], loc['coordinate']['longitude'])

        params = {'input': query,
                  "units": units,
                  "geolocation": "{},{}".format(*lat_lon),
                  "mode": "Default",
                  "format": "image,plaintext",
                  "output": "json",
                  **optional_params}
        url = f"{self.url}Full"
        data = self.get(url=url, params=params)
        return data.json()


class OpenWeatherMapApi(BaseApi):
    """Use Open Weather Map's One Call API to retrieve weather information"""

    def __init__(self, url=None, version="v1", identity_file=None):
        super().__init__(url, version, identity_file)
        self.url = f"{self.backend_url}/{self.backend_version}/owm"

    @staticmethod
    def owm_language(lang: str):
        """
        OWM supports 31 languages, see https://openweathermap.org/current#multi

        Convert Mycroft's language code to OpenWeatherMap's, if missing use english.

        Args:
            language_config: The Mycroft language code.
        """
        OPEN_WEATHER_MAP_LANGUAGES = (
            "af", "al", "ar", "bg", "ca", "cz", "da", "de", "el", "en", "es", "eu", "fa", "fi", "fr", "gl", "he", "hi",
            "hr", "hu", "id", "it", "ja", "kr", "la", "lt", "mk", "nl", "no", "pl", "pt", "pt_br", "ro", "ru", "se",
            "sk",
            "sl", "sp", "sr", "sv", "th", "tr", "ua", "uk", "vi", "zh_cn", "zh_tw", "zu"
        )
        special_cases = {"cs": "cz", "ko": "kr", "lv": "la"}
        lang_primary, lang_subtag = lang.split('-')
        if lang.replace('-', '_') in OPEN_WEATHER_MAP_LANGUAGES:
            return lang.replace('-', '_')
        if lang_primary in OPEN_WEATHER_MAP_LANGUAGES:
            return lang_primary
        if lang_subtag in OPEN_WEATHER_MAP_LANGUAGES:
            return lang_subtag
        if lang_primary in special_cases:
            return special_cases[lang_primary]
        return "en"

    # cached to save api calls, owm only updates data every 15mins or so
    @timed_lru_cache(seconds=60 * 10)
    def get_weather(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi(url=self.backend_url, version=self.backend_version).get_location()
            lat = loc['coordinate']['latitude']
            lon = loc['coordinate']['longitude']
        else:
            lat, lon = lat_lon
        response = self.get(url=self.url + "/onecall",
                            params={
                                "lang": self.owm_language(lang),
                                "lat": lat,
                                "lon": lon,
                                "units": units})
        return response.json()

    @timed_lru_cache(seconds=60 * 10)
    def get_current(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi(url=self.backend_url, version=self.backend_version).get_location()
            lat = loc['coordinate']['latitude']
            lon = loc['coordinate']['longitude']
        else:
            lat, lon = lat_lon
        response = self.get(url=self.url + "/weather",
                            params={
                                "lang": self.owm_language(lang),
                                "lat": lat,
                                "lon": lon,
                                "units": units})
        return response.json()

    @timed_lru_cache(seconds=60 * 10)
    def get_hourly(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi(url=self.backend_url, version=self.backend_version).get_location()
            lat = loc['coordinate']['latitude']
            lon = loc['coordinate']['longitude']
        else:
            lat, lon = lat_lon
        response = self.get(url=self.url + "/forecast",
                            params={
                                "lang": self.owm_language(lang),
                                "lat": lat,
                                "lon": lon,
                                "units": units})
        return response.json()

    @timed_lru_cache(seconds=60 * 10)
    def get_daily(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi(url=self.backend_url, version=self.backend_version).get_location()
            lat = loc['coordinate']['latitude']
            lon = loc['coordinate']['longitude']
        else:
            lat, lon = lat_lon
        response = self.get(url=self.url + "/forecast/daily",
                            params={
                                "lang": self.owm_language(lang),
                                "lat": lat,
                                "lon": lon,
                                "units": units})
        return response.json()


if __name__ == "__main__":
    d = DeviceApi("http://0.0.0.0:6712")

    # TODO turn these into unittests
    # ident = load_identity()
    # paired = is_paired()
    geo = GeolocationApi("http://0.0.0.0:6712")
    data = geo.get_geolocation("Lisbon Portugal")
    print(data)
    wolf = WolframAlphaApi("http://0.0.0.0:6712")
    data = wolf.spoken("what is the speed of light")
    print(data)
    data = wolf.full_results("2+2")
    print(data)
    owm = OpenWeatherMapApi("http://0.0.0.0:6712")
    data = owm.get_weather()
    print(data)
