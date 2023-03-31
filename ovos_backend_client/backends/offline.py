import json
from io import BytesIO, StringIO
from os import listdir, makedirs, remove
from os.path import isfile
from os.path import join
from tempfile import NamedTemporaryFile
from uuid import uuid4

import requests
import time
from ovos_config.config import Configuration
from ovos_config.config import update_mycroft_config
from ovos_config.locations import USER_CONFIG
from ovos_plugin_manager.stt import OVOSSTTFactory, get_stt_config
from ovos_utils.configuration import get_xdg_data_save_path
from ovos_utils.log import LOG
from ovos_utils.network_utils import get_external_ip
from ovos_utils.smtp_utils import send_smtp

from ovos_backend_client.backends.base import AbstractBackend, BackendType
from ovos_backend_client.database import JsonMetricDatabase, JsonWakeWordDatabase, \
    SkillSettings, OAuthTokenDatabase, OAuthApplicationDatabase, DeviceSettings
from ovos_backend_client.identity import IdentityManager


class OfflineBackend(AbstractBackend):

    def __init__(self, url="127.0.0.1", version="v1", identity_file=None, credentials=None):
        super().__init__(url, version, identity_file, BackendType.OFFLINE, credentials)
        self.stt = None

    # OWM API
    def owm_get_weather(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to configured location

        lat, lon = lat_lon or self._get_lat_lon()
        params = {
            "lang": lang,
            "units": units,
            "lat": lat, "lon": lon,
            "appid": self.credentials["owm"]
        }
        url = "https://api.openweathermap.org/data/2.5/onecall"
        response = self.get(url, params=params)
        return response.json()

    def owm_get_current(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to configured location

        lat, lon = lat_lon or self._get_lat_lon()
        params = {
            "lang": lang,
            "units": units,
            "lat": lat, "lon": lon,
            "appid": self.credentials["owm"]
        }
        url = "https://api.openweathermap.org/data/2.5/weather"
        response = self.get(url, params=params)
        return response.json()

    def owm_get_hourly(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to configured location

        lat, lon = lat_lon or self._get_lat_lon()
        params = {
            "lang": lang,
            "units": units,
            "lat": lat, "lon": lon,
            "appid": self.credentials["owm"]
        }
        url = "https://api.openweathermap.org/data/2.5/forecast"
        response = self.get(url, params=params)
        return response.json()

    def owm_get_daily(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to configured location

        lat, lon = lat_lon or self._get_lat_lon()
        params = {
            "lang": lang,
            "units": units,
            "lat": lat, "lon": lon,
            "appid": self.credentials["owm"]
        }
        url = "https://api.openweathermap.org/data/2.5/forecast/daily"
        response = self.get(url, params=params)
        return response.json()

    # Wolfram Alpha Api
    def wolfram_spoken(self, query, units="metric", lat_lon=None, optional_params=None):
        optional_params = optional_params or {}
        if not lat_lon:
            lat_lon = self._get_lat_lon(**optional_params)
        params = {'i': query,
                  "geolocation": "{},{}".format(*lat_lon),
                  'units': units,
                  **optional_params}
        url = 'https://api.wolframalpha.com/v1/spoken'
        params["appid"] = self.credentials["wolfram"]
        return self.get(url, params=params).text

    def wolfram_simple(self, query, units="metric", lat_lon=None, optional_params=None):
        optional_params = optional_params or {}
        if not lat_lon:
            lat_lon = self._get_lat_lon(**optional_params)
        params = {'i': query,
                  "geolocation": "{},{}".format(*lat_lon),
                  'units': units,
                  **optional_params}
        url = 'https://api.wolframalpha.com/v1/simple'
        params["appid"] = self.credentials["wolfram"]
        return self.get(url, params=params).text

    def wolfram_full_results(self, query, units="metric", lat_lon=None, optional_params=None):
        """Wrapper for the WolframAlpha Full Results v2 API.
        https://products.wolframalpha.com/api/documentation/
        Pods of interest
        - Input interpretation - Wolfram's determination of what is being asked about.
        - Name - primary name of
        """
        optional_params = optional_params or {}
        if not lat_lon:
            lat_lon = self._get_lat_lon(**optional_params)
        params = {'input': query,
                  "units": units,
                  "mode": "Default",
                  "format": "image,plaintext",
                  "geolocation": "{},{}".format(*lat_lon),
                  "output": "json",
                  **optional_params}
        url = 'https://api.wolframalpha.com/v2/query'
        params["appid"] = self.credentials["wolfram"]
        data = self.get(url, params=params)
        return data.json()

    # Geolocation Api
    def geolocation_get(self, location):
        """Call the geolocation endpoint.

        Args:
            location (str): the location to lookup (e.g. Kansas City Missouri)

        Returns:
            str: JSON structure with lookup results
        """
        url = "https://nominatim.openstreetmap.org/search"
        data = self.get(url, params={"q": location, "format": "json", "limit": 1}).json()[0]
        url = "https://nominatim.openstreetmap.org/details.php?osmtype=W&osmid=38210407&format=json"
        details = self.get(url, params={"osmid": data['osm_id'], "osmtype": data['osm_type'][0].upper(),
                                        "format": "json"}).json()

        location = {
            "city": {
                "code": details["addresstags"].get("postcode") or details["calculated_postcode"] or "",
                "name": details["localname"],
                "state": {
                    "code": details["addresstags"].get("state_code") or details["calculated_postcode"] or "",
                    "name": details["addresstags"].get("state") or data["display_name"].split(", ")[0],
                    "country": {
                        "code": details["country_code"].upper() or details["addresstags"].get("country"),
                        "name": data["display_name"].split(", ")[-1]
                    }
                }
            },
            "coordinate": {
                "latitude": data["lat"],
                "longitude": data["lon"]
            }
        }
        if "timezone" not in location:
            location["timezone"] = self._get_timezone(
                lon=location["coordinate"]["longitude"],
                lat=location["coordinate"]["latitude"])
        return location

    def reverse_geolocation_get(self, lat, lon):
        """Call the reverse geolocation endpoint.

        Args:
            lat (float): latitude
            lon (float): longitude

        Returns:
            str: JSON structure with lookup results
        """
        url = "https://nominatim.openstreetmap.org/reverse"
        details = self.get(url, params={"lat": lat, "lon": lon, "format": "json"}).json()
        address = details.get("address")
        location = {
            "address": details["display_name"],
            "city": {
                "code": address.get("postcode") or "",
                "name": address.get("city") or
                        address.get("village") or
                        address.get("county") or "",
                "state": {
                    "code": address.get("state_code") or
                            address.get("ISO3166-2-lvl4") or
                            address.get("ISO3166-2-lvl6")
                            or "",
                    "name": address.get("state") or
                            address.get("county")
                            or "",
                    "country": {
                        "code": address.get("country_code") or "",
                        "name": address.get("country") or "",
                    }
                }
            },
            "coordinate": {
                "latitude": details.get("lat") or lat,
                "longitude": details.get("lon") or lon
            }
        }
        if "timezone" not in location:
            location["timezone"] = self._get_timezone(
                lon=location["coordinate"]["longitude"],
                lat=location["coordinate"]["latitude"])
        return location

    def ip_geolocation_get(self, ip):
        """Call the geolocation endpoint.

        Args:
            ip (str): the ip address to lookup

        Returns:
            str: JSON structure with lookup results
        """
        if not ip or ip in ["0.0.0.0", "127.0.0.1"]:
            ip = get_external_ip()
        fields = "status,country,countryCode,region,regionName,city,lat,lon,timezone,query"
        data = requests.get("http://ip-api.com/json/" + ip,
                            params={"fields": fields}).json()
        region_data = {"code": data["region"],
                       "name": data["regionName"],
                       "country": {
                           "code": data["countryCode"],
                           "name": data["country"]}}
        city_data = {"code": data["city"],
                     "name": data["city"],
                     "state": region_data}
        timezone_data = {"code": data["timezone"],
                         "name": data["timezone"]}
        coordinate_data = {"latitude": float(data["lat"]),
                           "longitude": float(data["lon"])}
        return {"city": city_data,
                "coordinate": coordinate_data,
                "timezone": timezone_data}

    # Device Api
    def device_get(self):
        """ Retrieve all device information from the json db"""
        device = DeviceSettings()
        return device.selene_device

    def device_get_settings(self):
        """ Retrieve device settings information from the json db

        Returns:
            str: JSON string with user configuration information.
        """
        device = DeviceSettings()
        return device.selene_settings

    def device_get_skill_settings_v1(self):
        """ old style bidirectional skill settings api, still available!"""
        return self.db_list_skill_settings(self.uuid)

    def device_put_skill_settings_v1(self, data=None):
        """ old style bidirectional skill settings api, still available!"""
        # update local db
        s = SkillSettings.deserialize(data)
        s.store()
        return {}

    def device_get_code(self, state=None):
        return "ABCDEF"  # dummy data

    def device_activate(self, state, token,
                        core_version="unknown",
                        platform="unknown",
                        platform_build="unknown",
                        enclosure_version="unknown"):
        identity = self.admin_pair(state)
        return identity

    def device_update_version(self,
                              core_version="unknown",
                              platform="unknown",
                              platform_build="unknown",
                              enclosure_version="unknown"):
        pass  # irrelevant info

    def device_report_metric(self, name, data):
        self.db_post_metric(name, data)

    def device_get_location(self):
        """ Retrieve device location information from Configuration

        Returns:
            str: JSON string with user location.
        """
        return Configuration().get("location") or {}

    def device_get_oauth_token(self, dev_cred):
        """
            Get Oauth token for dev_credential dev_cred.

            Argument:
                dev_cred:   development credentials identifier

            Returns:
                json string containing token and additional information
        """
        raise self.oauth_get_token(dev_cred)

    def device_get_skill_settings(self):
        """Get the remote skill settings for all skills on this device."""
        return {s.skill_id: s.settings
                for s in self._get_local_settings()}

    def device_upload_skill_metadata(self, settings_meta):
        """Upload skill metadata.

        Args:
            settings_meta (dict): skill info and settings in JSON format
        """
        s = SkillSettings.deserialize(settings_meta)
        old_s = self.db_get_skill_settings(self.uuid, s.skill_id)
        if old_s: # keep old settings value, update meta values only
            s.settings = old_s.settings
        s.save()

    def device_upload_skills_data(self, data):
        """ Upload skills.json file. This file contains a manifest of installed
        and failed installations for use with the Marketplace.

        Args:
             data: dictionary with skills data from msm
        """
        pass

    def device_upload_wake_word_v1(self, audio, params, upload_url=None):
        """ upload precise wake word V1 endpoint - url can be external to backend"""
        return self.dataset_upload_wake_word(audio, params, upload_url)

    def device_upload_wake_word(self, audio, params):
        """ upload precise wake word V2 endpoint - integrated with device api"""
        return self.dataset_upload_wake_word(audio, params)

    # Metrics API
    def metrics_upload(self, name, data):
        """ upload metrics"""
        return self.db_post_metric(name, data)

    # Dataset API
    def dataset_upload_wake_word(self, audio, params, upload_url=None):
        """ upload wake word sample - url can be external to backend"""
        byte_data = audio.get_wav_data()
        if Configuration().get("listener", {}).get('record_wake_words'):
            self.db_post_ww_recording(byte_data, params["name"], params)

        upload_url = upload_url or Configuration().get("listener", {}).get("wake_word_upload", {}).get("url")
        if upload_url:
            # upload to arbitrary server
            ww_files = {
                'audio': BytesIO(byte_data),
                'metadata': StringIO(json.dumps(params))
            }
            return self.post(upload_url, files=ww_files)
        return {}

    # Email API
    def email_send(self, title, body, sender):
        """ will raise KeyError if SMTP not configured in mycroft.conf"""
        body += f"\n\nsent by: {sender}"  # append skill_id info to body

        mail_config = self.credentials["email"]

        smtp_config = mail_config["smtp"]
        user = smtp_config["username"]
        pswd = smtp_config["password"]
        host = smtp_config["host"]
        port = smtp_config.get("port", 465)

        recipient = mail_config.get("recipient") or user

        send_smtp(user, pswd,
                  user, recipient,
                  title, body,
                  host, port)

    # OAuth API
    def oauth_get_token(self, dev_cred):
        """
            Get Oauth token for dev_credential dev_cred.

            Argument:
                dev_cred:   development credentials identifier

            Returns:
                json string containing token and additional information
        """
        return self.db_get_oauth_token(dev_cred)

    # Admin API
    def admin_pair(self, uuid=None):
        uuid = uuid or str(uuid4())
        # create dummy identity file for third parties expecting it for pairing checks
        identity = {"uuid": uuid,
                    "access": "OVOSdbF1wJ4jA5lN6x6qmVk_QvJPqBQZTUJQm7fYzkDyY_Y=",
                    "refresh": "OVOS66c5SpAiSpXbpHlq9HNGl1vsw_srX49t5tCv88JkhuE=",
                    "expires_at": time.time() + 9999999999}
        # save identity file
        IdentityManager.save(identity)
        return identity

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
        update_mycroft_config({"location": loc})

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
        cfg = dict(prefs)
        cfg["listener"] = {}
        cfg["hotwords"] = {}
        cfg["tts"] = {}
        tts = None
        tts_cfg = {}
        ww = None
        ww_cfg = {}
        if "wake_word" in cfg:
            ww = cfg.pop("wake_word")
        if "ww_config" in cfg:
            ww_cfg = cfg.pop("ww_config")
        if "tts_module" in cfg:
            tts = cfg.pop("tts_module")
        if "tts_config" in cfg:
            tts_cfg = cfg.pop("tts_config")
            if not tts:
                tts = tts_cfg.get("module")
        if tts:
            cfg["tts"]["module"] = tts
            cfg["tts"][tts] = tts_cfg
        if ww:
            cfg["listener"]["wake_word"] = ww
            cfg["hotwords"][ww] = ww_cfg
        update_mycroft_config(cfg)

    def admin_set_device_info(self, uuid, info):
        """
        info = {"opt_in": True,
                "name": "my_device",
                "device_location": "kitchen",
                "email": "notifications@me.com",
                "isolated_skills": False,
                "lang": "en-us"}
        """
        # TODO - email support in credentials
        update_mycroft_config({"opt_in": info["opt_in"],
                               "lang": info["lang"]})

    # STT Api
    def load_stt_plugin(self, config=None, lang=None):
        config = config or get_stt_config(config)
        if lang:
            config["lang"] = lang
        self.stt = OVOSSTTFactory.create(config)

    def stt_get(self, audio, language="en-us", limit=1):
        """ Web API wrapper for performing Speech to Text (STT)

        Args:
            audio (bytes): The recorded audio, as in a FLAC file
            language (str): A BCP-47 language code, e.g. "en-US"
            limit (int): Maximum alternate transcriptions

       """
        if self.stt is None:
            self.load_stt_plugin(lang=language)
        with NamedTemporaryFile() as fp:
            fp.write(audio)
            with AudioFile(fp.name) as source:
                audio = Recognizer().record(source)
        tx = self.stt.execute(audio, language)
        if isinstance(tx, str):
            tx = [tx]
        return tx

    # Database API
    def db_list_devices(self):
        _mail_cfg = Configuration.get("email", {})

        tts_plug = Configuration.get("tts").get("module")
        tts_config = Configuration.get("tts")[tts_plug]

        default_ww = Configuration.get("listener").get("wake_word", "hey_mycroft")
        ww_config = Configuration.get("hotwords")[default_ww]

        device = {
            "uuid": self.uuid,
            "token": "DUMMYTOKEN123",
            "isolated_skills": True,
            "opt_in": Configuration.get("opt_in", False),
            "name": f"Device-{self.uuid}",
            "device_location": "somewhere",
            "email": _mail_cfg.get("recipient") or
                     _mail_cfg.get("smtp", {}).get("username"),
            "time_format": Configuration.get("date_format", "full"),
            "date_format": Configuration.get("date_format", "DMY"),
            "system_unit": Configuration.get("system_unit", "metric"),
            "lang": Configuration.get("lang") or "en-us",
            "location": Configuration.get("location"),
            "default_tts": tts_plug,
            "default_tts_cfg": tts_config,
            "default_ww": default_ww,
            "default_ww_cfg": ww_config
        }
        return [device]

    def db_get_device(self, uuid):
        if uuid != self.uuid:
            return None
        return self.db_list_devices()[0]

    def db_update_device(self, uuid, name=None,
                         device_location=None, opt_in=None,
                         location=None, lang=None, date_format=None,
                         system_unit=None, time_format=None, email=None,
                         isolated_skills=False, ww_id=None, voice_id=None):
        if uuid != self.uuid:
            identity = self.admin_pair(uuid)
        new_config = {

        }
        if opt_in is not None:
            new_config["opt_in"] = opt_in
        if location is not None:
            new_config["location"] = location
        if lang is not None:
            new_config["lang"] = lang
        if time_format is not None:
            new_config["time_format"] = time_format
        if date_format is not None:
            new_config["date_format"] = date_format
        if system_unit is not None:
            new_config["system_unit"] = system_unit
        if email is not None:
            new_config["email"]["recipient"] = email
        if device_location is not None:
            pass  # not tracked locally, reserved for future usage
        if ww_id is not None:
            ww_def = self.db_get_ww_definition(ww_id)
            if ww_def:
                name = ww_def["name"]
                cfg = ww_def["ww_config"]
                if "module" not in cfg:
                    cfg["module"] = ww_def["plugin"]
                new_config["listener"]["wake_word"] = name
                new_config["hotwords"][name] = cfg

        if voice_id is not None:
            ww_def = self.db_get_voice_definition(voice_id)
            if ww_def:
                plugin = ww_def["plugin"]
                cfg = ww_def["tts_config"]
                # TODO - gender -> persona
                if ww_def.get("lang"):
                    cfg["lang"] = ww_def["lang"]
                new_config["tts"]["module"] = plugin
                new_config["tts"][plugin] = cfg
        update_mycroft_config(new_config)

    def db_delete_device(self, uuid):
        # delete identity file/user config/skill settings

        settings_path = f""  # TODO

        skill_ids = listdir(settings_path)

        # delete skill settings
        for skill_id in skill_ids:
            s = f"{settings_path}/{skill_id}/settings.json"
            if isfile(s):
                remove(s)

        if isfile(IdentityManager.IDENTITY_FILE):
            remove(IdentityManager.IDENTITY_FILE)

        if isfile(USER_CONFIG):
            remove(USER_CONFIG)

    def db_post_device(self, uuid, token, *args, **kwargs):
        return self.db_update_device(uuid, *args, **kwargs)

    def _get_local_settings(self):
        settings_path = f""  # TODO
        skill_ids = listdir(settings_path)
        all_settings = []
        for skill_id in skill_ids:
            s = f"{settings_path}/{skill_id}/settings.json"
            if isfile(s):
                with open(s) as f:
                    settings = json.load(f)
            s = SkillSettings(skill_id, settings)
            all_settings.append(s)
        return all_settings

    def db_list_shared_skill_settings(self):
        return [s.serialize() for s in self._get_local_settings()]

    def db_get_shared_skill_settings(self, skill_id):
        settings_path = f""  # TODO
        makedirs(settings_path, exist_ok=True)
        s = f"{settings_path}/{skill_id}/settings.json"
        with open(s) as f:
            settings_json = json.load(f)
        return SkillSettings(skill_id=skill_id,
                             skill_settings=settings_json).serialize()

    def db_update_shared_skill_settings(self, skill_id,
                                        display_name=None,
                                        settings_json=None,
                                        metadata_json=None):
        settings_path = f""  # TODO
        makedirs(settings_path, exist_ok=True)
        s = f"{settings_path}/{skill_id}/settings.json"
        with open(s, "w") as f:
            json.dump(settings_json, f)
        return SkillSettings(skill_id=skill_id,
                             skill_settings=settings_path,
                             meta=metadata_json,
                             display_name=display_name).serialize()

    def db_delete_shared_skill_settings(self, skill_id):
        settings_path = f""  # TODO
        makedirs(settings_path, exist_ok=True)
        s = f"{settings_path}/{skill_id}/settings.json"
        if isfile(s):
            remove(s)
            return True
        return False

    def db_post_shared_skill_settings(self, skill_id,
                                      display_name,
                                      settings_json,
                                      metadata_json):
        return self.db_update_shared_skill_settings(skill_id, display_name=display_name,
                                                    settings_json=settings_json, metadata_json=metadata_json)

    def db_list_skill_settings(self, uuid):
        return self.db_list_shared_skill_settings()

    def db_get_skill_settings(self, uuid, skill_id):
        return self.db_get_shared_skill_settings(skill_id)

    def db_update_skill_settings(self, uuid, skill_id,
                                 display_name=None,
                                 settings_json=None,
                                 metadata_json=None):
        return self.db_update_shared_skill_settings(skill_id, display_name=display_name,
                                                    settings_json=settings_json, metadata_json=metadata_json)

    def db_delete_skill_settings(self, uuid, skill_id):
        return self.db_delete_shared_skill_settings(skill_id)

    def db_post_skill_settings(self, uuid, skill_id,
                               display_name,
                               settings_json,
                               metadata_json):
        return self.db_post_shared_skill_settings(skill_id, display_name=display_name,
                                                  settings_json=settings_json, metadata_json=metadata_json)

    def db_list_oauth_apps(self):
        return OAuthApplicationDatabase().values()

    def db_get_oauth_app(self, token_id):
        raise NotImplementedError()

    def db_update_oauth_app(self, token_id, client_id=None, client_secret=None,
                            auth_endpoint=None, token_endpoint=None, refresh_endpoint=None,
                            callback_endpoint=None, scope=None, shell_integration=None):
        raise NotImplementedError()

    def db_delete_oauth_app(self, token_id):
        raise NotImplementedError()

    def db_post_oauth_app(self, token_id, client_id, client_secret,
                          auth_endpoint, token_endpoint, refresh_endpoint,
                          callback_endpoint, scope, shell_integration=True):
        raise NotImplementedError()

    def db_list_oauth_tokens(self):
        return OAuthTokenDatabase().values()

    def db_get_oauth_token(self, token_id):
        """
            Get Oauth token for dev_credential dev_cred.

            Argument:
                dev_cred:   development credentials identifier

            Returns:
                json string containing token and additional information
        """
        return OAuthTokenDatabase().get(token_id) or {}

    def db_update_oauth_token(self, token_id, token_data):
        raise NotImplementedError()

    def db_delete_oauth_token(self, token_id):
        raise NotImplementedError()

    def db_post_oauth_token(self, token_id, token_data):
        raise NotImplementedError()

    def db_list_stt_recordings(self):
        raise NotImplementedError()

    def db_get_stt_recording(self, rec_id):
        raise NotImplementedError()

    def db_update_stt_recording(self, rec_id, transcription=None, metadata=None):
        raise NotImplementedError()

    def db_delete_stt_recording(self, rec_id):
        raise NotImplementedError()

    def db_post_stt_recording(self, byte_data, transcription, metadata=None):
        raise NotImplementedError()

    def db_list_ww_recordings(self):
        raise NotImplementedError()

    def db_get_ww_recording(self, rec_id):
        raise NotImplementedError()

    def db_update_ww_recording(self, rec_id, transcription=None, metadata=None):
        raise NotImplementedError()

    def db_delete_ww_recording(self, rec_id):
        raise NotImplementedError()

    def db_post_ww_recording(self, byte_data, transcription, metadata=None):
        listener_config = Configuration().get("listener", {})
        save_path = listener_config.get('save_path', f"{get_xdg_data_save_path()}/listener")
        saved_wake_words_dir = join(save_path, 'wake_words')
        metadata = metadata or {}
        if metadata:
            filename = join(saved_wake_words_dir,
                            '_'.join(str(metadata[k]) for k in sorted(metadata)) +
                            '.wav')
            if isfile(filename):
                with JsonWakeWordDatabase() as db:
                    db.add_wakeword(metadata["name"], filename, metadata, self.uuid)

    def db_list_metrics(self):
        return JsonMetricDatabase().values()

    def db_get_metric(self, metric_id):
        return JsonMetricDatabase().get(metric_id)

    def db_update_metric(self, metric_id, metadata):
        m = self.db_get_metric(metric_id)
        m.meta = metadata
        with JsonMetricDatabase() as db:
            db[metric_id] = m

    def db_delete_metric(self, metric_id):
        with JsonMetricDatabase() as db:
            if metric_id in db:
                db.pop(metric_id)
                return True
        return False

    def db_post_metric(self, metric_type, metadata):
        with JsonMetricDatabase() as db:
            m = db.add_metric(metric_type, metadata, self.uuid)
        return m.serialize()

    def db_list_ww_definitions(self):
        raise NotImplementedError()

    def db_get_ww_definition(self, ww_id):
        raise NotImplementedError()

    def db_update_ww_definition(self, ww_id, name, ww_config, plugin):
        raise NotImplementedError()

    def db_delete_ww_definition(self, ww_id):
        raise NotImplementedError()

    def db_post_ww_definition(self, name, ww_config, plugin):
        raise NotImplementedError()

    def db_list_voice_definitions(self):
        raise NotImplementedError()

    def db_get_voice_definition(self, voice_id):
        raise NotImplementedError()

    def db_update_voice_definition(self, voice_id, name=None, lang=None, plugin=None,
                                   tts_config=None, offline=None, gender=None):
        raise NotImplementedError()

    def db_delete_voice_definition(self, voice_id):
        raise NotImplementedError()

    def db_post_voice_definition(self, name, lang, plugin,
                                 tts_config, offline, gender=None):
        raise NotImplementedError()



class AbstractPartialBackend(OfflineBackend):
    """ helper class that internally delegates unimplemented methods to offline backend implementation
    backends that only provide microservices and no DeviceApi should subclass from here
    """

    def __init__(self, url=None, version="v1", identity_file=None, backend_type=BackendType.OFFLINE, credentials=None):
        super().__init__(url, version, identity_file, credentials)
        self.backend_type = backend_type


if __name__ == "__main__":
    b = OfflineBackend()
    l = b.ip_geolocation_get("0.0.0.0")
    print(l)

    b.load_stt_plugin({"module": "ovos-stt-plugin-vosk"})
    # a = b.geolocation_get("Fafe")
    # a = b.wolfram_full_results("2+2")
    # a = b.wolfram_spoken("what is the speed of light")
    # a = b.owm_get_weather()

    from speech_recognition import Recognizer, AudioFile

    with AudioFile("/home/user/PycharmProjects/selene_api/test/test.wav") as source:
        audio = Recognizer().record(source)

    flac_data = audio.get_flac_data()
    a = b.stt_get(flac_data)

    # a = b.owm_get_weather()
    # a = b.owm_get_daily()
    # a = b.owm_get_hourly()
    # a = b.owm_get_current()
    print(a)
