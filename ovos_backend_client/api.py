from ovos_utils import timed_lru_cache
from ovos_utils.log import LOG

import json
import os
from os import makedirs
from os.path import isfile
from ovos_config.config import Configuration, get_xdg_config_save_path
from ovos_backend_client.backends import OfflineBackend, \
    PersonalBackend, BackendType, get_backend_config, API_REGISTRY
from ovos_backend_client.database import SkillSettingsModel
from ovos_backend_client.settings import get_local_settings


class BaseApi:
    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None, credentials=None):
        url, version, identity_file, backend_type = get_backend_config(url, version,
                                                                       identity_file, backend_type)
        self.url = url
        self.credentials = credentials or {}
        if backend_type == BackendType.PERSONAL:
            self.backend = PersonalBackend(url, version, identity_file, credentials=credentials)
        else:  # if backend_type == BackendType.OFFLINE:
            self.backend = OfflineBackend(url, version, identity_file, credentials=credentials)
        self.validate_backend_type()

    def validate_backend_type(self):
        pass

    @property
    def backend_type(self):
        return self.backend.backend_type

    @property
    def backend_url(self):
        if not self.backend.url.startswith("http"):
            self.backend.url = f"http://{self.backend.url}"
        return self.backend.url

    @property
    def backend_version(self):
        return self.backend.backend_version

    @property
    def identity(self):
        return self.backend.identity

    @property
    def uuid(self):
        return self.backend.uuid

    @property
    def access_token(self):
        return self.backend.access_token

    @property
    def headers(self):
        return self.backend.headers

    def check_token(self):
        self.backend.check_token()

    def refresh_token(self):
        self.backend.refresh_token()

    def get(self, url=None, *args, **kwargs):
        return self.backend.get(url, *args, **kwargs)

    def post(self, url=None, *args, **kwargs):
        return self.backend.post(url, *args, **kwargs)

    def put(self, url=None, *args, **kwargs):
        return self.backend.put(url, *args, **kwargs)

    def patch(self, url=None, *args, **kwargs):
        return self.backend.patch(url, *args, **kwargs)


class AdminApi(BaseApi):
    def __init__(self, admin_key, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type, credentials={"admin": admin_key})
        self.url = f"{self.backend_url}/{self.backend_version}/admin"

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["admin"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")

    def get_backend_config(self):
        return self.backend.admin_get_backend_config()

    def update_backend_config(self, config):
        return self.backend.admin_update_backend_config(config)

    def pair(self, uuid=None):
        return self.backend.admin_pair(uuid)

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
        return self.backend.admin_set_device_location(uuid, loc)

    def set_device_prefs(self, uuid, prefs):
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
        self.backend.admin_set_device_prefs(uuid, prefs)

    def set_device_info(self, uuid, info):
        """
        info = {"opt_in": True,
                "name": "my_device",
                "device_location": "kitchen",
                "email": "notifications@me.com",
                "isolated_skills": False,
                "lang": "en-us"}
        """
        self.backend.admin_set_device_info(uuid, info)


class DeviceApi(BaseApi):
    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type)
        self.url = f"{self.backend_url}/{self.backend_version}/device"

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["device"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")

    def get(self, url=None, *args, **kwargs):
        """ Retrieve all device information from the web backend """
        return self.backend.device_get()

    def get_settings(self):
        """ Retrieve device settings information from the web backend

        Returns:
            str: JSON string with user configuration information.
        """
        return self.backend.device_get_settings()

    def get_code(self, state=None):
        return self.backend.device_get_code(state)

    def activate(self, state, token,
                 core_version="unknown",
                 platform="unknown",
                 platform_build="unknown",
                 enclosure_version="unknown"):
        return self.backend.device_activate(state, token, core_version,
                                            platform, platform_build, enclosure_version)

    def update_version(self,
                       core_version="unknown",
                       platform="unknown",
                       platform_build="unknown",
                       enclosure_version="unknown"):
        return self.backend.device_update_version(core_version, platform, platform_build, enclosure_version)

    def get_location(self):
        """ Retrieve device location information from the web backend

        Returns:
            str: JSON string with user location.
        """
        return self.backend.device_get_location()

    def upload_skill_metadata(self, settings_meta):
        """Upload skill metadata.

        Args:
            settings_meta (dict): skill info and settings in JSON format
        """
        return self.backend.device_upload_skill_metadata(settings_meta)

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

        return self.backend.device_upload_skills_data(to_send)

    ## DEPRECATED APIS below, use dedicated classes instead
    def get_oauth_token(self, dev_cred):
        """
            Get Oauth token for dev_credential dev_cred.

            Argument:
                dev_cred:   development credentials identifier

            Returns:
                json string containing token and additional information
        """
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: use OAuthApi class instead")
        return self.backend.device_get_oauth_token(dev_cred)

    def report_metric(self, name, data):
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: use MetricsApi class instead")
        return self.backend.device_report_metric(name, data)

    def get_subscription(self):
        """
            Get information about type of subscription this unit is connected
            to.

            Returns: dictionary with subscription information
        """
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: there are no subscriptions")
        return self.backend.device_get_subscription()

    @property
    def is_subscriber(self):
        """
            status of subscription. True if device is connected to a paying
            subscriber.
        """
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: there are no subscriptions")
        return self.backend.is_subscriber

    def get_subscriber_voice_url(self, voice=None, arch=None):
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: there are no subscriptions")
        return self.backend.device_get_subscriber_voice_url(voice, arch)

    def get_skill_settings_v1(self):
        """ old style deprecated bidirectional skill settings api, still available! """
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: use SkillSettingsApi class instead")
        return self.backend.device_get_skill_settings_v1()

    def put_skill_settings_v1(self, data):
        """ old style deprecated bidirectional skill settings api, still available! """
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: use SkillSettingsApi class instead")
        return self.backend.device_put_skill_settings_v1(data)

    # cached for 30 seconds because often 1 call per skill is done in quick succession
    @timed_lru_cache(seconds=30)
    def get_skill_settings(self):
        """Get the remote skill settings for all skills on this device."""
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: use SkillSettingsApi class instead")
        return self.backend.device_get_skill_settings()

    def send_email(self, title, body, sender):
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: use EmailApi class instead")
        return self.backend.device_send_email(title, body, sender)

    def upload_wake_word_v1(self, audio, params):
        """ upload precise wake word V1 endpoint - DEPRECATED"""
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: use DatasetApi class instead")
        return self.backend.device_upload_wake_word_v1(audio, params)

    def upload_wake_word(self, audio, params):
        """ upload precise wake word V2 endpoint """
        ## DEPRECATED - compat only for old devices
        LOG.warning("DEPRECATED: use DatasetApi class instead")
        return self.backend.device_upload_wake_word(audio, params)


class STTApi(BaseApi):
    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type)
        self.url = f"{self.backend_url}/{self.backend_version}/stt"

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["stt"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")

    @property
    def headers(self):
        h = self.backend.headers
        h["Content-Type"] = "audio/x-flac"
        return h

    def stt(self, audio, language="en-us", limit=1):
        """ Web API wrapper for performing Speech to Text (STT)

        Args:
            audio (bytes): The recorded audio, as in a FLAC file
            language (str): A BCP-47 language code, e.g. "en-US"
            limit (int): Maximum minutes to transcribe(?)

        Returns:
            dict: JSON structure with transcription results
        """
        return self.backend.stt_get(audio, language, limit)


class GeolocationApi(BaseApi):
    """Web API wrapper for performing geolocation lookups."""

    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type)

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["geolocate"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")
        if self.backend_type == BackendType.OFFLINE:
            self.url = "https://nominatim.openstreetmap.org"
        else:
            self.url = f"{self.backend_url}/{self.backend_version}/geolocation"

    def get_geolocation(self, location):
        """Call the geolocation endpoint.

        Args:
            location (str): the location to lookup (e.g. Kansas City Missouri)

        Returns:
            str: JSON structure with lookup results
        """
        return self.backend.geolocation_get(location)

    def get_ip_geolocation(self, ip):
        """Call the geolocation endpoint.

        Args:
            ip (str): the ip address to lookup

        Returns:
            str: JSON structure with lookup results
        """
        return self.backend.ip_geolocation_get(ip)

    def get_reverse_geolocation(self, lat, lon):
        """"Call the reverse geolocation endpoint.

        Args:
            lat (float): latitude
            lon (float): longitude

        Returns:
            str: JSON structure with lookup results
        """
        return self.backend.reverse_geolocation_get(lat, lon)


class WolframAlphaApi(BaseApi):

    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None, key=None):
        super().__init__(url, version, identity_file, backend_type, credentials={"wolfram": key})

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["wolfram"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")
        if self.backend_type == BackendType.OFFLINE and not self.credentials["wolfram"]:
            raise ValueError("WolframAlpha api key not set!")

        if self.backend_type == BackendType.OFFLINE:
            self.url = "https://api.wolframalpha.com"
        else:
            self.url = f"{self.backend_url}/{self.backend_version}/wolframAlpha"

    # cached to save api calls, wolfram answer wont change often
    @timed_lru_cache(seconds=60 * 30)
    def spoken(self, query, units="metric", lat_lon=None, optional_params=None):
        return self.backend.wolfram_spoken(query, units, lat_lon, optional_params)

    @timed_lru_cache(seconds=60 * 30)
    def simple(self, query, units="metric", lat_lon=None, optional_params=None):
        return self.backend.wolfram_simple(query, units, lat_lon, optional_params)

    @timed_lru_cache(seconds=60 * 30)
    def full_results(self, query, units="metric", lat_lon=None, optional_params=None):
        """Wrapper for the WolframAlpha Full Results v2 API.
            https://products.wolframalpha.com/api/documentation/
            Pods of interest
            - Input interpretation - Wolfram's determination of what is being asked about.
            - Name - primary name of
            """
        return self.backend.wolfram_full_results(query, units, lat_lon, optional_params)


class OpenWeatherMapApi(BaseApi):
    """Use Open Weather Map's One Call API to retrieve weather information"""

    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None, key=None):
        super().__init__(url, version, identity_file, backend_type, credentials={"owm": key})

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["owm"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")
        if self.backend_type == BackendType.OFFLINE and not self.backend.credentials["owm"]:
            raise ValueError("OWM api key not set!")
        if self.backend_type == BackendType.OFFLINE:
            self.url = "https://api.openweathermap.org/data/2.5"
        else:
            self.url = f"{self.backend_url}/{self.backend_version}/owm"

    def owm_language(self, lang: str):
        """
        OWM supports 31 languages, see https://openweathermap.org/current#multi

        Convert Mycroft's language code to OpenWeatherMap's, if missing use english.

        Args:
            lang: The Mycroft language code.
        """
        return self.backend.owm_language(lang)

    # cached to save api calls, owm only updates data every 15mins or so
    @timed_lru_cache(seconds=60 * 10)
    def get_weather(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        return self.backend.owm_get_weather(lat_lon, lang, units)

    @timed_lru_cache(seconds=60 * 10)
    def get_current(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        return self.backend.owm_get_current(lat_lon, lang, units)

    @timed_lru_cache(seconds=60 * 10)
    def get_hourly(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        return self.backend.owm_get_hourly(lat_lon, lang, units)

    @timed_lru_cache(seconds=60 * 10)
    def get_daily(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        return self.backend.owm_get_daily(lat_lon, lang, units)


class EmailApi(BaseApi):
    """Web API wrapper for sending email"""

    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type)

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["email"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")
        if self.backend_type == BackendType.OFFLINE:
            self.url = self.credentials["smtp"]["host"]
        else:
            self.url = self.backend_url

    def send_email(self, title, body, sender):
        return self.backend.email_send(title, body, sender)


class SkillSettingsApi(BaseApi):
    """Web API wrapper for skill settings"""

    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type)

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["skill_settings"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")

    def upload_skill_settings(self):
        """ upload skill settings from XDG path"""
        return self.backend.skill_settings_upload(get_local_settings())

    def download_skill_settings(self):
        """ write downloaded settings to XDG path"""
        settings = self.backend.skill_settings_download()
        for s in settings:  # list of SkillSettingsModel or dicts
            settings_path = f"{get_xdg_config_save_path()}/skills/{s.skill_id}"
            makedirs(settings_path, exist_ok=True)
            with open( f"{settings_path}/settingsmeta.json", "w") as f:
                json.dump(s.meta, f, indent=4, ensure_ascii=False)
            with open(f"{settings_path}/settings.json", "w") as f:
                json.dump(s.skill_settings, f, indent=4, ensure_ascii=False)
        return settings


class DatasetApi(BaseApi):
    """Web API wrapper for dataset collection"""

    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type)

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["dataset"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")

    def upload_wake_word(self, audio, params, upload_url=None):
        return self.backend.dataset_upload_wake_word(audio, params, upload_url)

    def upload_stt_recording(self, audio, params, upload_url=None):
        return self.backend.dataset_upload_stt_recording(audio, params, upload_url)


class MetricsApi(BaseApi):
    """Web API wrapper for netrics collection"""

    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type)

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["metrics"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")

    def report_metric(self, name, data):
        return self.backend.metrics_upload(name, data)


class OAuthApi(BaseApi):
    """Web API wrapper for oauth api"""

    def __init__(self, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type)

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["oauth"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")

    def get_oauth_token(self, dev_cred):
        """
            Get Oauth token for dev_credential dev_cred.

            Argument:
                dev_cred:   development credentials identifier

            Returns:
                json string containing token and additional information
        """
        return self.backend.oauth_get_token(dev_cred)


class DatabaseApi(BaseApi):
    """Web API wrapper for oauth api"""

    def __init__(self, admin_key=None, url=None, version="v1", identity_file=None, backend_type=None):
        super().__init__(url, version, identity_file, backend_type, credentials={"admin": admin_key})
        self.url = f"{self.backend_url}/{self.backend_version}/admin"

    def validate_backend_type(self):
        if not API_REGISTRY[self.backend_type]["database"]:
            raise ValueError(f"{self.__class__.__name__} not available for {self.backend_type}")
        if self.backend_type in [BackendType.PERSONAL] and not self.credentials.get("admin"):
            raise ValueError(f"Admin key not set, can not access remote database")

    def list_devices(self):
        return self.backend.db_list_devices()

    def get_device(self, uuid):
        return self.backend.db_get_device(uuid)

    def update_device(self, uuid, name=None,
                      device_location=None, opt_in=False,
                      location=None, lang=None, date_format=None,
                      system_unit=None, time_format=None, email=None,
                      isolated_skills=False, ww_id=None, voice_id=None):
        return self.backend.db_update_device(uuid, name, device_location, opt_in,
                                             location, lang, date_format, system_unit, time_format,
                                             email, isolated_skills, ww_id, voice_id)

    def delete_device(self, uuid):
        return self.backend.db_delete_device(uuid)

    def add_device(self, uuid, token, name=None,
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
        return self.backend.db_post_device(uuid, token, name, device_location, opt_in,
                                           location, lang, date_format, system_unit, time_format,
                                           email, isolated_skills, ww_id, voice_id)

    def list_shared_skill_settings(self):
        return self.backend.db_list_shared_skill_settings()

    def get_shared_skill_settings(self, skill_id):
        return self.backend.db_get_shared_skill_settings(skill_id)

    def update_shared_skill_settings(self, skill_id,
                                     display_name=None,
                                     settings_json=None,
                                     metadata_json=None):
        return self.backend.db_update_shared_skill_settings(skill_id, display_name,
                                                            settings_json, metadata_json)

    def delete_shared_skill_settings(self, skill_id):
        return self.backend.db_delete_shared_skill_settings(skill_id)

    def add_shared_skill_settings(self, skill_id,
                                  display_name,
                                  settings_json,
                                  metadata_json):
        return self.backend.db_post_shared_skill_settings(skill_id, display_name,
                                                          settings_json, metadata_json)

    def list_skill_settings(self, uuid):
        return self.backend.db_list_skill_settings(uuid)

    def get_skill_settings(self, uuid, skill_id):
        return self.backend.db_get_skill_settings(uuid, skill_id)

    def update_skill_settings(self, uuid, skill_id,
                              display_name=None,
                              settings_json=None,
                              metadata_json=None):
        return self.backend.db_update_skill_settings(uuid, skill_id, display_name,
                                                     settings_json, metadata_json)

    def delete_skill_settings(self, uuid, skill_id):
        return self.backend.db_delete_skill_settings(uuid, skill_id)

    def add_skill_settings(self, uuid, skill_id,
                           display_name,
                           settings_json,
                           metadata_json):
        return self.backend.db_post_skill_settings(uuid, skill_id, display_name,
                                                   settings_json, metadata_json)

    def list_oauth_apps(self):
        return self.backend.db_list_oauth_apps()

    def get_oauth_app(self, token_id):
        return self.backend.db_get_oauth_app(token_id)

    def update_oauth_app(self, token_id, client_id=None, client_secret=None,
                         auth_endpoint=None, token_endpoint=None, refresh_endpoint=None,
                         callback_endpoint=None, scope=None, shell_integration=None):
        return self.backend.db_update_oauth_app(token_id, client_id, client_secret, auth_endpoint, token_endpoint,
                                                refresh_endpoint, callback_endpoint, scope, shell_integration)

    def delete_oauth_app(self, token_id):
        return self.backend.db_delete_oauth_app(token_id)

    def add_oauth_app(self, token_id, client_id, client_secret,
                      auth_endpoint, token_endpoint, refresh_endpoint,
                      callback_endpoint, scope, shell_integration=True):
        return self.backend.db_post_oauth_app(token_id, client_id, client_secret, auth_endpoint, token_endpoint,
                                              refresh_endpoint, callback_endpoint, scope, shell_integration)

    def list_oauth_tokens(self):
        return self.backend.db_list_oauth_tokens()

    def get_oauth_token(self, token_id):
        return self.backend.db_get_oauth_token(token_id)

    def update_oauth_token(self, token_id, token_data):
        return self.backend.db_update_oauth_token(token_id, token_data)

    def delete_oauth_token(self, token_id):
        return self.backend.db_delete_oauth_token(token_id)

    def add_oauth_token(self, token_id, token_data):
        return self.backend.db_post_oauth_token(token_id, token_data)

    def list_stt_recordings(self):
        return self.backend.db_list_stt_recordings()

    def get_stt_recording(self, rec_id):
        return self.backend.db_get_stt_recording(rec_id)

    def update_stt_recording(self, rec_id, transcription=None, metadata=None):
        return self.backend.db_update_stt_recording(rec_id, transcription, metadata)

    def delete_stt_recording(self, rec_id):
        return self.backend.db_delete_stt_recording(rec_id)

    def add_stt_recording(self, byte_data, transcription, metadata=None):
        return self.backend.db_post_stt_recording(byte_data, transcription, metadata)

    def list_ww_recordings(self):
        return self.backend.db_list_ww_recordings()

    def get_ww_recording(self, rec_id):
        return self.backend.db_get_ww_recording(rec_id)

    def update_ww_recording(self, rec_id, transcription=None, metadata=None):
        return self.backend.db_update_ww_recording(rec_id, transcription, metadata)

    def delete_ww_recording(self, rec_id):
        return self.backend.db_delete_ww_recording(rec_id)

    def add_ww_recording(self, byte_data, transcription, metadata=None):
        return self.backend.db_post_ww_recording(byte_data, transcription, metadata)

    def list_metrics(self):
        return self.backend.db_list_metrics()

    def get_metric(self, metric_id):
        return self.backend.db_get_metric(metric_id)

    def update_metric(self, metric_id, metadata):
        return self.backend.db_update_metric(metric_id, metadata)

    def delete_metric(self, metric_id):
        return self.backend.db_delete_metric(metric_id)

    def add_metric(self, metric_type, metadata):
        return self.backend.db_post_metric(metric_type, metadata)

    def list_ww_definitions(self):
        return self.backend.db_list_ww_definitions()

    def get_ww_definition(self, ww_id):
        return self.backend.db_get_ww_definition(ww_id)

    def update_ww_definition(self, ww_id, name, lang, ww_config, plugin):
        return self.backend.db_update_ww_definition(ww_id, name, lang, ww_config, plugin)

    def delete_ww_definition(self, ww_id):
        return self.backend.db_delete_ww_definition(ww_id)

    def add_ww_definition(self, name, lang, ww_config, plugin):
        return self.backend.db_post_ww_definition(name, lang, ww_config, plugin)

    def list_voice_definitions(self):
        return self.backend.db_list_voice_definitions()

    def get_voice_definition(self, voice_id):
        return self.backend.db_get_voice_definition(voice_id)

    def update_voice_definition(self, voice_id, name=None, lang=None, plugin=None,
                                tts_config=None, offline=None, gender=None):
        return self.backend.db_update_voice_definition(voice_id, name, lang, plugin, tts_config, offline, gender)

    def delete_voice_definition(self, voice_id):
        return self.backend.db_delete_voice_definition(voice_id)

    def add_voice_definition(self, name, lang, plugin,
                             tts_config, offline, gender=None):
        return self.backend.db_post_voice_definition(name, lang, plugin, tts_config, offline, gender)


if __name__ == "__main__":
    # d = DeviceApi(FAKE_BACKEND_URL)

    # TODO turn these into unittests
    # voice_id = load_identity()
    # paired = is_paired()
    geo = GeolocationApi(backend_type=BackendType.OFFLINE)
    data = geo.get_geolocation("Missouri Kansas")
    print(data)
    exit(6)
    wolf = WolframAlphaApi(backend_type=BackendType.OFFLINE)
    # data = wolf.spoken("what is the speed of light")
    # print(data)
    # data = wolf.full_results("2+2")
    # print(data)

    owm = OpenWeatherMapApi(backend_type=BackendType.OFFLINE)
    data = owm.get_current()
    print(data)
    data = owm.get_weather()
    print(data)
