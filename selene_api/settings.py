import json
from copy import deepcopy

from selene_api.api import DeviceApi


class RemoteSkillSettings:
    """ WARNING: selene backend does not use proper skill_id, if you have
    skills with same name but different author settings will overwrite each
    other on the backend, THIS CLASS IS NOT 100% SAFE in mycroft-core

    mycroft-core uses msm to generate weird metadata, removes author and munges github branch names into id
    ovos-core uses the proper deterministic skill_id and can be used safely

    you can define arbitrary strings as skill_id to use this as a datastore

    skill matching is currently done by checking "if {skill_id} in string"
    """

    def __init__(self, skill_id, settings=None, meta=None, url=None, version="v1"):
        self.api = DeviceApi(url, version)
        self.skill_id = skill_id
        self.identifier = skill_id
        self.settings = settings or {}
        self.meta = meta or {}
        self.local_path = ""  # TODO XDG

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

        WARNING: selene backend does not use proper skill_id, if you have
        skills with same name but different author settings will overwrite each
        other on the backend, THIS METHOD IS NOT 100% SAFE in mycroft-core

        mycroft-core uses msm to generate weird metadata, removes author and munges github branch names into id

        ovos-core uses the proper deterministic skill_id and can be used safely
        """
        data = self.api.get_skill_settings_v1()

        def match_settings(x, against):
            uuid = None
            for sets in x:
                fields = sets["identifier"].split("|")
                if len(fields) == 3:
                    uuid, skill_id, branch = fields
                elif len(fields) == 2:
                    if fields[0].startswith("@"):
                        uuid, skill_id = fields
                    else:
                        skill_id, branch = fields
                else:
                    skill_id = sets["identifier"]

                # setting belong to another device
                if uuid and uuid != self.api.uuid:
                    uuid = uuid.replace("@", "")
                    # TODO shared_settings flag
                    # continue

                if skill_id == against:
                    return self.deserialize(sets)

        # this is a mess, possible keys seen by logging data
        # - {skill_id}
        # - @|{skill_id}
        # - @{uuid}|{skill_id}
        # - {skill_id}|{branch}
        # - @|{skill_id}|{branch}
        # - @{uuid}|{skill_id}|{branch}
        # - {skill_id_no_author}
        # - @|{skill_id_no_author}
        # - @{uuid}|{skill_id_no_author}
        # - {skill_id_no_author}|{branch}
        # - @|{skill_id_no_author}|{branch}
        # - @{uuid}|{skill_id_no_author}|{branch}
        # - {whatever we feel like uploading}
        s = match_settings(data, self.skill_id) or \
            match_settings(data, self.selene_gid) or \
            match_settings(data, self.identifier) or \
            match_settings(data, self.skill_id.split(".")[0])

        if s:
            self.meta = s.meta
            self.settings = s.settings
            # update actual identifier from selene
            self.identifier = s.skill_id

    def upload(self):
        data = self.serialize()
        return self.api.put_skill_settings_v1(data)

    def load(self):
        # TODO load from file
        pass

    def store(self):
        # TODO save to file
        pass

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

        skill_id = data.get("skill_gid") or \
                   data.get("identifier")  # deprecated
        return RemoteSkillSettings(skill_id, skill_json, skill_meta,
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
