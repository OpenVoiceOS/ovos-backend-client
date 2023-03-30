from ovos_config.config import Configuration

from ovos_backend_client.backends.base import BackendType
from ovos_backend_client.backends.offline import OfflineBackend
from ovos_backend_client.backends.personal import PersonalBackend

API_REGISTRY = {
    BackendType.OFFLINE: {
        "admin": True,  # updates mycroft.conf if used
        "database": True,  # manages local files only
        "device": True,  # manages local files only
        "skill_settings": True,  # manages local files only
        "dataset": True,  # manages local files only
        "metrics": True,  # manages local files only
        "wolfram": True,  # key needs to be set
        "geolocate": True,  # nominatim - no key needed
        "stt": True,  # uses OPM and reads from mycroft.conf
        "owm": True,  # key needs to be set
        "email": True,  # smtp config needs to be set
        "oauth": True  # oauth PHAL plugin to register apps
    },
    BackendType.PERSONAL: {
        "admin": True,
        "database": True,  # requires ovos-personal-backend>=0.2.0
        "device": True,
        "skill_settings": True,
        "dataset": True,
        "metrics": True,
        "wolfram": True,
        "geolocate": True,
        "stt": True,
        "owm": True,
        "email": True,
        "oauth": True  # can use personal-backend-manager to register apps
    }
}


def get_backend_type(conf=None):
    conf = conf or Configuration()
    if "server" in conf:
        conf = conf["server"]
    if conf.get("disabled"):
        return BackendType.OFFLINE
    if "backend_type" in conf:
        return conf["backend_type"]
    url = conf.get("url")
    if not url:
        return BackendType.OFFLINE
    return BackendType.PERSONAL


def get_backend_config(url=None, version="v1", identity_file=None, backend_type=None):
    config = Configuration()
    config_server = config.get("server") or {}
    if not url:
        url = config_server.get("url")
        version = config_server.get("version") or version
        backend_type = backend_type or get_backend_type(config)
    elif not backend_type:
        backend_type = get_backend_type({"url": url})

    if not url and backend_type:
        if backend_type == BackendType.PERSONAL:
            url = "http://0.0.0.0:6712"
        else:
            url = "http://127.0.0.1"

    return url, version, identity_file, backend_type
