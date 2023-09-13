import enum
import json
from copy import deepcopy

from json_database import JsonStorageXDG, JsonDatabaseXDG
from ovos_config.config import Configuration, get_xdg_config_save_path
from ovos_config.locations import get_xdg_config_save_path
from ovos_config.meta import get_xdg_base

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


class DatabaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__setattr__(k, v)

    def serialize(self):
        return self.__dict__

    @classmethod
    def deserialize(cls, kwargs):
        return cls(**kwargs)


class MetricModel(DatabaseModel):
    def __init__(self, metric_id, metric_type, meta=None, uuid="AnonDevice"):
        if isinstance(meta, str):
            meta = json.loads(meta)
        super().__init__(metric_id=metric_id, metric_type=metric_type, meta=meta, uuid=uuid)


class WakeWordRecordingModel(DatabaseModel):
    def __init__(self, wakeword_id, transcription, path, meta=None,
                 uuid="AnonDevice", tag=AudioTag.UNTAGGED, speaker_type=SpeakerTag.UNTAGGED):
        if isinstance(meta, str):
            meta = json.loads(meta)
        super().__init__(wakeword_id=wakeword_id, transcription=transcription,
                         path=path, meta=meta or [], uuid=uuid,
                         tag=tag, speaker_type=speaker_type)


class UtteranceRecordingModel(DatabaseModel):
    def __init__(self, utterance_id, transcription, path, uuid="AnonDevice"):
        super().__init__(utterance_id=utterance_id, transcription=transcription, path=path, uuid=uuid)


class SkillSettingsModel(DatabaseModel):
    """ represents skill settings for a individual skill"""

    def __init__(self, skill_id, skill_settings=None,
                 meta=None, display_name=None, remote_id=None):
        remote_id = remote_id or skill_id
        if not remote_id.startswith("@"):
            remote_id = f"@|{remote_id}"
        if isinstance(meta, str):
            meta = json.loads(meta)
        super().__init__(skill_id=skill_id, skill_settings=skill_settings or {},
                         meta=meta or {}, display_name=display_name or skill_id, remote_id=remote_id)

    def store(self):
        with open(f"{get_xdg_config_save_path()}/skills/{self.skill_id}/settings.json" "w") as f:
            json.dump(self.skill_settings, f, indent=4, ensure_ascii=False)
        # TODO - autogen meta if needed (?)
        with open(f"{get_xdg_config_save_path()}/skills/{self.skill_id}/settingsmeta.json" "w") as f:
            json.dump(self.meta, f, indent=4, ensure_ascii=False)

    def serialize(self):
        # settings meta with updated placeholder values from settings
        # old style selene db stored skill settings this way
        meta = deepcopy(self.meta)
        for idx, section in enumerate(meta.get('sections', [])):
            for idx2, field in enumerate(section["fields"]):
                if "value" not in field:
                    continue
                if field["name"] in self.skill_settings:
                    meta['sections'][idx]["fields"][idx2]["value"] = self.skill_settings[field["name"]]
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

        return SkillSettingsModel(skill_id, skill_json, skill_meta, display_name,
                                  remote_id=remote_id)


class DeviceModel(DatabaseModel):
    """ global device settings
    represent some fields from mycroft.conf but also contain some extra fields
    """

    def __init__(self):
        identity = IdentityManager.get()

        default_ww = Configuration().get("listener", {}).get("wake_word", "hey_mycroft")
        default_tts = Configuration().get("tts", {}).get("module", "ovos-tts-plugin-mimic3-server")
        mail_cfg = Configuration().get("email", {})

        uuid = identity.uuid
        super().__init__(uuid=uuid, token=identity.access,
                         isolated_skills=True,
                         name=f"Device-{uuid}",
                         device_location="somewhere",  # indoor location
                         email=mail_cfg.get("recipient") or \
                               mail_cfg.get("smtp", {}).get("username"),
                         date_format=Configuration().get("date_format") or "DMY",
                         system_unit=Configuration().get("system_unit") or "metric",
                         time_format=Configuration().get("time_format") or "full",
                         opt_in=Configuration().get("opt_in") or False,
                         lang=Configuration().get("lang") or "en-us",
                         location=Configuration["location"],
                         default_tts=default_tts,
                         default_tts_cfg=Configuration().get("tts", {}).get(default_tts, {}),
                         default_ww=default_ww.replace(" ", "_"),
                         default_ww_cfg=Configuration().get("hotwords", {}).get(default_ww, {})
                         )

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


class JsonMetricDatabase(JsonDatabaseXDG):
    def __init__(self):
        super().__init__("ovos_metrics", xdg_folder=get_xdg_base())

    def add_metric(self, metric_type=None, meta=None, uuid="AnonDevice"):
        metric_id = self.total_metrics() + 1
        metric = MetricModel(metric_id, metric_type, meta, uuid)
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


class JsonWakeWordDatabase(JsonDatabaseXDG):
    def __init__(self):
        super().__init__("ovos_wakewords", xdg_folder=get_xdg_base())

    def add_wakeword(self, transcription, path, meta=None,
                     uuid="AnonDevice", tag=AudioTag.UNTAGGED,
                     speaker_type=SpeakerTag.UNTAGGED):
        wakeword_id = self.total_wakewords() + 1
        wakeword = WakeWordRecordingModel(wakeword_id,
                                          transcription,
                                          path, meta, uuid,
                                          tag, speaker_type)
        self.add_item(wakeword)
        return wakeword

    def get_wakeword(self, rec_id):
        ww = self.get(rec_id)
        if ww:
            return WakeWordRecordingModel.deserialize(ww)
        return None

    def update_wakeword(self, rec_id, transcription=None, path=None,
                        meta=None, tag=AudioTag.UNTAGGED,
                        speaker_type=SpeakerTag.UNTAGGED):
        ww = self.get_wakeword(rec_id)
        if not ww:
            return None
        if transcription:
            ww.transcription = transcription
        if path:
            ww.path = path
        if tag:
            ww.tag = tag
        if speaker_type:
            ww.speaker_type = speaker_type
        self[rec_id] = ww.serialize()
        return ww

    def delete_wakeword(self, rec_id):
        if self.get(rec_id):
            self.pop(rec_id)
            return True
        return False

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
        super().__init__("ovos_utterances", xdg_folder=get_xdg_base())

    def add_utterance(self, transcription, path, uuid="AnonDevice"):
        utterance_id = self.total_utterances() + 1
        utterance = UtteranceRecordingModel(utterance_id, transcription,
                                            path, uuid)
        self.add_item(utterance)

    def get_utterance(self, rec_id):
        ww = self.get(rec_id)
        if ww:
            return UtteranceRecordingModel.deserialize(ww)
        return None

    def update_utterance(self, rec_id, transcription):
        ww = self.get_utterance(rec_id)
        if not ww:
            return None
        ww.transcription = transcription
        self[rec_id] = ww.serialize()
        return ww

    def delete_utterance(self, rec_id):
        if self.get(rec_id):
            self.pop(rec_id)
            return True
        return False

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


class OAuthTokenDatabase(JsonStorageXDG):
    """ This helper class creates ovos-config-assistant/ovos-backend-manager compatible json databases
        This allows users to use oauth even when not using a backend"""

    def __init__(self):
        super().__init__("ovos_oauth", xdg_folder=get_xdg_base())

    def add_token(self, token_id, token_data):
        self[token_id] = token_data

    def update_token(self, token_id, token_data):
        self.add_token(token_id, token_data)

    def get_token(self, token_id):
        return self.get(token_id)

    def delete_token(self, token_id):
        if token_id in self:
            self.pop(token_id)
            return True
        return False

    def total_tokens(self):
        return len(self)


class OAuthApplicationDatabase(JsonStorageXDG):
    """ This helper class creates ovos-config-assistant/ovos-backend-manager compatible json databases
        This allows users to use oauth even when not using a backend"""

    def __init__(self):
        super().__init__("ovos_oauth_apps", xdg_folder=get_xdg_base())

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

    def get_application(self, oauth_service):
        return self.get(oauth_service)

    def update_application(self, oauth_service,
                           client_id, client_secret,
                           auth_endpoint, token_endpoint, refresh_endpoint,
                           callback_endpoint, scope, shell_integration=True):
        self.update_application(oauth_service,
                                client_id, client_secret,
                                auth_endpoint, token_endpoint, refresh_endpoint,
                                callback_endpoint, scope, shell_integration)

    def delete_application(self, oauth_service):
        if oauth_service in self:
            self.pop(oauth_service)
            return True
        return False

    def total_apps(self):
        return len(self)
