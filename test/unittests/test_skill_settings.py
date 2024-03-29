import unittest

from ovos_backend_client.database import SkillSettingsModel


class TestSkillSettings(unittest.TestCase):

    def test_deserialize(self):
        meta = {"sections": [
            {
                "fields": [
                    {"name": "test", "value": True}
                ]
            }
        ]}

        data = {
            "skillMetadata": meta,
            "skill_gid": "@|test_skill"
        }
        s = SkillSettingsModel.deserialize(data)
        self.assertEqual(s.display_name, "Test Skill")
        self.assertEqual(s.skill_id, "test_skill")
        self.assertEqual(s.remote_id, "@|test_skill")
        self.assertEqual(s.skill_settings, {"test": True})
        self.assertEqual(s.meta, meta)

        old_data = {
            "skillMetadata": meta,
            "display_name": "Test Skill",
            "identifier": "@|test_skill"
        }
        s = SkillSettingsModel.deserialize(old_data)
        self.assertEqual(s.display_name, "Test Skill")
        self.assertEqual(s.skill_id, "test_skill")
        self.assertEqual(s.remote_id, "@|test_skill")
        self.assertEqual(s.skill_settings, {"test": True})
        self.assertEqual(s.meta, meta)

    def test_serialize(self):
        meta = {"sections": [
            {
                "fields": [
                    {"name": "test", "value": False}
                ]
            }
        ]}
        settings = {"test": True}
        updated_meta = {"sections": [
            {
                "fields": [
                    {"name": "test", "value": True}
                ]
            }
        ]}

        s = SkillSettingsModel("test_skill", settings, meta, "Test Skill")
        self.assertEqual(s.skill_settings, settings)
        self.assertEqual(s.meta, meta)
        self.assertEqual(s.display_name, "Test Skill")
        self.assertEqual(s.skill_id, "test_skill")

        s2 = s.serialize()
        self.assertEqual(s.meta, meta)
        self.assertEqual(s2["display_name"], "Test Skill")
        self.assertEqual(s2["skill_gid"], "@|test_skill")
        self.assertEqual(s2['skillMetadata'], updated_meta)

    def test_skill_id(self):
        uuid = "jbgblnkl-dgsg-sgsdg-sgags"
        meta = {"sections": [
            {
                "fields": [
                    {"name": "test", "value": True}
                ]
            }
        ]}

        data = {
            "skillMetadata": meta,
            "skill_gid": "@|test_skill"
        }
        s = SkillSettingsModel.deserialize(data)
        self.assertEqual(s.skill_id, "test_skill")

        data = {
            "skillMetadata": meta,
            "skill_gid": f"@{uuid}|test_skill"
        }
        s = SkillSettingsModel.deserialize(data)
        self.assertEqual(s.skill_id, "test_skill")
        self.assertEqual(s.display_name, "Test Skill")

        data = {
            "skillMetadata": meta,
            "skill_gid": "@|test_skill|20.02"
        }
        s = SkillSettingsModel.deserialize(data)
        self.assertEqual(s.skill_id, "test_skill")
        self.assertEqual(s.display_name, "Test Skill")

        data = {
            "skillMetadata": meta,
            "skill_gid": f"@{uuid}|test_skill|20.02"
        }
        s = SkillSettingsModel.deserialize(data)
        self.assertEqual(s.skill_id, "test_skill")
        self.assertEqual(s.display_name, "Test Skill")

        data = {
            "skillMetadata": meta,
            "skill_gid": "test_skill"
        }
        s = SkillSettingsModel.deserialize(data)
        self.assertEqual(s.skill_id, "test_skill")
        self.assertEqual(s.remote_id, "@|test_skill")
        self.assertEqual(s.display_name, "Test Skill")

        data = {
            "skillMetadata": meta,
            "skill_gid": "test_skill.author"
        }
        s = SkillSettingsModel.deserialize(data)
        self.assertEqual(s.skill_id, "test_skill.author")
        self.assertEqual(s.remote_id, "@|test_skill.author")
        self.assertEqual(s.display_name, "Test Skill")

