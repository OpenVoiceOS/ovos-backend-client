from ovos_utils.log import LOG
from ovos_utils.network_utils import is_connected
from selene_api.exceptions import BackendDown, InternetDown, HTTPError
from selene_api.identity import IdentityManager
from selene_api.api import DeviceApi

_paired_cache = False


def has_been_paired():
    """ Determine if this device has ever been paired with a web backend

    Returns:
        bool: True if ever paired with backend (not factory reset)
    """
    # This forces a load from the identity file in case the pairing state
    # has recently changed
    id = IdentityManager.load()
    return id.uuid is not None and id.uuid != ""


def is_paired(ignore_errors=True):
    """Determine if this device is actively paired with a web backend

    Determines if the installation of Mycroft has been paired by the user
    with the backend system, and if that pairing is still active.

    Returns:
        bool: True if paired with backend
    """
    global _paired_cache
    if _paired_cache:
        # NOTE: This assumes once paired, the unit remains paired.  So
        # un-pairing must restart the system (or clear this value).
        # The Mark 1 does perform a restart on RESET.
        return True
    api = DeviceApi()
    _paired_cache = api.identity.uuid and check_remote_pairing(ignore_errors)

    return _paired_cache


def check_remote_pairing(ignore_errors):
    """Check that a basic backend endpoint accepts our pairing.

    Args:
        ignore_errors (bool): True if errors should be ignored when

    Returns:
        True if pairing checks out, otherwise False.
    """
    try:
        DeviceApi().get()
        return True
    except HTTPError as e:
        if e.response.status_code == 401:
            return False
        error = e
    except Exception as e:
        error = e

    LOG.warning('Could not get device info: {}'.format(repr(error)))

    if ignore_errors:
        return False

    if isinstance(error, HTTPError):
        if is_connected():
            raise BackendDown from error
        else:
            raise InternetDown from error
    else:
        raise error

