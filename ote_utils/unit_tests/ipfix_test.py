from builtins import object
import os
import mock
import pyshark
import pytest

from ote_utils import ipfix


class FakeCapture(object):
    def __init__(self, param=None, value=None):
        if param is not None:
            self.cflow = type(
                "FakePacket", (object,), {param: value, "_all_fields": {"a": fake_field()}}
            )


class fake_field(object):
    def __init__(self):
        self.pos = 0
        self.showname_key = "Enterprise Private entry"
        self.showname = "Type 1"

    def get_default_value(self):
        return "0000:0000:FF3F:0030"


@mock.patch("ote_utils.ipfix.pyshark.FileCapture")
def test_ipfix_capture(mock_pyshark):
    path = get_resource_path("ipfix.pcap")
    ipfix.collect_ipfix_capture(path)
    mock_pyshark.assert_called_once_with(path)


def test_get_packet():
    packet = ipfix.get_packet_in({"1": 1, "2": 2, "3": 3, "4": 4}, "1")
    assert packet == 1
    with pytest.raises(ipfix.IpfixException):
        ipfix.get_packet_in({"1": 1, "2": 2, "3": 3, "4": 4}, "52")


@pytest.mark.parametrize(
    "function,expected_value",
    [(ipfix.get_ipfix_flowsets, "flowset_id"), (ipfix.get_ipfix_templates, "template_id")],
)
def test_packet_attr_collection(function, expected_value):
    fake_flowset = [
        FakeCapture(expected_value),
        FakeCapture(expected_value),
        FakeCapture("Chase"),
        FakeCapture("Bob"),
        FakeCapture("Chase"),
        FakeCapture(expected_value),
        FakeCapture(expected_value),
    ]

    flowset_packets = function(fake_flowset)
    assert len(flowset_packets) == 4
    assert hasattr(flowset_packets[0].cflow, expected_value)


def test_capture_length():
    assert ipfix.get_capture_length([1, 2, 3, 4]) == 4
    assert ipfix.get_capture_length([]) == 0
    assert ipfix.get_capture_length({1: 2, 2: 3, 3: 4, 4: 5}) == 4


def test_get_flowset_id():
    capture = {
        0: FakeCapture("flowset_id", "2"),
        1: FakeCapture("flowset_id", "257"),
        2: FakeCapture("Chase"),
    }
    packet = ipfix.get_packet_in(capture, 0)
    assert packet.cflow.flowset_id == "2"
    packet = ipfix.get_packet_in(capture, 1)
    assert packet.cflow.flowset_id == "257"


def test_T128_ipfix_info():
    packet = FakeCapture("flowset_id", "2")
    packet_info = ipfix.build_T128_ipfix_info(packet)
    assert packet_info == [{"RecordType": 4282318896}]

    packet = FakeCapture("template_id", "2")
    with pytest.raises(ipfix.IpfixException):
        ipfix.build_T128_ipfix_info(packet)


def get_resource_path(resource_filename):
    return os.path.join(os.path.dirname(__file__), "resources", resource_filename)
