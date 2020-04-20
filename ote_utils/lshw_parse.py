from __future__ import absolute_import
from builtins import str
from builtins import range
from . import json_parse
import re


def get_pci_macs(dictionary):
    """
    Takes lshw dict and parses out the interfce pcis and macs
    Args:
        dictionary - lshw dict
    Return:
        dict of form {pci:mac} for all interfaces on host
    """
    return {pci: mac for pci, mac in _find_interface_macs(dictionary)}


def get_interface_pcis(dictionary):
    """
    Takes lshw dict and parses out the interfce pcis
    Args:
        dictionary - lshw dict
    Return:
        dict of form {intf:pci} for all interfaces on host
    """
    return {name: pci for pci, name in _find_interface_pcis(dictionary)}


def get_mgmt_interface_pcis(dictionary):
    """
    Takes lshw dict and parses out the mgmt interfce pcis
    Args:
        dictionary - lshw dict
    Return:
        dict of form {intf:pci} for all interfaces on host
    """
    return {name: pci for pci, name in _find_mgmt_interface_pcis(dictionary)}


def get_memory_dictionary(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        list of entire child dictionaries that contains key: class value: memory<#>
    """
    mem_list = []
    slots = get_mem_slot_count(dictionary)
    if slots == 1:
        mem_list.append(json_parse._get_dictionary_using_unique_pair(dictionary, "id", "memory"))
    else:
        for mem in range(slots):
            mem_list.append(
                json_parse._get_dictionary_using_unique_pair(dictionary, "id", "memory:" + str(mem))
            )

    return mem_list


def get_memory_size(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        size in bytes of the system's memory
    """
    size = 0
    for mem in get_memory_dictionary(dictionary):
        if "children" in mem:
            for bank in mem["children"]:
                if bank["product"] != "NO DIMM":
                    size += int(bank["size"])
    return size


def get_mem_bank_count(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        number of memory banks on the system
    """
    return len(get_memory_dictionary(dictionary))


def get_mem_slot_count(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        number of memory slots in system
    """
    slots = json_parse._get_dictionary_using_unique_pair(dictionary, "id", "memory")
    if slots != None:
        slot_num = 1
    else:
        slot_num = 0
        slots = json_parse._get_dictionary_using_unique_pair(
            dictionary, "id", "memory:" + str(slot_num)
        )
        while slots != None:
            slot_num += 1
            slots = json_parse._get_dictionary_using_unique_pair(
                dictionary, "id", "memory:" + str(slot_num)
            )
    return slot_num


def get_cpu_dictionary(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        dict containing the processor information
    """
    child_dict1 = dictionary["children"][0]
    for child in child_dict1["children"]:
        if child.get("class") == "processor":
            return child


def get_cpu_version(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        Cpu type of system
    """
    return get_cpu_dictionary(dictionary)["version"]


def get_cpu_count(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        number of cpu running of the host
    """
    cpu_count = 0
    child_dict1 = dictionary["children"][0]
    for child in child_dict1["children"]:
        if child.get("class") == "processor":
            cpu_count += 1
    return cpu_count


def get_network_interface_dictionary(dictionary, interface):
    """
    Args:
        dictionary - lshw dict
        interface - interface that you are looking fir
            ex.  0000:00:14.3
    Return:
        the interface child dictionary that contains the key: logicalname value: *interface*
    """
    return json_parse._get_dictionary_using_unique_pair(dictionary, "logicalname", interface)


def get_dpdk_nic(dictionary, pci):
    """
    Args:
        dictionary - lshw dict
        pci - pci of host system
            ex.
    Return:
        Nic linked to the system network with pci
    """
    return json_parse._get_dictionary_using_unique_pair(dictionary, "businfo", "pci@" + str(pci))[
        "product"
    ]


def get_dpdk_driver(dictionary, pci):
    """
    Args:
        dictionary - lshw dict
        interface - interface that you are looking fir
            ex.  0000:00:14.3
    Return:
        the interface driver for the network with pci
    """
    return json_parse._get_dictionary_using_unique_pair(dictionary, "businfo", "pci@" + str(pci))[
        "configuration"
    ]["driver"]


def get_LSHW_system_info(dictionary, *args):
    """
    Args:
        dictionary - lshw dict
        key - key in lshw dict you want the value or values of
    Return:
        all values of key *key* in entire lshw dict
    """
    system_params = args if (len(args) > 0) else ["id", "vendor", "version", "product"]
    return {param: get_system_info(dictionary, param) for param in system_params}


def get_system_info(dictionary, key):
    """
    Args:
        dictionary - lshw dict
    Return:
        System Id Ex: t1_dut1
    """
    try:
        return dictionary[key]
    except TypeError:
        return "{}: Not availible".format(key)


def get_system_core_count(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        Total number of cores in the system
    """
    cpu_dict = json_parse._get_dictionary_using_unique_pair(dictionary, "description", "CPU")
    return cpu_dict["configuration"]["cores"]


def get_lshw_info(dictionary, key):
    """
    Args:
        dictionary - lshw dict
    Return:
        System Id Ex: t1_dut1
    """
    try:
        return dictionary[key]
    except TypeError:
        return "{}: Not availible".format(key)


def get_cpu_info(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        A stripped down version of CPU info
    """
    cpu_count = get_cpu_count(dictionary)
    cpu_info = json_parse._get_dictionary_using_unique_pair(dictionary, "description", "CPU")
    cpu_info["cpu_count"] = cpu_count
    clear_fields = [
        "vendor",
        "id",
        "slot",
        "handle",
        "description",
        "businfo",
        "capabilities",
        "physid",
        "size",
    ]
    for field in clear_fields:
        cpu_info.pop(field, None)
    return cpu_info


def get_memory_info(dictionary):
    """
    Args:
        dictionary - lshw dict
    Return:
        General Memory info and bank info key that contains
        the information for each memory bank on the system
    """
    memory_info = get_memory_dictionary(dictionary)
    mem_bank_count = get_mem_bank_count(dictionary)
    memory_info["memory_bank_count"] = mem_bank_count

    bank_info = {}
    for bank in memory_info["children"]:
        bank_id = bank.pop("id")
        bank_info[bank_id] = bank

    memory_info.pop("children")
    memory_info["bank_info"] = bank_info
    return memory_info


def _find_interface_macs(dictionary):
    re_mac = re.compile(r"(?:[0-9a-fA-F]:?){12}")
    if all(i in dictionary for i in ["handle", "serial"]) and re_mac.match(dictionary["serial"]):
        yield [dictionary["handle"][4:], dictionary["serial"]]
    if isinstance(dictionary, dict):
        for k in dictionary:
            if isinstance(dictionary[k], list):
                for items in dictionary[k]:
                    for keys in _find_interface_macs(items):
                        yield keys


def _find_interface_pcis(dictionary):
    re_name = re.compile(r"dpdk\d+")
    if all(i in dictionary for i in ["handle", "logicalname"]) and re_name.match(
        str(dictionary["logicalname"])
    ):
        yield [dictionary["handle"][4:], dictionary["logicalname"]]
    if isinstance(dictionary, dict):
        for k in dictionary:
            if isinstance(dictionary[k], list):
                for items in dictionary[k]:
                    for keys in _find_interface_pcis(items):
                        yield keys


def _find_mgmt_interface_pcis(dictionary):
    re_name = re.compile(r"eth\d+")
    if all(i in dictionary for i in ["handle", "logicalname"]) and re_name.match(
        str(dictionary["logicalname"])
    ):
        yield [dictionary["handle"][4:], dictionary["logicalname"]]
    if isinstance(dictionary, dict):
        for k in dictionary:
            if isinstance(dictionary[k], list):
                for items in dictionary[k]:
                    for keys in _find_mgmt_interface_pcis(items):
                        yield keys
