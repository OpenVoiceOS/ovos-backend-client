# Selene Api

Unofficial python api for interaction with https://api.mycroft.ai , also compatible with [ovos-local-backend](https://github.com/OpenVoiceOS/OVOS-local-backend)

Will only work if running in a device paired with mycroft, a valid identity2.json must exist

## STT

a companion stt plugin is available - [ovos-stt-plugin-selene](https://github.com/OpenVoiceOS/ovos-stt-plugin-selene)

## Geolocation

```python
from selene_api.api import GeolocationApi
geo = GeolocationApi()
data = geo.get_geolocation("Lisbon Portugal")
# {'city': 'Lisboa',
# 'country': 'Portugal', 
# 'latitude': 38.7077507, 
# 'longitude': -9.1365919, 
# 'timezone': 'Europe/Lisbon'}
```

## OpenWeatherMap Proxy

```python
from selene_api.api import OpenWeatherMapApi
owm = OpenWeatherMapApi()
data = owm.get_weather()
# dict - see api docs from owm onecall api
```


## Wolfram Alpha proxy

```python
from selene_api.api import WolframAlphaApi

wolf = WolframAlphaApi()
answer = wolf.spoken("what is the speed of light")
# The speed of light has a value of about 300 million meters per second

data = wolf.full_results("2+2")
# dict - see api docs from wolfram
```


## Remote Settings

To interact with skill settings on selene 

```python
from selene_api.settings import RemoteSkillSettings

# in ovos-core skill_id is deterministic and safe
s = RemoteSkillSettings("skill.author")
# in mycroft-core please ensure a valid remote_id
# in MycroftSkill class you can use
# remote_id = self.settings_meta.skill_gid
# s = RemoteSkillSettings("skill.author", remote_id="@|whatever_msm_decided")
s.download()

s.settings["existing_value"] = True
s.settings["new_value"] = "will NOT show up in UI"
s.upload()

# auto generate new settings meta for all new values before uploading
s.settings["new_value"] = "will show up in UI"
s.generate_meta()  # now "new_value" is in meta
s.upload()


```

## Selene Cloud

by hijacking skill settings we allows storing arbitrary data in selene and use it across devices and skills

```python
from selene_api.cloud import SeleneCloud

cloud = SeleneCloud()
cloud.add_entry("test", {"secret": "NOT ENCRYPTED MAN"})
data = cloud.get_entry("test")
```

an encrypted version is also supported if you dont trust selene!

```python
from selene_api.cloud import SecretSeleneCloud

k = "D8fmXEP5VqzVw2HE"   # you need this to read back the data
cloud = SecretSeleneCloud(k)
cloud.add_entry("test", {"secret": "secret data, selene cant read this"})
data = cloud.get_entry("test")
```

![](https://matrix-client.matrix.org/_matrix/media/r0/download/matrix.org/SrqxZnxzRNSqJaydKGRQCFKo)


## Admin Api (local backend only!)

since local backend does not provide a web ui a [admin api](https://github.com/OpenVoiceOS/OVOS-local-backend#admin-api) can be used to manage your devices

```python
from selene_api.api import AdminApi
admin = AdminApi("secret_admin_key")
uuid = "..."  # check identity2.json in the device you want to manage
# manually pair a device
identity_json = admin.pair(uuid)
# set device info
info = {"opt_in": True,
        "name": "my_device",
        "device_location": "kitchen",
        "email": "notifications@me.com",
        "isolated_skills": False,
        "lang": "en-us"}
admin.set_device_info(uuid, info)
# set device preferences
prefs = {"time_format": "full",
        "date_format": "DMY",
        "system_unit": "metric",
        "lang": "en-us"}
admin.set_device_prefs(uuid, prefs)
# set location data
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
admin.set_device_location(uuid, loc)
```

