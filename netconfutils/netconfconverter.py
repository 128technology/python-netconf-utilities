"""
Library for converting a running configuration to Netconf XML.
"""

from lxml import etree

from netconfutils import configmodel


class ConfigParseError(RuntimeError):

    "Exception class for errors while parsing configuration"


class NetconfConverter(object):

    """
    Converts a running configuration to Netconf XML.
    """
    operation_elem_name = etree.QName(
        'urn:ietf:params:xml:ns:netconf:base:1.0',
        'operation')

    def __init__(self):
        """
        Initialize NetconfConverter.  Setting write_object_keys_as_parameters to
        True will cause any keys specified with the objects to also be written
        to the Netconf XML as leaf parameters.
        """
        self.write_object_keys_as_parameters = False

    def load_config_model(self, file_pattern, config_prefix='', config_elem_name='config'):
        """
        Parses the specified Netconf yin definition files.  The parameter
        file_pattern should be set to a glob pattern of all of the yin
        files.  I.e. model/*.yin
        """
        self.model = configmodel.ConfigModel(config_prefix, config_elem_name)
        self.model.parse(file_pattern)

    def convert_config_to_netconf_xml(self, config_string_or_list, tag):
        """
        Converts a running configuration to Netconf XML. If specified as a
        string, each line of the string should contain a single config command.
        If specified as a list, it should contain one config line per item. The
        first line of either format must be 'config' with a matching 'exit' at
        the end.  Each object specified should be terminated with an 'exit'.
        """
        if isinstance(config_string_or_list, basestring):
            config_list = self._convert_config_string_to_list(config_string_or_list)
        else:
            config_list = config_string_or_list

        return self._convert_config_list_to_netconf_xml(config_list, tag)

    def _convert_config_list_to_netconf_xml(self, config_list, tag):

        builder = etree.TreeBuilder()
        config_elem_name = etree.QName(
            'urn:ietf:params:xml:ns:netconf:base:1.0',
            tag)
        builder.start(config_elem_name, {})
        builder.data('\n')

        current_xml_token_stack = []
        config_line = '(start)'

        try:
            for line_number, config_line in enumerate(config_list, start=1):
                if not self._is_line_empty_or_comment(config_line):
                    self._process_config_line(builder, current_xml_token_stack,
                                              config_line)
            builder.end(config_elem_name)
            builder.data('\n')
            root = builder.close()
        except Exception as e:
            raise ConfigParseError('Error parsing config, line ' +
                                   str(line_number) + ': "' + config_line +
                                   '" : ' + str(e))
        return root

    def _convert_config_string_to_list(self, config_str):
        lines = config_str.split('\n')
        return [line.strip() for line in lines]

    def _is_line_empty_or_comment(self, config_line):
        return (len(config_line) is 0) or (config_line[0] == '#')

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

        if tokens[0] == 'exit':
            self._process_exit_token(builder, stack)
        elif tokens[0] == 'delete':
            del tokens[0]
            self._process_config_tokens(builder, stack, tokens, 'delete')
        elif tokens[0] == 'create':
            del tokens[0]
            self._process_config_tokens(builder, stack, tokens, 'create')
        else:
            self._process_config_tokens(builder, stack, tokens)

    def _process_exit_token(self, builder, stack):
        token = stack[-1]
        element_name = self._get_element_name(stack, token)
        stack.pop()
        self._add_indent(builder, stack)
        builder.end(element_name)
        builder.data('\n')

    def _process_config_tokens(self, builder, stack, tokens, operation=None):
        first_token = tokens[0]
        prefix_nsmap = self._get_nsmap(stack, first_token)
        if self._is_path_container(stack, first_token):
            self._add_indent(builder, stack)
            stack.append(first_token)
            element_name = self._get_element_name(stack, first_token)
            elem = builder.start(element_name, {}, prefix_nsmap)
            if operation == 'delete':
                elem.set(NetconfConverter.operation_elem_name, 'delete')
            elif operation == 'create':
                elem.set(NetconfConverter.operation_elem_name, 'create')
            builder.data('\n')
            if self.write_object_keys_as_parameters:
                self._add_key_elements(builder, stack, tokens)
        else:
            self._add_indent(builder, stack)
            element_name = self._get_element_name(stack, first_token)
            elem = builder.start(element_name, {}, prefix_nsmap)
            if operation == 'delete':
                elem.set(NetconfConverter.operation_elem_name, 'delete')
            elif operation == 'create':
                elem.set(NetconfConverter.operation_elem_name, 'create')
            if self._is_path_identity_type(stack, first_token):
                current_prefix = self._check_prefix(stack, tokens)
                tokens[1] = current_prefix + ':' + tokens[1]
            builder.data(' '.join(tokens[1:]))
            builder.end(element_name)
            builder.data('\n')

    def _check_prefix(self, stack, tokens):
        stack_copy = list(stack)
        stack_copy.append(tokens[0])
        xpath = self._convert_stack_to_xpath(stack_copy)
        key = self.model.identity_map[xpath]
        current_prefix = key[tokens[1]]

        return current_prefix

    def _get_nsmap(self, stack, token):
        stack_copy = list(stack)
        stack_copy.append(token)
        xpath = self._convert_stack_to_xpath(stack_copy)
        try:
            prefix, namespace = self.model.namespace_map[xpath]
            nsmap = {prefix: namespace}
        except KeyError:
            nsmap = {}
        return nsmap

    def _is_path_container(self, stack, token):
        stack_copy = list(stack)
        stack_copy.append(token)
        xpath = self._convert_stack_to_xpath(stack_copy)

        return xpath in self.model.container_map

    def _is_path_identity_type(self, stack, token):
        stack_copy = list(stack)
        stack_copy.append(token)
        xpath = self._convert_stack_to_xpath(stack_copy)

        return xpath in self.model.identity_map

    def _is_path_augmented_type(self, stack, token):
        stack_copy = list(stack)
        stack_copy.append(token)
        xpath = self._convert_stack_to_xpath(stack_copy)

        return xpath in self.model.namespace_map

    def _convert_stack_to_xpath(self, stack):
        return '/'.join(stack)

    def _add_indent(self, builder, stack):
        indent = len(stack) * '    '
        builder.data(indent)

    def _get_element_name(self, stack, token):
        stack_copy = list(stack)

        if self._is_path_augmented_type(stack_copy, token):
            stack_copy.append(token)

        xpath = self._convert_stack_to_xpath(stack_copy)
        while xpath not in self.model.namespace_map and len(stack_copy) > 0:
            stack_copy.pop()
            xpath = self._convert_stack_to_xpath(stack_copy)

        if xpath in self.model.namespace_map:
            tag_data = self.model.namespace_map[xpath]
            return etree.QName(tag_data[1], token)
        else:
            return token

    def _add_key_elements(self, builder, stack, tokens):
        xpath = self._convert_stack_to_xpath(stack)
        if xpath in self.model.container_map:
            keys = self.model.container_map[xpath]
            if len(keys) != (len(tokens) - 1):
                raise ConfigParseError(
                    ('Invalid keys specified for {}, ' +
                     'valid keys: {} tokens: {}').format(
                        xpath, str(keys), str(tokens[1:])))
            for token_index, key in enumerate(keys, start=1):
                if self._is_path_identity_type(stack, key):
                    identity_tokens = [key, tokens[token_index]]
                    current_prefix = self._check_prefix(stack, identity_tokens)
                    tokens[token_index] = current_prefix + \
                        ':' + tokens[token_index]
                self._add_indent(builder, stack)
                element_name = self._get_element_name(stack, key)
                builder.start(element_name, {})
                builder.data(tokens[token_index])
                builder.end(element_name)
                builder.data('\n')
