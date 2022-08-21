import json
import os
import time
from os.path import isfile, expanduser

from combo_lock import ComboLock
from ovos_utils.log import LOG

identity_lock = ComboLock('/tmp/identity-lock')


def find_identity():
    locations = [
        "~/.mycroft/identity/identity2.json",  # old location
        "~/.config/mycroft/identity/identity2.json",  # xdg location
        "~/mycroft-config/identity/identity2.json",  # smartgic docker default loc
    ]
    for loc in locations:
        loc = expanduser(loc)
        if isfile(loc):
            return loc
    return None


def load_identity():
    locations = [
        "~/.mycroft/identity/identity2.json",  # old location
        "~/.config/mycroft/identity/identity2.json",  # xdg location
        "~/mycroft-config/identity/identity2.json",  # smartgic docker default loc
    ]
    for loc in locations:
        loc = expanduser(loc)
        if isfile(loc):
            LOG.debug(f"identity found: {loc}")
            try:
                with open(loc) as f:
                    return json.load(f)
            except:
                LOG.error("invalid identity file!")
                continue
    return {}


class DeviceIdentity:
    def __init__(self, **kwargs):
        self.uuid = kwargs.get("uuid", "")
        self.access = kwargs.get("access", "")
        self.refresh = kwargs.get("refresh", "")
        self.expires_at = kwargs.get("expires_at", 0)

    def is_expired(self):
        return self.refresh and 0 < self.expires_at <= time.time()

    def has_refresh(self):
        return self.refresh != ""


class IdentityManager:
    __identity = None

    @staticmethod
    def _load():
        LOG.debug('Loading identity')
        try:
            identity_file = find_identity()
            if identity_file:
                with open(identity_file, 'r') as f:
                    IdentityManager.__identity = DeviceIdentity(**json.load(f))
            else:
                IdentityManager.__identity = DeviceIdentity()
        except Exception as e:
            LOG.exception(f'Failed to load identity file: {repr(e)}')
            IdentityManager.__identity = DeviceIdentity()

    @staticmethod
    def load(lock=True):
        try:
            if lock:
                identity_lock.acquire()
                IdentityManager._load()
        finally:
            if lock:
                identity_lock.release()
        return IdentityManager.__identity

    @staticmethod
    def save(login=None, lock=True):
        LOG.debug('Saving identity')
        if lock:
            identity_lock.acquire()
        try:
            if login:
                IdentityManager._update(login)
            identity_file = find_identity()
            with open(identity_file, 'w') as f:
                json.dump(IdentityManager.__identity.__dict__, f)
                f.flush()
                os.fsync(f.fileno())
        finally:
            if lock:
                identity_lock.release()

    @staticmethod
    def _update(login=None):
        LOG.debug('Updaing identity')
        login = login or {}
        expiration = login.get("expiration", 0)
        IdentityManager.__identity.uuid = login.get("uuid", "")
        IdentityManager.__identity.access = login.get("accessToken", "")
        IdentityManager.__identity.refresh = login.get("refreshToken", "")
        IdentityManager.__identity.expires_at = time.time() + expiration

    @staticmethod
    def update(login=None, lock=True):
        if lock:
            identity_lock.acquire()
        try:
            IdentityManager._update()
        finally:
            if lock:
                identity_lock.release()

    @staticmethod
    def get():
        if not IdentityManager.__identity:
            IdentityManager.load()
        return IdentityManager.__identity
