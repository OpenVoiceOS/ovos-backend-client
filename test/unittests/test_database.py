import unittest

from os import environ
from os.path import join, dirname, exists, basename, isdir
from shutil import rmtree


class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cache_test_dir = join(dirname(__file__), "text_xdg_cache")
        environ['XDG_CACHE_HOME'] = cache_test_dir

    @classmethod
    def tearDownClass(cls) -> None:
        test_path = environ.pop('XDG_CACHE_HOME')
        if isdir(test_path):
            rmtree(test_path)

    def test_metric_model(self):
        from ovos_backend_client.database import MetricModel
        # TODO

    def test_ww_recording_model(self):
        from ovos_backend_client.database import WakeWordRecordingModel
        # TODO

    def test_utterance_recording_model(self):
        from ovos_backend_client.database import UtteranceRecordingModel
        # TODO

    def test_skill_settings_model(self):
        from ovos_backend_client.database import SkillSettingsModel
        # TODO

    def test_device_model(self):
        from ovos_backend_client.database import DeviceModel
        # TODO

    def test_json_metric_database(self):
        from ovos_backend_client.database import JsonMetricDatabase
        test_db = JsonMetricDatabase()
        test_db.add_metric("test")
        self.assertEqual(test_db.total_metrics(), 1)
        self.assertFalse(exists(test_db.path))
        self.assertEqual(basename(test_db.path), "ovos_metrics.jsondb")
        test_db.commit()
        self.assertTrue(exists(test_db.path))
        # TODO: Test enter/exit

    def test_json_wake_word_database(self):
        from ovos_backend_client.database import JsonWakeWordDatabase
        test_db = JsonWakeWordDatabase()
        test_db.add_wakeword("test", __file__)
        self.assertEqual(test_db.total_wakewords(), 1)
        self.assertEqual(test_db.get_wakeword(0).path, __file__)
        self.assertFalse(exists(test_db.path))
        self.assertEqual(basename(test_db.path), "ovos_wakewords.jsondb")
        test_db.commit()
        self.assertTrue(exists(test_db.path))
        # TODO: Test enter/exit, update, delete

    def test_json_utterance_database(self):
        from ovos_backend_client.database import JsonUtteranceDatabase
        test_db = JsonUtteranceDatabase()
        test_db.add_utterance("test", __file__)
        self.assertEqual(test_db.total_utterances(), 1)
        self.assertEqual(test_db.get_utterance(0).path, __file__)
        self.assertFalse(exists(test_db.path))
        self.assertEqual(basename(test_db.path), "ovos_utterances.jsondb")
        test_db.commit()
        self.assertTrue(exists(test_db.path))
        # TODO: Test enter/exit, update, delete

    def test_oauth_token_database(self):
        from ovos_backend_client.database import OAuthTokenDatabase
        test_db = OAuthTokenDatabase()
        test_db.add_token("test_id", "test_data")
        self.assertEqual(test_db.get_token("test_id"), "test_data")
        self.assertEqual(test_db.total_tokens(), 1)
        test_db.update_token("test_id", "new_data")
        self.assertEqual(test_db.get_token("test_id"), "new_data")
        self.assertEqual(test_db.total_tokens(), 1)
        self.assertFalse(exists(test_db.path))
        self.assertEqual(basename(test_db.path), "ovos_oauth.json")
        test_db.store()
        self.assertTrue(exists(test_db.path))
        self.assertTrue(test_db.delete_token("test_id"))
        self.assertFalse(test_db.delete_token("test_id"))

    def test_oauth_application_database(self):
        from ovos_backend_client.database import OAuthApplicationDatabase
        test_db = OAuthApplicationDatabase()
        test_application = {"oauth_service": "test_service",
                            "client_id": "test_client",
                            "client_secret": "test_secret",
                            "auth_endpoint": "test_endpoint",
                            "token_endpoint": "test_token",
                            "callback_endpoint": "test_callback",
                            "scope": "test_scope",
                            "shell_integration": True}
        test_db.add_application(**test_application)
        self.assertEqual(test_db.get_application("test_service"),
                         test_application)
        self.assertEqual(test_db.total_apps(), 1)

        self.assertFalse(exists(test_db.path))
        self.assertEqual(basename(test_db.path), "ovos_oauth_apps.json")
        test_db.store()
        self.assertTrue(exists(test_db.path))
        self.assertTrue(test_db.delete_application("test_service"))
        self.assertFalse(test_db.delete_application("test_service"))

    def test_update_oauth_application_database(self):
        from ovos_backend_client.database import OAuthApplicationDatabase
        test_db = OAuthApplicationDatabase()
        test_application = {"oauth_service": "test_service",
                            "client_id": "test_client",
                            "client_secret": "test_secret",
                            "auth_endpoint": "test_endpoint",
                            "token_endpoint": "test_token",
                            "callback_endpoint": "test_callback",
                            "scope": "test_scope",
                            "shell_integration": True}
        test_db.add_application(**test_application)
        test_application["client_id"] = "test_client2"
        test_db.update_application(**test_application)
        self.assertEqual(test_db.get_application("test_service"),
                         test_application)
        self.assertEqual(test_db.total_apps(), 1)

        self.assertEqual(basename(test_db.path), "ovos_oauth_apps.json")
