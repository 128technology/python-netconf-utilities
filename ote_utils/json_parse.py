import json


def create_dict_from_json(input_file):
    """
    Opens a .jsom file and converts it into a
    python dict
    """
    with open(input_file) as json_file:
        json_dict = json.load(json_file)
    return json_dict


def get_key_values(dictionary, key):
    """
    Args:
        dictionary - dict
        key - key in dict on branch
    Return:
        all values of key *key* in entire dict
    """
    return [value for value in _key_value_generator(dictionary, key)]


def _get_dictionary_using_unique_pair(dictionary, search_key, search_value, leaf=None):
    for key in dictionary:
        if key == search_key and dictionary[key] == search_value:
            leaf = dictionary
        if isinstance(dictionary[key], dict):
            leaf = _get_dictionary_using_unique_pair(
                dictionary[key], search_key, search_value, leaf
            )
        elif isinstance(dictionary[key], list):
            for item in dictionary[key]:
                if isinstance(item, dict):
                    leaf = _get_dictionary_using_unique_pair(item, search_key, search_value, leaf)
    return leaf


def _key_value_generator(dictionary, key):
    if key in dictionary:
        yield dictionary[key]
    if isinstance(dictionary, dict):
        for k in dictionary:
            if isinstance(dictionary[k], list):
                for items in dictionary[k]:
                    for keys in _key_value_generator(items, key):
                        yield keys
