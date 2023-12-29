import abc
import json
from enum import Enum
from io import BytesIO, StringIO

import requests
from ovos_config.config import Configuration

from ovos_backend_client.database import SkillSettingsModel
from ovos_backend_client.identity import IdentityManager

try:
    from timezonefinder import TimezoneFinder
except ImportError:
    TimezoneFinder = None


class BackendType(str, Enum):
    OFFLINE = "offline"
    PERSONAL = "personal"


class AbstractBackend:

    def __init__(self, url, version="v1", identity_file=None, backend_type=BackendType.OFFLINE, credentials=None):
        self.backend_url = url
        self.backend_type = backend_type
        self._identity_file = identity_file
        self.backend_version = version
        if not url.startswith("http"):
            url = f"http://{url}"
        self.url = url
        self.credentials = credentials or {}

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
    def access_token(self):
        return self.identity.access

    @property
    def headers(self):
        return {"Device": self.uuid,
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}"}

    def check_token(self):
        if self.identity.is_expired():
            self.refresh_token()

    def refresh_token(self):
        pass

    def get(self, url=None, *args, **kwargs):
        url = url or self.url
        if not url.startswith("http"):
            url = f"http://{url}"
        headers = self.headers
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        self.check_token()
        return requests.get(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def post(self, url=None, *args, **kwargs):
        url = url or self.url
        if not url.startswith("http"):
            url = f"http://{url}"
        headers = self.headers
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        self.check_token()
        return requests.post(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def put(self, url=None, *args, **kwargs):
        url = url or self.url
        if not url.startswith("http"):
            url = f"http://{url}"
        headers = self.headers
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        self.check_token()
        return requests.put(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def patch(self, url=None, *args, **kwargs):
        url = url or self.url
        if not url.startswith("http"):
            url = f"http://{url}"
        headers = self.headers
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        self.check_token()
        return requests.patch(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def delete(self, url=None, *args, **kwargs):
        url = url or self.url
        if not url.startswith("http"):
            url = f"http://{url}"
        headers = self.headers
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        self.check_token()
        return requests.delete(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    # OWM Api
    @staticmethod
    def _get_lat_lon(**kwargs):
        lat = kwargs.get("latitude") or kwargs.get("lat")
        lon = kwargs.get("longitude") or kwargs.get("lon") or kwargs.get("lng")
        if not lat or not lon:
            cfg = Configuration().get("location", {}).get("coordinate", {})
            lat = cfg.get("latitude")
            lon = cfg.get("longitude")
        return lat, lon

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
            "hr", "hu", "id", "it", "ja", "kr", "la", "lt", "mk", "nl", "no", "pl", "pt", "pt_br", "ro", "ru",
            "se", "sk", "sl", "sp", "sr", "sv", "th", "tr", "ua", "uk", "vi", "zh_cn", "zh_tw", "zu"
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

    @abc.abstractmethod
    def owm_get_weather(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def owm_get_current(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def owm_get_hourly(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def owm_get_daily(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        raise NotImplementedError()

    # Wolfram Alpha Api
    @abc.abstractmethod
    def wolfram_spoken(self, query, units="metric", lat_lon=None, optional_params=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def wolfram_simple(self, query, units="metric", lat_lon=None, optional_params=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def wolfram_full_results(self, query, units="metric", lat_lon=None, optional_params=None):
        """Wrapper for the WolframAlpha Full Results v2 API.
        https://products.wolframalpha.com/api/documentation/
        Pods of interest
        - Input interpretation - Wolfram's determination of what is being asked about.
        - Name - primary name of
        """
        raise NotImplementedError()

    # Geolocation Api
    @staticmethod
    def _get_timezone(**kwargs):
        if TimezoneFinder:
            lat, lon = AbstractBackend._get_lat_lon(**kwargs)
            tz = TimezoneFinder().timezone_at(lng=float(lon), lat=float(lat))
            return {
                "name": tz.replace("/", " "),
                "code": tz
            }
        else:
            cfg = Configuration().get("location", {}).get("timezone")
            return cfg or {"name": "UTC", "code": "UTC"}

    @abc.abstractmethod
    def geolocation_get(self, location):
        """Call the geolocation endpoint.

        Args:
            location (str): the location to lookup (e.g. Kansas City Missouri)

        Returns:
            str: JSON structure with lookup results
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def reverse_geolocation_get(self, lat, lon):
        """Call the reverse geolocation endpoint.

        Args:
            lat (float): latitude
            lon (float): longitude

        Returns:
            str: JSON structure with lookup results
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def ip_geolocation_get(self, ip):
        """Call the geolocation endpoint.

        Args:
            ip (str): the ip address to lookup

        Returns:
            str: JSON structure with lookup results
        """
        raise NotImplementedError()

    # STT Api
    @abc.abstractmethod
    def stt_get(self, audio, language="en-us", limit=1):
        """ Web API wrapper for performing Speech to Text (STT)

        Args:
            audio (bytes): The recorded audio, as in a FLAC file
            language (str): A BCP-47 language code, e.g. "en-US"
            limit (int): Maximum minutes to transcribe(?)

        Returns:
            dict: JSON structure with transcription results
        """
        raise NotImplementedError()

    # Device Api
    def device_get(self):
        """ Retrieve all device information from the web backend """
        return {"uuid": IdentityManager.get().uuid,
                "name": "AnonDevice",
                "description": "unknown",
                "coreVersion": "unknown",
                "enclosureVersion": "unknown",
                "platform": "ovos-backend-client",
                "user": {"uuid": "Anon"}
                }

    @abc.abstractmethod
    def device_get_settings(self):
        """ Retrieve device settings information from the web backend

        Returns:
            str: JSON string with user configuration information.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def device_get_code(self, state=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def device_activate(self, state, token,
                        core_version="unknown",
                        platform="unknown",
                        platform_build="unknown",
                        enclosure_version="unknown"):
        raise NotImplementedError()

    @abc.abstractmethod
    def device_update_version(self,
                              core_version="unknown",
                              platform="unknown",
                              platform_build="unknown",
                              enclosure_version="unknown"):
        raise NotImplementedError()

    @abc.abstractmethod
    def device_get_location(self):
        """ Retrieve device location information from the web backend

        Returns:
            str: JSON string with user location.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def device_upload_skills_data(self, data):
        """ Upload skills.json file. This file contains a manifest of installed
        and failed installations for use with the Marketplace.

        Args:
             data: dictionary with skills data from msm
        """
        raise NotImplementedError()

    # Metrics API
    @abc.abstractmethod
    def metrics_upload(self, name, data):
        """ upload metrics"""
        raise NotImplementedError()

    # OAuth API
    @abc.abstractmethod
    def oauth_get_token(self, dev_cred):
        """
            Get Oauth token for dev_credential dev_cred.

            Argument:
                dev_cred:   development credentials identifier

            Returns:
                json string containing token and additional information
        """
        raise NotImplementedError()

    # Dataset API
    def dataset_upload_wake_word(self, audio, params, upload_url=None):
        """ upload wake word sample - url can be external to backend"""
        if not isinstance(audio, bytes):
            byte_data = audio.get_wav_data()
        else:
            byte_data = audio
        upload_url = upload_url or Configuration().get("listener", {}).get("wake_word_upload", {}).get("url")
        if upload_url:
            # upload to arbitrary server
            ww_files = {
                'audio': BytesIO(byte_data),
                'metadata': StringIO(json.dumps(params))
            }
            return self.post(upload_url, files=ww_files)
        return {}

    def dataset_upload_stt_recording(self, audio, params, upload_url=None):
        """ upload stt sample - url can be external to backend"""
        if not isinstance(audio, bytes):
            byte_data = audio.get_wav_data()
        else:
            byte_data = audio
        upload_url = upload_url or Configuration().get("listener", {}).get("utterance_upload", {}).get("url")
        if upload_url:
            # upload to arbitrary server
            ww_files = {
                'audio': BytesIO(byte_data),
                'metadata': StringIO(json.dumps(params))
            }
            return self.post(upload_url, files=ww_files)
        return {}

    # Email API
    @abc.abstractmethod
    def email_send(self, title, body, sender):
        raise NotImplementedError()

    # Skill settings api
    @abc.abstractmethod
    def skill_settings_upload(self, skill_settings):
        # list of SkillSettingsModel or dicts
        raise NotImplementedError()

    @abc.abstractmethod
    def skill_settings_download(self):
        # return list of SkillSettingsModel
        raise NotImplementedError()

    # Admin Api
    @abc.abstractmethod
    def admin_pair(self, uuid=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def admin_get_backend_config(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def admin_update_backend_config(self, config):
        raise NotImplementedError()

    @abc.abstractmethod
    def admin_set_device_location(self, uuid, loc):
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
        raise NotImplementedError()

    @abc.abstractmethod
    def admin_set_device_prefs(self, uuid, prefs):
        """
        prefs = {"time_format": "full",
                "date_format": "DMY",
                "system_unit": "metric",
                "lang": "en-us",
                "wake_word": "hey_mycroft",
                "ww_config": {"phonemes": "HH EY . M AY K R AO F T",
                             "module": "ovos-ww-plugin-pocketsphinx",
                             "threshold": 1e-90},
                "tts_module": "ovos-tts-plugin-mimic",
                "tts_config": {"voice": "ap"}}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def admin_set_device_info(self, uuid, info):
        """
        info = {"opt_in": True,
                "name": "my_device",
                "device_location": "kitchen",
                "email": "notifications@me.com",
                "isolated_skills": False,
                "lang": "en-us"}
        """
        raise NotImplementedError()

    # Database api
    @abc.abstractmethod
    def db_list_devices(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_device(self, uuid):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_device(self, uuid, name=None,
                         device_location=None, opt_in=False,
                         location=None, lang=None, date_format=None,
                         system_unit=None, time_format=None, email=None,
                         isolated_skills=False, ww_id=None, voice_id=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_device(self, uuid):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_device(self, uuid, token, name=None,
                       device_location="somewhere",
                       opt_in=Configuration().get("opt_in", False),
                       location=Configuration().get("location"),
                       lang=Configuration().get("lang"),
                       date_format=Configuration().get("date_format", "DMY"),
                       system_unit=Configuration().get("system_unit", "metric"),
                       time_format=Configuration().get("date_format", "full"),
                       email=None,
                       isolated_skills=False,
                       ww_id=None,
                       voice_id=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_list_shared_skill_settings(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_shared_skill_settings(self, skill_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_shared_skill_settings(self, skill_id,
                                        display_name=None,
                                        settings_json=None,
                                        metadata_json=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_shared_skill_settings(self, skill_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_shared_skill_settings(self, skill_id,
                                      display_name,
                                      settings_json,
                                      metadata_json):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_list_skill_settings(self, uuid):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_skill_settings(self, uuid, skill_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_skill_settings(self, uuid, skill_id,
                                 display_name=None,
                                 settings_json=None,
                                 metadata_json=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_skill_settings(self, uuid, skill_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_skill_settings(self, uuid, skill_id,
                               display_name,
                               settings_json,
                               metadata_json):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_list_oauth_apps(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_oauth_app(self, token_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_oauth_app(self, token_id, client_id=None, client_secret=None,
                            auth_endpoint=None, token_endpoint=None, refresh_endpoint=None,
                            callback_endpoint=None, scope=None, shell_integration=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_oauth_app(self, token_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_oauth_app(self, token_id, client_id, client_secret,
                          auth_endpoint, token_endpoint, refresh_endpoint,
                          callback_endpoint, scope, shell_integration=True):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_list_oauth_tokens(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_oauth_token(self, token_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_oauth_token(self, token_id, token_data):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_oauth_token(self, token_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_oauth_token(self, token_id, token_data):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_list_stt_recordings(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_stt_recording(self, rec_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_stt_recording(self, rec_id, transcription=None, metadata=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_stt_recording(self, rec_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_stt_recording(self, byte_data, transcription, metadata=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_list_ww_recordings(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_ww_recording(self, rec_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_ww_recording(self, rec_id, transcription=None, metadata=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_ww_recording(self, rec_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_ww_recording(self, byte_data, transcription, metadata=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_list_metrics(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_metric(self, metric_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_metric(self, metric_id, metadata):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_metric(self, metric_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_metric(self, metric_type, metadata):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_list_ww_definitions(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_ww_definition(self, ww_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_ww_definition(self, ww_id, name, lang, ww_config, plugin):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_ww_definition(self, ww_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_ww_definition(self, name, lang, ww_config, plugin):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_list_voice_definitions(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_get_voice_definition(self, voice_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_update_voice_definition(self, voice_id, name=None, lang=None, plugin=None,
                                   tts_config=None, offline=None, gender=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_delete_voice_definition(self, voice_id):
        raise NotImplementedError()

    @abc.abstractmethod
    def db_post_voice_definition(self, name, lang, plugin,
                                 tts_config, offline, gender=None):
        raise NotImplementedError()

    # DEPRECATED APIS
    @property
    def is_subscriber(self):
        """
            status of subscription. True if device is connected to a paying
            subscriber.
        """
        ## DEPRECATED - compat only for old devices
        try:
            return self.device_get_subscription().get('@type') != 'free'
        except Exception:
            # If can't retrieve, assume not paired and not a subscriber yet
            return False

    def device_report_metric(self, name, data):
        ## DEPRECATED - compat only for old devices
        return self.metrics_upload(name, data)

    def device_get_oauth_token(self, dev_cred):
        """
            Get Oauth token for dev_credential dev_cred.

            Argument:
                dev_cred:   development credentials identifier

            Returns:
                json string containing token and additional information
        """
        ## DEPRECATED - compat only for old devices
        raise self.oauth_get_token(dev_cred)

    def device_get_skill_settings_v1(self):
        """ old style bidirectional skill settings api, still available!"""
        ## DEPRECATED - compat only for old devices
        return [s.serialize() for s in self.skill_settings_download()]

    def device_put_skill_settings_v1(self, data=None):
        """ old style bidirectional skill settings api, still available!"""
        ## DEPRECATED - compat only for old devices
        s = SkillSettingsModel.deserialize(data)
        settings = [s]
        self.skill_settings_upload(settings)
        return {}

    def device_get_skill_settings(self):
        """Get the remote skill settings for all skills on this device."""
        ## DEPRECATED - compat only for old devices
        return {s.skill_id: s.skill_settings for s in self.skill_settings_download()}

    def device_upload_skill_metadata(self, settings_meta):
        """Upload skill metadata.

        Args:
            settings_meta (dict): skill info and settings in JSON format
        """
        ## DEPRECATED - compat only for old devices
        s = SkillSettingsModel.deserialize(settings_meta)
        settings = self.device_get_skill_settings()
        old_s = settings.get(s.skill_id)
        if old_s:  # keep old settings value, update meta values only
            s.skill_settings = old_s.skill_settings
        self.device_put_skill_settings_v1(s.serialize())

    def device_send_email(self, title, body, sender):
        ## DEPRECATED - compat only for old devices
        return self.email_send(title, body, sender)

    def device_upload_wake_word_v1(self, audio, params, upload_url=None):
        """ upload precise wake word V1 endpoint - url can be external to backend"""
        return self.dataset_upload_wake_word(audio, params, upload_url)

    def device_upload_wake_word(self, audio, params):
        """ upload precise wake word V2 endpoint - integrated with device api"""
        return self.dataset_upload_wake_word(audio, params)

    def device_get_subscription(self):
        """
            Get information about type of subscription this unit is connected
            to.

            Returns: dictionary with subscription information
        """
        ## DEPRECATED - compat only for old devices
        return {"@type": "free"}

    def device_get_subscriber_voice_url(self, voice=None, arch=None):
        ## DEPRECATED - compat only for old devices
        return None
