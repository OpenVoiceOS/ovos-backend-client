import enum
import json
from copy import deepcopy

from json_database import JsonStorageXDG, JsonDatabaseXDG
from ovos_config.config import Configuration
from ovos_backend_client.identity import IdentityManager


class AudioTag(str, enum.Enum):
    UNTAGGED = "untagged"
    WAKE_WORD = "wake_word"
    SPEECH = "speech"
    NOISE = "noise"
    SILENCE = "silence"


class SpeakerTag(str, enum.Enum):
    UNTAGGED = "untagged"
    MALE = "male"
    FEMALE = "female"
    CHILDREN = "children"


class OAuthTokenDatabase(JsonStorageXDG):
    """ This helper class creates ovos-config-assistant/ovos-backend-manager compatible json databases
        This allows users to use oauth even when not using a backend"""

    def __init__(self):
        super().__init__("ovos_oauth")

    def add_token(self, oauth_service, token_data):
        self[oauth_service] = token_data

    def total_tokens(self):
        return len(self)


class OAuthApplicationDatabase(JsonStorageXDG):
    """ This helper class creates ovos-config-assistant/ovos-backend-manager compatible json databases
        This allows users to use oauth even when not using a backend"""

    def __init__(self):
        super().__init__("ovos_oauth_apps")

    def add_application(self, oauth_service,
                        client_id, client_secret,
                        auth_endpoint, token_endpoint, refresh_endpoint,
                        callback_endpoint, scope, shell_integration=True):
        self[oauth_service] = {"oauth_service": oauth_service,
                               "client_id": client_id,
                               "client_secret": client_secret,
                               "auth_endpoint": auth_endpoint,
                               "token_endpoint": token_endpoint,
                               "refresh_endpoint": refresh_endpoint,
                               "callback_endpoint": callback_endpoint,
                               "scope": scope,
                               "shell_integration": shell_integration}

    def total_apps(self):
        return len(self)


class Metric:
    def __init__(self, metric_id, metric_type, meta=None, uuid="AnonDevice"):
        if isinstance(meta, str):
            meta = json.loads(meta)
        self.metric_id = metric_id
        self.metric_type = metric_type
        self.meta = meta or {}
        self.uuid = uuid


class JsonMetricDatabase(JsonDatabaseXDG):
    def __init__(self):
        super().__init__("ovos_metrics")

    def add_metric(self, metric_type=None, meta=None, uuid="AnonDevice"):
        metric_id = self.total_metrics() + 1
        metric = Metric(metric_id, metric_type, meta, uuid)
        self.add_item(metric)
        return metric

    def total_metrics(self):
        return len(self)

    def __enter__(self):
        """ Context handler """
        return self

    def __exit__(self, _type, value, traceback):
        """ Commits changes and Closes the session """
        try:
            self.commit()
        except Exception as e:
            print(e)


class WakeWordRecording:
    def __init__(self, wakeword_id, transcription, path, meta=None,
                 uuid="AnonDevice", tag=AudioTag.UNTAGGED, speaker_type=SpeakerTag.UNTAGGED):
        self.wakeword_id = wakeword_id
        self.transcription = transcription
        self.path = path
        if isinstance(meta, str):
            meta = json.loads(meta)
        self.meta = meta or []
        self.uuid = uuid
        self.tag = tag
        self.speaker_type = speaker_type


class UtteranceRecording:
    def __init__(self, utterance_id, transcription, path, uuid="AnonDevice"):
        self.utterance_id = utterance_id
        self.transcription = transcription
        self.path = path
        self.uuid = uuid


class JsonWakeWordDatabase(JsonDatabaseXDG):
    def __init__(self):
        super().__init__("ovos_wakewords")

    def add_wakeword(self, transcription, path, meta=None,
                     uuid="AnonDevice", tag=AudioTag.UNTAGGED,
                     speaker_type=SpeakerTag.UNTAGGED):
        wakeword_id = self.total_wakewords() + 1
        wakeword = WakeWordRecording(wakeword_id, transcription, path, meta, uuid, tag, speaker_type)
        self.add_item(wakeword)

    def total_wakewords(self):
        return len(self)

    def __enter__(self):
        """ Context handler """
        return self

    def __exit__(self, _type, value, traceback):
        """ Commits changes and Closes the session """
        try:
            self.commit()
        except Exception as e:
            print(e)


class JsonUtteranceDatabase(JsonDatabaseXDG):
    def __init__(self):
        super().__init__("ovos_utterances")

    def add_utterance(self, transcription, path, uuid="AnonDevice"):
        utterance_id = self.total_utterances() + 1
        utterance = UtteranceRecording(utterance_id, transcription,
                                       path, uuid)
        self.add_item(utterance)

    def total_utterances(self):
        return len(self)

    def __enter__(self):
        """ Context handler """
        return self

    def __exit__(self, _type, value, traceback):
        """ Commits changes and Closes the session """
        try:
            self.commit()
        except Exception as e:
            print(e)


class SkillSettings:
    """ represents skill settings for a individual skill"""

    def __init__(self, skill_id, skill_settings=None,
                 meta=None, display_name=None, remote_id=None):
        self.skill_id = skill_id
        self.display_name = display_name or self.skill_id
        self.settings = skill_settings or {}
        self.remote_id = remote_id or skill_id
        if not self.remote_id.startswith("@"):
            self.remote_id = f"@|{self.remote_id}"
        self.meta = meta or {}

    @property
    def path(self):
        # TODO - xdg path
        return f"{self.skill_id}/settings.json"

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def serialize(self):
        # settings meta with updated placeholder values from settings
        # old style selene db stored skill settings this way
        meta = deepcopy(self.meta)
        for idx, section in enumerate(meta.get('sections', [])):
            for idx2, field in enumerate(section["fields"]):
                if "value" not in field:
                    continue
                if field["name"] in self.settings:
                    meta['sections'][idx]["fields"][idx2]["value"] = self.settings[field["name"]]
        return {'skillMetadata': meta,
                "skill_gid": self.remote_id,
                "display_name": self.display_name}

    @staticmethod
    def deserialize(data):
        if isinstance(data, str):
            data = json.loads(data)

        skill_json = {}
        skill_meta = data.get("skillMetadata") or {}
        for s in skill_meta.get("sections", []):
            for f in s.get("fields", []):
                if "name" in f and "value" in f:
                    val = f["value"]
                    if isinstance(val, str):
                        t = f.get("type", "")
                        if t == "checkbox":
                            if val.lower() == "true" or val == "1":
                                val = True
                            else:
                                val = False
                        elif t == "number":
                            if val == "False":
                                val = 0
                            elif val == "True":
                                val = 1
                            else:
                                val = float(val)
                        elif val.lower() in ["none", "null", "nan"]:
                            val = None
                        elif val == "[]":
                            val = []
                        elif val == "{}":
                            val = {}
                    skill_json[f["name"]] = val

        remote_id = data.get("skill_gid") or data.get("identifier")
        # this is a mess, possible keys seen by logging data
        # - @|XXX
        # - @{uuid}|XXX
        # - XXX

        # where XXX has been observed to be
        # - {skill_id}  <- ovos-core
        # - {msm_name} <- mycroft-core
        #   - {mycroft_marketplace_name} <- all default skills
        #   - {MycroftSkill.name} <- sometimes sent to msm (very uncommon)
        #   - {skill_id.split(".")[0]} <- fallback msm name
        # - XXX|{branch} <- append by msm (?)
        # - {whatever we feel like uploading} <- SeleneCloud utils
        fields = remote_id.split("|")
        skill_id = fields[0]
        if len(fields) > 1 and fields[0].startswith("@"):
            skill_id = fields[1]

        display_name = data.get("display_name") or \
                       skill_id.split(".")[0].replace("-", " ").replace("_", " ").title()

        return SkillSettings(skill_id, skill_json, skill_meta, display_name,
                             remote_id=remote_id)


class DeviceSettings:
    """ global device settings
    represent some fields from mycroft.conf but also contain some extra fields
    """
    def __init__(self):
        identity = IdentityManager.get()

        default_ww = Configuration.get("listener", {}).get("wake_word", "hey_mycroft")
        default_tts = Configuration.get("tts", {}).get("module", "ovos-tts-plugin-mimic3-server")

        self.uuid = identity["uuid"]
        self.token = identity["access"]

        # ovos exclusive
        # individual skills can also control this via "__shared_settings" flag
        self.isolated_skills = True

        # extra device info
        self.name = f"Device-{self.uuid}"  # friendly device name
        self.device_location = "somewhere"  # indoor location
        mail_cfg = Configuration.get("email", {})
        self.email = mail_cfg.get("recipient") or \
                     mail_cfg.get("smtp", {}).get("username")
        # mycroft.conf values
        self.date_format = Configuration.get("date_format") or "DMY"
        self.system_unit = Configuration.get("system_unit") or "metric"
        self.time_format = Configuration.get("time_format") or "full"
        self.opt_in = Configuration.get("opt_in") or False
        self.lang = Configuration.get("lang") or "en-us"
        self.location = Configuration["location"]

        # default config values
        # these are usually set in selene during pairing process

        # tts - 'ttsSettings': {'mimic2': {'voice': 'kusal'}, 'module': 'mimic2'}
        self.default_tts = default_tts
        self.default_tts_cfg = Configuration.get("tts", {}).get(default_tts, {})

        # wake word -  selene returns the full listener config, supports only a single wake word, and support only pocketsphinx....
        # 'listenerSetting': {
        # 'channels': 1, 'energyRatio': 1.5, 'multiplier': 1,  'sampleRate': 16000,
        # 'uuid': 'd5b2cd4c-c3f1-4afb-b4e0-9212d322786e',   # <- unique ww uuid in selene db (?)
        # 'phonemes': '...',
        # 'threshold': '...',
        # 'wakeWord': '...'}
        self.default_ww = default_ww.replace(" ", "_")
        # this needs to be done due to the convoluted logic in core, a _ will be added in config hotwords section and cause a mismatch otherwise
        self.default_ww_cfg = Configuration.get("hotwords", {}).get(default_ww, {})

    @property
    def selene_device(self):
        return {
            "description": self.device_location,
            "uuid": self.uuid,
            "name": self.name,

            # not tracked / meaningless
            # just for api compliance with selene
            'coreVersion': "unknown",
            'platform': 'unknown',
            'enclosureVersion': "",
            "user": {"uuid": self.uuid}  # users not tracked
        }

    @property
    def selene_settings(self):
        # this endpoint corresponds to a mycroft.conf
        # location is usually grabbed in a separate endpoint
        # in here we return it in case downstream is
        # aware of this and wants to save 1 http call

        # NOTE - selene returns the full listener config
        # this SHOULD NOT be done, since backend has no clue of hardware downstream
        # we return only wake word config
        if self.default_ww and self.default_ww_cfg:
            ww_cfg = {self.default_ww: self.default_ww_cfg}
            listener = {"wakeWord": self.default_ww.replace(" ", "_")}
        else:
            ww_cfg = {}
            listener = {}

        tts_config = dict(self.default_tts_cfg)
        if "module" in tts_config:
            tts = tts_config.pop("module")
            tts_settings = {"module": tts, tts: tts_config}
        else:
            tts_settings = {}
        return {
            "dateFormat": self.date_format,
            "optIn": self.opt_in,
            "systemUnit": self.system_unit,
            "timeFormat": self.time_format,
            "uuid": self.uuid,
            "lang": self.lang,
            "location": self.location,
            "listenerSetting": listener,
            "hotwordsSetting": ww_cfg,  # not present in selene, parsed correctly by core
            'ttsSettings': tts_settings
        }

    def serialize(self):
        return self.__dict__

    @staticmethod
    def deserialize(data):
        if isinstance(data, str):
            data = json.loads(data)
        return DeviceSettings(**data)
