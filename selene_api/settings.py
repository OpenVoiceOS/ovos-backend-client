import json
from copy import deepcopy
from os.path import join, isfile, dirname
from os import makedirs
from ovos_utils.configuration import get_xdg_config_save_path
from selene_api.api import DeviceApi


class RemoteSkillSettings:
    """ WARNING: selene backend does not use proper skill_id, if you have
    skills with same name but different author settings will overwrite each
    other on the backend, THIS CLASS IS NOT 100% SAFE in mycroft-core

    mycroft-core uses msm to generate weird metadata, removes author and munges github branch names into id
    ovos-core uses the proper deterministic skill_id and can be used safely
    if running in mycroft-core you want to use remote_id=self.settings_meta.skill_gid

    you can define arbitrary strings as skill_id to use this as a datastore

    skill matching is currently done by checking "if {skill_id} in string"
    """

    def __init__(self, skill_id, settings=None, meta=None, url=None, version="v1", remote_id=None):
        self.api = DeviceApi(url, version)
        self.skill_id = skill_id
        self.identifier = remote_id or \
                          self.selene_gid if not skill_id.startswith("@") else skill_id
        self.settings = settings or {}
        self.meta = meta or {}
        self.local_path = join(get_xdg_config_save_path(), 'skills', self.skill_id, 'settings.json')

    @property
    def selene_gid(self):
        if self.api.identity.uuid:
            return f'@{self.api.identity.uuid}|{self.skill_id}'
        return f'@|{self.skill_id}'

    @staticmethod
    def _settings2meta(settings):
        """ generates basic settingsmeta fields"""
        fields = []
        for k, v in settings.items():
            if k.startswith("_"):
                continue
            label = k.replace("-", " ").replace("_", " ").title()
            if isinstance(v, bool):
                fields.append({
                    "name": k,
                    "type": "checkbox",
                    "label": label,
                    "value": str(v).lower()
                })
            if isinstance(v, str):
                fields.append({
                    "name": k,
                    "type": "text",
                    "label": label,
                    "value": v
                })
            if isinstance(v, int) or isinstance(v, float):
                fields.append({
                    "name": k,
                    "type": "number",
                    "label": label,
                    "value": str(v)
                })
        return fields

    def generate_meta(self):
        """ auto generate settings meta info for any valid value defined in settings but missing in meta"""
        names = []
        for s in self.meta.get("sections", []):
            names += [f["name"] for f in s.get("fields", [])]
        new_meta = self._settings2meta(
            {k: v for k, v in self.settings.items()
             if k not in names and not k.startswith("_")})
        self.meta["sections"].append({"name": "Skill Settings", "fields": new_meta})
        # TODO auto update in backend ?

    def download(self):
        """
        download skill settings for this skill from selene

        WARNING: mycroft-core does not use proper skill_id, if you have
        skills with same name but different author settings will overwrite each
        other on the backend, THIS METHOD IS NOT SAFE in mycroft-core

        mycroft-core uses msm to generate weird metadata, removes author and munges github branch names into id
        if running in mycroft-core you want to use remote_id=self.settings_meta.skill_gid

        ovos-core uses the proper deterministic skill_id and can be used safely
        """
        data = self.api.get_skill_settings_v1()

        def match_settings(x, against):
            # this is a mess, possible keys seen by logging data
            # - @|XXX
            # - @{uuid}|XXX
            # - XXX

            # where XXX has been observed to be
            # - {skill_id}  <- ovos-core
            # - {MycroftSkill.name}
            # - {msm_name} <- mycroft-core
            # - XXX|{branch} <- append by msm (?)
            # - {whatever we feel like uploading} <- SeleneCloud utils

            for sets in x:
                fields = sets["identifier"].split("|")
                skill_id = fields[0]
                uuid = None
                if len(fields) >= 2 and fields[0].startswith("@"):
                    uuid = fields[0].replace("@", "")
                    skill_id = fields[1]

                # setting belong to another device
                if uuid and uuid != self.api.uuid:
                    # TODO shared_settings flag
                    # continue
                    pass

                if skill_id == against or sets["identifier"] == against:
                    return self.deserialize(sets)

        s = match_settings(data, self.identifier) or \
            match_settings(data, self.skill_id)

        if s:
            self.meta = s.meta
            self.settings = s.settings
            # update actual identifier from selene
            self.identifier = s.identifier

    def upload(self):
        data = self.serialize()
        return self.api.put_skill_settings_v1(data)

    def load(self):
        if not isfile(self.local_path):
            self.settings = {}
        else:
            with open(self.local_path) as f:
                self.settings = json.load(f)

    def store(self):
        makedirs(dirname(self.local_path), exist_ok=True)
        with open(self.local_path, "w") as f:
            json.dump(self.settings, f, indent=2)

    def get(self, key):
        return self.settings.get(key)

    def __str__(self):
        return str(self.settings)

    def __setitem__(self, key, value):
        self.settings[key] = value

    def __getitem__(self, item):
        return self.settings.get(item)

    def __dict__(self):
        return self.serialize()

    def serialize(self):
        meta = deepcopy(self.meta)
        for idx, section in enumerate(meta.get('sections', [])):
            for idx2, field in enumerate(section["fields"]):
                if "value" not in field:
                    continue
                if field["name"] in self.settings:
                    val = self.settings[field["name"]]
                    meta['sections'][idx]["fields"][idx2]["value"] = str(val)
        return {'skillMetadata': meta,
                "skill_gid": self.identifier,
                "display_name": self.skill_id}

    def deserialize(self, data):
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
                            val = float(val)
                        elif val.lower() in ["none", "null", "nan"]:
                            val = None
                        elif val == "[]":
                            val = []
                        elif val == "{}":
                            val = {}

                    skill_json[f["name"]] = val

        skill_id = remote_id = data.get("skill_gid") or \
                   data.get("identifier")  # deprecated

        fields = skill_id.split("|")
        skill_id = fields[0]
        if len(fields) > 1 and fields[0].startswith("@"):
            skill_id = fields[1]
        return RemoteSkillSettings(skill_id, skill_json, skill_meta, remote_id=remote_id,
                                   url=self.api.backend_url, version=self.api.backend_version)


if __name__ == "__main__":
    s = RemoteSkillSettings("mycroft-date-time")
    print(s.api.get_skill_settings_v1())
    s.download()
    print(s)
    s.settings["not"] = "yes"  # ignored, not in meta
    s.settings["show_time"] = True
    s.upload()
    s.download()
    print(s)
    s.settings["not"] = "yes"
    s.generate_meta()  # now in meta
    s.settings["not"] = "no"
    s.settings["show_time"] = False
    s.upload()
    s.download()
    print(s)
