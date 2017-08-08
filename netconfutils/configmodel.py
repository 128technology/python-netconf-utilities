"""
Library for reading Netconf yin definition files into a form usable by the
config to Netconf XML converter.
"""

import glob

from copy import deepcopy

from lxml import etree


class ConfigModelParseError(RuntimeError):

    "Exception class for errors while parsing the configuration model"


class ConfigModel(object):

    """
    Library for reading Netconf yin definition files into a form usable by the
    config to Netconf XML converter.
    """

    YIN_NAMESPACE = 'urn:ietf:params:xml:ns:yang:yin:1'
    CONFIG_MODEL_NAMESPACE = 'configmodel'
    NAMESPACE_TAG = str(etree.QName(YIN_NAMESPACE, 'namespace'))
    PREFIX_TAG = str(etree.QName(YIN_NAMESPACE, 'prefix'))
    GROUPING_TAG = str(etree.QName(YIN_NAMESPACE, 'grouping'))
    USES_TAG = str(etree.QName(YIN_NAMESPACE, 'uses'))
    IDENTITY_TAG = str(etree.QName(YIN_NAMESPACE, 'identity'))
    AUGMENT_TAG = str(etree.QName(YIN_NAMESPACE, 'augment'))
    CHOICE_TAG = str(etree.QName(YIN_NAMESPACE, 'choice'))
    CASE_TAG = str(etree.QName(YIN_NAMESPACE, 'case'))
    CONTAINER_TAG = str(etree.QName(YIN_NAMESPACE, 'container'))
    LIST_TAG = str(etree.QName(YIN_NAMESPACE, 'list'))
    KEY_TAG = str(etree.QName(YIN_NAMESPACE, 'key'))
    LEAF_TAG = str(etree.QName(YIN_NAMESPACE, 'leaf'))
    LEAF_LIST_TAG = str(etree.QName(YIN_NAMESPACE, 'leaf-list'))
    TYPE_TAG = str(etree.QName(YIN_NAMESPACE, 'type'))
    BASE_TAG = str(etree.QName(YIN_NAMESPACE, 'base'))
    PREFIX_ATTR = str(etree.QName(CONFIG_MODEL_NAMESPACE, 'prefix'))
    NS_ATTR = str(etree.QName(CONFIG_MODEL_NAMESPACE, 'ns'))
    _NSMAP = {'yin': YIN_NAMESPACE}

    def __init__(self, config_prefix='', config_elem_name='config'):
        self.namespace_map = {}
        self.container_map = {}
        self.identity_map = {}

        self._config_elem_name = config_elem_name
        self._xml_chunks = {}
        self._identity_elems = []
        self._config_root = None
        self._config_prefix = config_prefix
        self._config_ns = ''
        self._identity_prefix_map = {}
        self._identity_path_map = {}

    def parse(self, file_pattern):
        """
        Parses the specified Netconf yin definition files.  The parameter
        file_pattern should be set to a glob pattern of all of the yin
        files.  I.e. model/*.yin
        """
        for filename in sorted(glob.glob(file_pattern), reverse=True):
            self._parse_xml_file(filename)
        self._combine_xml_chunks(self._config_root,
                                 '/' + self._config_prefix + ':' +
                                 self._config_elem_name,
                                 self._config_prefix)
        self._parse_combined_xml(self._config_root, self._config_prefix)

    def _parse_xml_file(self, filename):
        model = etree.parse(filename)
        self._resolve_groupings(model)
        file_ns_url, file_ns_prefix = self._get_global_namespace(model)
        if self._config_prefix in file_ns_url:
            self._parse_xml_chunk_containers(model, file_ns_url, file_ns_prefix)
            self._parse_xml_chunk_augments(model, file_ns_url, file_ns_prefix)
            self._parse_xml_chunk_identities(model, file_ns_url)

    def _resolve_groupings(self, model):
        groupings = {}
        for data_definition in model.findall('/' + ConfigModel.GROUPING_TAG):
            groupings[data_definition.attrib['name']] = data_definition

        for uses in model.findall('//' + ConfigModel.USES_TAG):
            if uses.attrib['name'] in groupings:
                parent_elem = uses.getparent()
                for data_definition in groupings[uses.attrib['name']]:
                    parent_elem.append(deepcopy(data_definition))
                parent_elem.remove(uses)

    def _parse_xml_chunk_containers(self, model, file_ns_url, file_ns_prefix):
        containers = model.findall('/' + ConfigModel.CONTAINER_TAG)
        for container in containers:
            if container.attrib['name'] == self._config_elem_name:
                self._config_root = container
                self._config_prefix = file_ns_prefix
                self._config_ns = file_ns_url

    def _parse_xml_chunk_augments(self, model, file_ns_url, file_ns_prefix):
        augments = model.findall('//' + ConfigModel.AUGMENT_TAG)
        for augment in augments:
            target_path = augment.attrib['target-node']
            if not target_path in self._xml_chunks:
                self._xml_chunks[target_path] = []
            augment.attrib[ConfigModel.PREFIX_ATTR] = file_ns_prefix
            augment.attrib[ConfigModel.NS_ATTR] = file_ns_url
            self._xml_chunks[target_path].append(augment)

    def _parse_xml_chunk_identities(self, model, file_ns_url):
        identities = model.findall('/' + ConfigModel.IDENTITY_TAG)
        for identity in identities:
            insert_ns_elem = identity
            base_elem = identity.find(ConfigModel.BASE_TAG)
            if base_elem is not None:
                base_elem.attrib['name'] = self._strip_ns_prefix_if_present(
                                               base_elem.attrib['name'])
                insert_ns_elem = base_elem
            etree.SubElement(insert_ns_elem, 'modelns', {'uri':file_ns_url})
            self._identity_elems.append(identity)

    def _strip_ns_prefix_if_present(self, token):
        if ':' in token:
            token = token.split(':')[1]
        return token

    def _combine_xml_chunks(self, container, target_path, file_ns_prefix):
        if target_path in self._xml_chunks:
            for chunk in self._xml_chunks[target_path]:
                container.append(chunk)

        self._search_for_xml_chunks(container, target_path, file_ns_prefix)

    def _search_for_xml_chunks(self, container, target_path, file_ns_prefix):
        for child in container:
            if ConfigModel.PREFIX_ATTR in child.attrib:
                ns_prefix = child.attrib[ConfigModel.PREFIX_ATTR]
            else:
                ns_prefix = file_ns_prefix
            if child.tag in [self.AUGMENT_TAG, self.CHOICE_TAG, self.CASE_TAG]:
                self._search_for_xml_chunks(child, target_path, ns_prefix)
            elif child.tag in [self.CONTAINER_TAG, self.LIST_TAG]:
                new_target_path = target_path + '/' + ns_prefix + ':' + child.attrib['name']
                self._combine_xml_chunks(child, new_target_path, ns_prefix)

    def _parse_combined_xml(self, combined_xml, prefix):
        path = self._config_elem_name
        self._define_namespace(path, prefix, self._config_ns)
        self._define_container(path, [])

        self._walk_containers_recursive(path, self._config_root)
        self._parse_identities(combined_xml)

    def _get_global_namespace(self, model):
        ns_elem = model.find('/' + ConfigModel.NAMESPACE_TAG)

        if ns_elem is None:
            raise ConfigModelParseError(
                'Could not find global namespace value in XML model')

        prefix_elem = model.find('/' + ConfigModel.PREFIX_TAG)

        if prefix_elem is None:
            raise ConfigModelParseError(
                'Could not find global namespace prefix in XML model')
        return ns_elem.attrib['uri'], prefix_elem.attrib['value']

    def _define_namespace(self, path, prefix, namespace):
        self.namespace_map[path] = (prefix, namespace)
        self._identity_prefix_map[namespace] = prefix

    def _define_container(self, path, keys):
        self.container_map[path] = keys

    def _find_config_container_element(self, model):
        config = model.find(
            '/' + ConfigModel.CONTAINER_TAG + "[@name='" +
            self._config_elem_name + "']")

        if config is None:
            raise ConfigModelParseError(
                'Could not find config container in XML model')

        return config

    def _walk_containers_recursive(self, path, parent):
        for child in parent:
            if child.tag in [self.AUGMENT_TAG, self.CHOICE_TAG, self.CASE_TAG]:
                self._walk_containers_recursive(path, child)
            elif child.tag in [self.CONTAINER_TAG, self.LIST_TAG]:
                self._parse_container(path, parent, child)
                child_path = self._append_elem_to_path(path, child)
                self._walk_containers_recursive(child_path, child)
            elif child.tag in [self.LEAF_TAG, self.LEAF_LIST_TAG]:
                self._parse_leaf(path, child)

    def _parse_container(self, path, parent, child):
        child_path = self._append_elem_to_path(path, child)
        if parent.tag == self.AUGMENT_TAG:
            self._define_namespace(child_path,
                                   parent.attrib[self.PREFIX_ATTR],
                                   parent.attrib[self.NS_ATTR])

        keys = []
        for item in child:
            if item.tag == self.KEY_TAG:
                keys.extend(item.attrib['value'].split())

        self._define_container(child_path, keys)

    @staticmethod
    def _append_elem_to_path(path, child):
        name = child.attrib['name']
        return path + '/' + name

    def _parse_leaf(self, path, leaf):
        augment_ancestor = self._get_closest_augment_ancestor(leaf)
        if augment_ancestor is not None:
            self._define_namespace(self._append_elem_to_path(path, leaf),
                                   augment_ancestor.attrib[self.PREFIX_ATTR],
                                   augment_ancestor.attrib[self.NS_ATTR])

        type_elem = leaf.find(self.TYPE_TAG)
        if (type_elem is not None and
                type_elem.attrib['name'] == 'identityref'):

            base_elem = type_elem.find(self.BASE_TAG)
            if base_elem is not None:
                self._define_identity_path_map(self._append_elem_to_path(path,
                                                                         leaf),
                                               base_elem.attrib['name'])

    def _get_closest_augment_ancestor(self, leaf):
        augment_ancestors = leaf.xpath('ancestor-or-self::yin:augment',
                                       namespaces=ConfigModel._NSMAP)

        if len(augment_ancestors) > 0:
            closest_augment_ancestor = augment_ancestors[-1]
        else:
            closest_augment_ancestor = None

        return closest_augment_ancestor

    def _define_identity_path_map(self, path, base_name):
        self._identity_path_map[path] = base_name

    def _parse_identities(self, model):
        for path, base_name in self._identity_path_map.iteritems():
            identity_values = self._find_identities(model, base_name)
            self.identity_map[path] = identity_values

    def _find_identities(self, model, base_name):
        identity_values = {}

        for child in self._identity_elems:
            base_elem = child.find(self.BASE_TAG)
            if (base_elem is not None and
                    base_elem.attrib['name'] == base_name):

                identity_prefix = self._get_identity_prefix(base_elem)
                identity_values[child.attrib['name']] = identity_prefix

        return identity_values

    def _get_identity_prefix(self, base_elem):
        ns_elem = base_elem.find('modelns')
        if ns_elem is None:
            raise ConfigModelParseError(
                'No namespace defined for ' + ns_elem.tag)

        return self._identity_prefix_map[ns_elem.attrib['uri']]
