from ote_restlib.rest_client import RestClient
from ote_utils.ote_logger import OteLogger


logger = OteLogger(__name__)


class AlarmHandler(object):
    def __init__(self):
        """
        Initializes AlarmHandler object
        """
        self.baseline_alarms = []

    def get_all_alarms(self, rest_connections):
        """
        Retreives all alarms from rest connections

        == Args ==
            rest_connections - a list of rest connections to DUTs

        == Returns ==
            list (Alarm) - A list of all current Alarm objects
        """
        alarms = []
        for connection in rest_connections:
            response = self._make_alarm_request(connection)
            for alarm in response:
                alarms.append(Alarm(alarm))
        return alarms

    def _make_alarm_request(self, rest_conn):
        endpoint = "/api/v1/alarm"
        logger.debug("endpoint: {}".format(endpoint))
        response = rest_conn.make_request("get", endpoint, params={"shelvedStatus": "all"})
        logger.debug("Test no alarms response: {}".format(response))
        return response


class Alarm(object):
    def __init__(self, alarm):
        self.id = alarm.get("id")
        self.node = alarm.get("node")
        self.router = alarm.get("router")
        self.process = alarm.get("process")
        self.source = alarm.get("source")
        self.time = alarm.get("time")
        self.message = alarm.get("message")
        self.category = alarm.get("category")
        self.severity = alarm.get("severity")
        self.shelvedStatus = alarm.get("shelvedStatus")
        self.shelvedReason = alarm.get("shelvedReason")
        self.value = alarm.get("value")

    def __str__(self):
        ret = "alarm-id: {}\n".format(self.id)
        ret += "node: {}\n".format(self.node)
        ret += "router: {}\n".format(self.router)
        ret += "process: {}\n".format(self.process)
        ret += "source: {}\n".format(self.source)
        ret += "time: {}\n".format(self.time)
        ret += "message: {}\n".format(self.message)
        ret += "category: {}\n".format(self.category)
        ret += "severity: {}\n".format(self.severity)
        ret += "shelved-status: {}\n".format(self.shelvedStatus)
        ret += "shelved-reason: {}\n".format(self.shelvedReason)
        ret += "value: {}\n".format(self.value)
        return ret

    def __eq__(self, other):
        matching_items = set(self.items()) & set(other.items())
        return matching_items == set(other.items()) or matching_items == set(self.items())

    def items(self):
        return [(k, v) for k, v in self.__dict__.items() if v]

    def get(self, var):
        return self.__dict__[var]
