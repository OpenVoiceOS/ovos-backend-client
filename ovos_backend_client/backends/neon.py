from ovos_backend_client.backends.offline import AbstractPartialBackend, BackendType

try:
    from neon_utils.mq_utils import send_mq_request as send_neon_mq
except ImportError:
    send_neon_mq = None

NEON_API_URL = "https://api.neon.ai"


class NeonMQBackend(AbstractPartialBackend):
    def __init__(self, url=NEON_API_URL, version="v1", identity_file=None, credentials=None):
        if send_neon_mq is None:
            raise ImportError("neon_utils not installed!")
        super().__init__(url, version, identity_file, BackendType.NEON_MQ, credentials)

    @staticmethod
    def _request_mq_api(neon_api: str,
                        query_params: dict,
                        timeout: int = 30) -> dict:
        """
        Handle a request for information from the Neon API Proxy Server
        @param query_params: Data parameters to pass to remote API
        @param timeout: Request timeout in seconds
        @return: dict response from API with: `status_code`, `content`, and `encoding`
        """

        if not query_params:
            raise ValueError("Got empty query params")
        if not isinstance(query_params, dict):
            raise TypeError(f"Expected dict, got: {query_params}")
        query_params["service"] = neon_api
        response = send_neon_mq("/neon_api", query_params, "neon_api_input", "neon_api_output", timeout)
        return response or {"status_code": 401,
                            "content": f"Neon API failed to give a response within {timeout} seconds",
                            "encoding": None}

    # OWM Api
    def owm_get_weather(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to configured location
        lat, lon = lat_lon or self._get_lat_lon()
        return self._request_mq_api(
            "open_weather_map",
            {
                "units": units,
                "lat": lat,
                "lng": lon,
                "lang": lang,
                "api": "onecall"
            })

    def owm_get_current(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to configured location
        lat, lon = lat_lon or self._get_lat_lon()
        return self._request_mq_api(
            "open_weather_map",
            {
                "units": units,
                "lat": lat,
                "lng": lon,
                "lang": lang,
                "api": "weather"
            })

    def owm_get_hourly(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        raise NotImplementedError()

    def owm_get_daily(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        raise NotImplementedError()

    # Wolfram Alpha API
    def wolfram_spoken(self, query, units="metric", lat_lon=None, optional_params=None):
        optional_params = optional_params or {}
        if not lat_lon:
            lat_lon = self._get_lat_lon(**optional_params)
        lat, lon = lat_lon
        return self._request_mq_api(
            "wolfram_alpha",
            {
                "units": units,
                "lat": lat,
                "lon": lon,
                "query": query,
                "api": "spoken"
            })

    def wolfram_simple(self, query, units="metric", lat_lon=None, optional_params=None):
        optional_params = optional_params or {}
        if not lat_lon:
            lat_lon = self._get_lat_lon(**optional_params)
        lat, lon = lat_lon
        return self._request_mq_api(
            "wolfram_alpha",
            {
                "units": units,
                "lat": lat,
                "lon": lon,
                "query": query,
                "api": "simple"
            })

    def wolfram_full_results(self, query, units="metric", lat_lon=None, optional_params=None):
        """Wrapper for the WolframAlpha Full Results v2 API.
        https://products.wolframalpha.com/api/documentation/
        Pods of interest
        - Input interpretation - Wolfram's determination of what is being asked about.
        - Name - primary name of
        """
        optional_params = optional_params or {}
        if not lat_lon:
            lat_lon = self._get_lat_lon(**optional_params)
        lat, lon = lat_lon
        return self._request_mq_api(
            "wolfram_alpha",
            {
                "units": units,
                "lat": lat,
                "lon": lon,
                "query": query,
                "api": "full"
            })

    # Geolocation Api
    def geolocation_get(self, location):
        """Call the geolocation endpoint.

        Args:
            location (str): the location to lookup (e.g. Kansas City Missouri)

        Returns:
            str: JSON structure with lookup results
        """
        raise NotImplementedError()  # TODO

    # Metrics API
    def metrics_upload(self, name, data):
        """ upload metrics"""
        raise NotImplementedError()  # TODO

    # Email API
    def email_send(self, title, body, sender):
        mail_config = self.credentials["email"]
        smtp_username = mail_config.get("smtp", {}).get("username")
        recipient = mail_config.get("recipient") or smtp_username

        request_data = {"recipient": recipient,
                        "subject": title,
                        "body": body,
                        "attachments": {}}
        # TODO - use self._request_mq_api()
        data = send_neon_mq("/neon_emails", request_data,
                            "neon_emails_input")
        return data.get("success")

    # STT Api
    def stt_get(self, audio, language="en-us", limit=1):
        """ Web API wrapper for performing Speech to Text (STT)

        Args:
            audio (bytes): The recorded audio, as in a FLAC file
            language (str): A BCP-47 language code, e.g. "en-US"
            limit (int): Maximum minutes to transcribe(?)

       """
        # if flac not supported
        #
        #     @staticmethod
        #     def _get_wav_data(audio):
        #         with NamedTemporaryFile() as fp:
        #             fp.write(audio)
        #             with AudioFile(fp.name) as source:
        #                 audio = Recognizer().record(source)
        #         return audio.get_wav_data()
        #
        #     content_type = "audio/wav"
        #     audio = _get_wav_data(audio)
        raise NotImplementedError()  # TODO

