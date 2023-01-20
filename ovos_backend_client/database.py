import os
from os.path import join

from json_database import JsonStorageXDG, JsonDatabaseXDG
from ovos_config.config import Configuration
from ovos_utils.configuration import get_xdg_data_save_path


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


class BackendDatabase:
    """ This helper class creates ovos-config-assistant/ovos-backend-manager compatible json databases
    This allows users to visualize metrics, tag wake words and configure devices
    even when not using a backend"""

    def __init__(self, uuid):
        self.uuid = uuid

    def update_device_db(self, data):
        with JsonStorageXDG("ovos_preferences", subfolder="OpenVoiceOS") as db:
            db.update(data)
        cfg = Configuration()
        tts = cfg.get("tts", {}).get("module")
        ww = cfg.get("listener", {}).get("wake_word", "hey_mycroft")

        with JsonStorageXDG("ovos_devices") as db:
            skips = ["state", "coreVersion", "platform", "platform_build", "enclosureVersion"]
            default = {
                "uuid": self.uuid,
                "isolated_skills": True,
                "name": "LocalDevice",
                "device_location": "127.0.0.1",
                "email": "",
                "date_format": cfg.get("date_format") or "DMY",
                "time_format": cfg.get("time_format") or "full",
                "system_unit": cfg.get("system_unit") or "metric",
                "opt_in": cfg.get("opt_in", False),
                "lang": cfg.get("lang", "en-us"),
                "location": cfg.get("location", {}),
                "default_tts": tts,
                "default_tts_cfg": cfg.get("tts", {}).get(tts, {}),
                "default_ww": ww,
                "default_ww_cfg": cfg.get("hotwords", {}).get(ww, {})
            }
            data = {k: v if k not in data else data[k]
                    for k, v in default.items() if k not in skips}
            db[self.uuid] = data

    def update_metrics_db(self, name, data):
        # shared with personal backend for UI compat
        with JsonDatabaseXDG("ovos_metrics") as db:
            db.add_item({
                "metric_id": len(db) + 1,
                "uuid": self.uuid,
                "metric_type": name,
                "meta": data
            })

    def update_ww_db(self, params):
        listener_config = Configuration().get("listener", {})
        save_path = listener_config.get('save_path', f"{get_xdg_data_save_path()}/listener")
        saved_wake_words_dir = join(save_path, 'wake_words')
        filename = join(saved_wake_words_dir,
                        '_'.join(str(params[k]) for k in sorted(params)) +
                        '.wav')
        if os.path.isfile(filename):
            with JsonDatabaseXDG("ovos_wakewords") as db:
                db.add_item({
                    "wakeword_id": len(db) + 1,
                    "uuid": self.uuid,
                    "meta": params,
                    "path": filename,
                    "transcription": params["name"]
                })
        return filename
