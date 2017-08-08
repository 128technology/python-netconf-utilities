"""
Library for handling Netconf RPC or state requests and responses
"""

from lxml import etree
import exemel


def create_netconf_rpc_request(command, namespace, **args):
    """
    Creates a Netconf RPC request.  Command specifies the tag name of the
    command to be issued and namspace specifies the namespace.  Additional
    arguments can be specified optionally by args.
    """

    args_dict = {'#ns': namespace}
    args_dict.update(args)
    command_ele = etree.fromstring(exemel.build(args_dict, root=command))

    return command_ele


def parse_xml_to_dict(result_xml_str):
    """
    Parses XML results from Netconf into a python dictionary.  Dictionary
    entries will have keys of the element names and values of the XML text
    nodes.  When multiple of the same element is present, values will be
    appended together as a list.
    """
    result_xml = etree.fromstring(result_xml_str)
    return _parse_xml_to_dict_recurse(result_xml)


def create_netconf_filter(filter_tag_list):
    """
    Creates a filter appropriate for a Netconf get subtree request.  The
    filter_tag_list provides the subtree filter for the get state request.
    Each entry should be an element tag in {namespace}tag format.
    """
    first_ele = None
    last_ele = None
    for tag_name in filter_tag_list:
        if last_ele is None:
            last_ele = etree.Element(tag_name)
            first_ele = last_ele
        else:
            last_ele = etree.SubElement(last_ele, tag_name)

    return first_ele


def _parse_xml_to_dict_recurse(sub_xml):
    result = {}
    if etree.iselement(sub_xml):
        if len(sub_xml) > 0:
            for item in sub_xml:
                tag = etree.QName(item.tag).localname
                if tag in result:
                    result[tag].append(_parse_xml_to_dict_recurse(item))
                else:
                    result[tag] = [_parse_xml_to_dict_recurse(item)]
        else:
            result = sub_xml.text
    else:
        result = sub_xml
    return result
