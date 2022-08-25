from requests import RequestException


class BackendDown(RequestException):
    pass


class InternetDown(RequestException):
    pass
