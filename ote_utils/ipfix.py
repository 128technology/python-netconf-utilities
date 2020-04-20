from builtins import str
import datetime
import pyshark
import re
import uuid

from pyshark.packet.fields import LayerField, LayerFieldsContainer


class IpfixException(Exception):
    pass


def collect_ipfix_capture(file="ipfix.pcap"):
    """Converts a pcap file to a FileCapture pyshark object

    Args:
        file - file to convert into a FileCapture object

    Returns:
        obj - FileCapture object from pyshark
    """
    return pyshark.FileCapture(file)


def get_packet_in(capture, packet_number):
    """Collect a specific packet from a capture object

    Args
        capture - Pyshark Capture object or list containing packets
        packet_number - Index of packet to

    Returns
        obj - Packet object for specified packet

    Raises
        IpfixException: Packet index out of range

    == Example ==
    Get Packet In     ${capture}     3
    """
    try:
        return capture[packet_number]
    except KeyError:
        raise IpfixException("There are only {} packets in this capture".format(len(capture)))


def get_ipfix_flowsets(capture):
    """Produces a list of all flowset packets captured within a capture object

    Args
        capture - pyshark FileCapture object

    Returns
        array - List of all packets that contain an ipfix flowset
    """
    flowset_capture = []
    for packet in capture:
        if hasattr(packet.cflow, "flowset_id"):
            flowset_capture.append(packet)

    return flowset_capture


def get_ipfix_templates(capture):
    """Produces a list of all flowset packets captured within a capture object

    Args ==
        capture - pyshark FileCapture object

    Returns ==
        List of all packets that contain an ipfix template
    """
    template_capture = []
    for packet in capture:
        if hasattr(packet.cflow, "template_id"):
            template_capture.append(packet)

    return template_capture


def get_capture_length(capture):
    """Returns the length (number of packets) within a capture

    Args
        capture - pyshark FileCapture object

    Returns
        Interger length / number of packets
    """
    return len([packet for packet in capture])


def get_flowset_id_for(packet):
    """Returns the flowset id of a cflow flowset packet

    Args
        packet - pyshark Packet object

    Returns
        str - Flowset ID value as a string

    Raises
        IpfixException: No flowset id was found for this packet
    """
    try:
        return packet.cflow.flowset_id
    except:
        raise IpfixException("No Flowset ID found")


def build_T128_ipfix_info(packet):
    """Builds a list of tuples containing fields and their info for a given ipfix flow packet

    Args ==
        packet - pyshark Packet object

    Returns ==
        Colapsed cflow fields as tuples in a list
    """
    if hasattr(packet.cflow, "template_id"):
        raise IpfixException("Template packet, Flowset Needed")

    sorted_field_list = _sort_fields(_get_all_field_lines(packet.cflow))

    ipfix_info = []
    for field in sorted_field_list:
        field_info = _get_field_info(field)
        if "String_len_short" not in field_info:
            ipfix_info.append(_get_field_info(field))
    return ipfix_info


def _sort_fields(fields_list):
    return sorted(fields_list, key=lambda x: x.pos, reverse=True)


def _get_enterprise_info(field):
    enterprise_type = re.findall("Type\s\d+", field.showname)[0]
    return _enterprise_type_map(enterprise_type, field)


def _get_field_info(field):
    try:
        if "Enterprise Private entry" in field.showname_key:
            key, value = _get_enterprise_info(field)
        else:
            key, value = field.showname_key, field.showname_value
    except:
        key, value = field.get_default_value(), "static"

    return {key: value}


def _get_all_field_lines(packet):
    return [field for field in _get_all_fields_with_alternates(packet)]


def _get_all_fields_with_alternates(packet):
    all_fields = list(packet._all_fields.values())
    all_fields += sum(
        [field.alternate_fields for field in all_fields if isinstance(field, LayerFieldsContainer)],
        [],
    )
    return all_fields


def _decode_field_ascii(data, encoding="hex"):
    return ("".join(data.split(":"))).decode(encoding)


def _decode_field_int(data):
    return int("".join(data.split(":")), 16)


def _decode_field_date(data):
    time = int("".join(data.split(":")), 16)
    return str(datetime.datetime.fromtimestamp(time))


def _decode_field_uuid(data):
    id_data = _decode_field_ascii(data)
    return str(uuid.UUID(bytes=id_data))


def _decode_field_ip(data):
    byte_list = data.split(":")
    byte_list = [int(x, 16) for x in byte_list]
    return ".".join(str(x) for x in byte_list)


def _enterprise_type_map(enterprise_type, field):
    field_map = {
        "Type 1": {"name": "RecordType", "decode": _decode_field_int},
        "Type 2": {"name": "IPv4AddressMask", "decode": _decode_field_ip},
        "Type 3": {"name": "Protocol", "decode": _decode_field_int},
        "Type 4": {"name": "TenantID", "decode": _decode_field_uuid},
        "Type 5": {"name": "RouteID", "decode": _decode_field_uuid},
        "Type 6": {"name": "SessionType", "decode": _decode_field_ascii},
        "Type 7": {"name": "StartTime", "decode": _decode_field_date},
        "Type 8": {"name": "EndTime", "decode": _decode_field_date},
        "Type 9": {"name": "CurrentByteCount", "decode": _decode_field_int},
        "Type 10": {"name": "CurrentPacketCount", "decode": _decode_field_int},
        "Type 11": {"name": "TcpRetransmissionCount", "decode": _decode_field_int},
        "Type 12": {"name": "ServiceName", "decode": _decode_field_ascii},
        "Type 13": {"name": "ServiceClass", "decode": _decode_field_ascii},
        "Type 14": {"name": "FlowID", "decode": _decode_field_uuid},
        "Type 15": {"name": "ServiceGroup", "decode": _decode_field_ascii},
        "Type 16": {"name": "Tenant", "decode": _decode_field_ascii},
    }
    name = field_map[enterprise_type]["name"]
    value = field_map[enterprise_type]["decode"](field.get_default_value())
    return name, value
