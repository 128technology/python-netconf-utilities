from ote_restlib.rest_client import RestClient


class EventHandler(object):
    def __init__(self, dut, username, password, port=443):
        """Initializes EventHandler object
        == Args ==
            - dut (device dict) - DUT to handle events from
            - username (str) - Username for requests
            - password (str) - Password for requests
            - port (int, optional) - Port to requst events via REST
        """
        self.baseline_events = []
        self.host = dut["host"]["address"]
        self.username = username
        self.password = password
        self.port = port

    def update_baseline_events(self):
        """
        Sets the baseline events for this handler.

        == Args ==
         - self (event_handler) - reference to an EventHandler object

        == Return ==
        - baseline_events - The list of existing Event objects
        """
        self.baseline_events = self._make_event_request()
        return self.baseline_events

    def get_new_events(self):
        """
        Retrieves new events that have occured since the baseline was taken

        == Args ==
         - self

        == Return ==
        - new_events - The list of new Event objects
        """
        all_events = self._make_event_request()
        return list(set(all_events) - set(self.baseline_events))

    def _make_event_request(self):
        return self._make_event_rest_request(self.host, self.username, self.password, self.port)

    @classmethod
    def _make_event_rest_request(cls, host, username, password, port=443):
        rest_conn = RestClient()
        rest_conn.connect(host, username, password, port)
        endpoint = "/api/v1/audit"
        response = rest_conn.make_request("get", endpoint)
        return cls._get_events_in_response(response)

    @staticmethod
    def _get_events_in_response(response):
        return [Event(event_dict) for event_dict in response]


class Event(object):
    def __init__(self, event):
        self.event = event
        self.key = (
            event["type"],
            event["subtype"],
            event["timestamp"],
            event["router"],
            event["node"],
        )
        self.type = event["type"]
        self.subtype = event["subtype"]
        self.timestamp = event["timestamp"]
        self.router = event["router"]
        self.node = event["node"]
        self.data = event["data"]

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        return self.key == other.key

    def __str__(self):
        return str(self.event)

    __repr__ = __str__
