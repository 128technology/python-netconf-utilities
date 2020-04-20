"""
Library for converting a running configuration to Netconf XML.
"""

from builtins import str
from past.builtins import basestring
from builtins import object
from lxml import etree

import yinsolidated


class ConfigParseError(RuntimeError):

    "Exception class for errors while parsing configuration"


class NetconfConverter(object):

    """
    Converts a running configuration to Netconf XML.
    """

    YIN_NAMESPACE = "urn:ietf:params:xml:ns:yang:yin:1"
    IDENTITY_TAG = str(etree.QName(YIN_NAMESPACE, "identity"))
    IDENTITY_MAP = {}
    operation_elem_name = etree.QName("urn:ietf:params:xml:ns:netconf:base:1.0", "operation")

    def load_config_model(self, config_model_file):
        """
        Parses the specified Netconf xml Consolidated Config Model file

        Args:
            config_model_file (str): Consolidated model Config xml file
        """
        self.model = yinsolidated.parse(config_model_file)
        self._find_identities()

    def load_user_model(self, user_model_file):
        """
        Parses the specified Netconf xml Consolidated User Model file

        Args:
            config_model_file (str): Consolidated model User xml file
        """
        self.model = yinsolidated.parse(user_model_file)

    def convert_config_to_netconf_xml(self, config_string_or_list, tag, attributes={}):
        """
        Converts a running configuration to Netconf XML. If specified as a
        string, each line of the string should contain a single config command.
        If specified as a list, it should contain one config line per item. The
        first line of either format must be 'config' with a matching 'exit' at
        the end.  Each object specified should be terminated with an 'exit'.

        Args:
            config_string_or_list (str/array): Config to convert to xml based on model
            tag (str): custom tag to add to xml block
            attributes (str): custom attr of starting tags in built netconf
        """
        if isinstance(config_string_or_list, basestring):
            config_list = self._convert_config_string_to_list(config_string_or_list)
        else:
            config_list = config_string_or_list

        return self._convert_config_list_to_netconf_xml(config_list, tag, attributes)

    def _convert_config_list_to_netconf_xml(self, config_list, tag, attributes):

        builder = etree.TreeBuilder()
        config_elem_name = etree.QName("urn:ietf:params:xml:ns:netconf:base:1.0", tag)
        builder.start(config_elem_name, attributes)
        builder.data("\n")

        current_xml_token_stack = []
        config_line = "(start)"

        try:
            for line_number, config_line in enumerate(config_list, start=1):
                if not self._is_line_empty_or_comment(config_line):
                    self._process_config_line(builder, current_xml_token_stack, config_line)
            builder.end(config_elem_name)
            builder.data("\n")
            root = builder.close()
        except Exception as e:
            raise ConfigParseError("Error parsing config " + str(e))
        return root

    def _process_config_line(self, builder, stack, config_line):
        tokens = config_line.split()

        start_token = 0
        end_token = 0
        if len(tokens) > 1:
            start_token = 1
            end_token = len(tokens) - 1

        if tokens[start_token].startswith('"') and tokens[end_token].endswith('"'):
            tokens[start_token] = tokens[start_token][1:]
            tokens[end_token] = tokens[end_token][:-1]

        if tokens[0] == "exit":
            self._process_exit_token(builder, stack)
        elif tokens[0] == "delete":
            del tokens[0]
            self._process_config_tokens(builder, stack, tokens, "delete")
        elif tokens[0] == "create":
            del tokens[0]
            self._process_config_tokens(builder, stack, tokens, "create")
        else:
            self._process_config_tokens(builder, stack, tokens)

    def _process_config_tokens(self, builder, stack, tokens, operation=None):
        first_token = tokens[0]
        ns, prefix, yang_keyword = self._find_model_node(stack, first_token)
        element_name = etree.QName(ns, first_token)

        self._add_indent(builder, stack)
        elem = builder.start(element_name, {}, {prefix: ns})

        if operation == "delete":
            elem.set(NetconfConverter.operation_elem_name, "delete")
        elif operation == "create":
            elem.set(NetconfConverter.operation_elem_name, "create")

        if yang_keyword in ["leaf", "leaf-list", "case"]:
            if len(tokens) > 1:
                if self._is_identity_type(tokens[1], ns):
                    tokens[1] = prefix + ":" + tokens[1]
                builder.data(" ".join(tokens[1:]))
            builder.end(element_name)
            builder.data("\n")
        else:
            stack.append(first_token)
            builder.data("\n")

    def _find_model_node(self, stack, token):
        stack_copy = list(stack)
        if token is not None:
            stack_copy.append(token)
        tree = self.model.getroot()

        for name in stack_copy:
            tree = self.find_child(tree, name)

        if tree is None:
            raise Exception("Token {} does not exist in the data model".format(token))

        return tree.namespace, tree.prefix, etree.QName(tree.tag).localname

    def find_child(self, tree, name):
        node = tree.find("*/[@name='{}']".format(name))
        if node is None:
            for child in tree:
                if etree.QName(child.tag).localname in ["choice", "case"]:
                    node = self.find_child(child, name)
                    if node is not None:
                        return node
        return node

    def _process_exit_token(self, builder, stack):
        token = stack[-1]
        ns, _, _ = self._find_model_node(stack, None)
        element_name = etree.QName(ns, token)
        stack.pop()
        self._add_indent(builder, stack)
        builder.end(element_name)
        builder.data("\n")

    def _convert_config_string_to_list(self, config_str):
        lines = config_str.splitlines()
        return [line.strip() for line in lines]

    def _is_line_empty_or_comment(self, config_line):
        return (len(config_line) == 0) or (config_line[0] == "#")

    def _add_indent(self, builder, stack):
        indent = len(stack) * "    "
        builder.data(indent)

    def _find_identities(self):
        identities = self.model.findall("/" + self.IDENTITY_TAG)
        for child in identities:
            self.IDENTITY_MAP[child.name] = {"prefix": child.prefix, "namespace": child.namespace}

    def _is_identity_type(self, token, namespace):
        is_identity = False
        try:
            if self.IDENTITY_MAP[token]["namespace"] == namespace:
                is_identity = True
        except KeyError:
            pass
        return is_identity
