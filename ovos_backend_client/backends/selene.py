from ovos_config.config import Configuration

from ovos_backend_client.backends.personal import PersonalBackend, BackendType

SELENE_API_URL = "https://api.mycroft.ai"
SELENE_PRECISE_URL = "https://training.mycroft.ai/precise/upload"


class SeleneBackend(PersonalBackend):

    def __init__(self, url=SELENE_API_URL, version="v1", identity_file=None, credentials=None):
        super().__init__(url, version, identity_file, credentials)
        self.backend_type = BackendType.SELENE

    # Device API
    def device_upload_wake_word_v1(self, audio, params, upload_url=None):
        """ upload precise wake word V1 endpoint - url can be external to backend"""
        # ensure default value for selene backend
        if not upload_url:
            config = Configuration().get("listener", {}).get("wake_word_upload", {})
            upload_url = config.get("url") or SELENE_PRECISE_URL
        return super().device_upload_wake_word_v1(audio, params, upload_url)

    # Admin API - NOT available, use home.mycroft.ai instead
    def admin_pair(self, uuid=None):
        raise RuntimeError(f"AdminAPI not available for {self.backend_type}")

    def admin_set_device_location(self, uuid, loc):
        raise RuntimeError(f"AdminAPI not available for {self.backend_type}")

    def admin_set_device_prefs(self, uuid, prefs):
        raise RuntimeError(f"AdminAPI not available for {self.backend_type}")

    def admin_set_device_info(self, uuid, info):
        raise RuntimeError(f"AdminAPI not available for {self.backend_type}")

    # Database API - NOT available to end users
    def db_list_devices(self):
        raise NotImplementedError()

    def db_get_device(self, uuid):
        raise NotImplementedError()

    def db_update_device(self, uuid, name=None,
                         device_location=None, opt_in=False,
                         location=None, lang=None, date_format=None,
                         system_unit=None, time_format=None, email=None,
                         isolated_skills=False, ww_id=None, voice_id=None):
        raise NotImplementedError()

    def db_delete_device(self, uuid):
        raise NotImplementedError()

    def db_post_device(self, uuid, token, name=None,
                       device_location="somewhere",
                       opt_in=Configuration.get("opt_in", False),
                       location=Configuration.get("location"),
                       lang=Configuration.get("lang"),
                       date_format=Configuration.get("date_format", "DMY"),
                       system_unit=Configuration.get("system_unit", "metric"),
                       time_format=Configuration.get("date_format", "full"),
                       email=None,
                       isolated_skills=False,
                       ww_id=None,
                       voice_id=None):
        raise NotImplementedError()

    def db_list_shared_skill_settings(self):
        raise NotImplementedError()

    def db_get_shared_skill_settings(self, skill_id):
        raise NotImplementedError()

    def db_update_shared_skill_settings(self, skill_id,
                                        display_name=None,
                                        settings_json=None,
                                        metadata_json=None):
        raise NotImplementedError()

    def db_delete_shared_skill_settings(self, skill_id):
        raise NotImplementedError()

    def db_post_shared_skill_settings(self, skill_id,
                                      display_name,
                                      settings_json,
                                      metadata_json):
        raise NotImplementedError()

    def db_list_skill_settings(self, uuid):
        raise NotImplementedError()

    def db_get_skill_settings(self, uuid, skill_id):
        raise NotImplementedError()

    def db_update_skill_settings(self, uuid, skill_id,
                                 display_name=None,
                                 settings_json=None,
                                 metadata_json=None):
        raise NotImplementedError()

    def db_delete_skill_settings(self, uuid, skill_id):
        raise NotImplementedError()

    def db_post_skill_settings(self, uuid, skill_id,
                               display_name,
                               settings_json,
                               metadata_json):
        raise NotImplementedError()

    def db_list_oauth_apps(self):
        raise NotImplementedError()

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
        raise NotImplementedError()

    def db_get_oauth_token(self, token_id):
        raise NotImplementedError()

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
        raise NotImplementedError()

    def db_list_metrics(self):
        raise NotImplementedError()

    def db_get_metric(self, metric_id):
        raise NotImplementedError()

    def db_update_metric(self, metric_id, metadata):
        raise NotImplementedError()

    def db_delete_metric(self, metric_id):
        raise NotImplementedError()

    def db_post_metric(self, metric_type, metadata):
        raise NotImplementedError()

    def db_list_ww_definitions(self):
        raise NotImplementedError()

    def db_get_ww_definition(self, ww_id):
        raise NotImplementedError()

    def db_update_ww_definition(self, ww_id, name=None, lang=None,
                                ww_config=None, plugin=None):
        raise NotImplementedError()

    def db_delete_ww_definition(self, ww_id):
        raise NotImplementedError()

    def db_post_ww_definition(self, name, lang, ww_config, plugin):
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
