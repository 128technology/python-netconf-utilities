import os
import sys
import textwrap

import pytest
import xmlunittest

from lxml import etree
from ote_utils.netconfutils import netconfconverter


def t128_model():
    t128_model = netconfconverter.NetconfConverter()
    t128_model.load_config_model(get_resource_path("consolidatedT128Model.xml"))
    return t128_model


class NetconfConverterTestCase(xmlunittest.XmlTestCase):
    def setUp(self):
        super(NetconfConverterTestCase, self).setUp()
        self.t128_model = t128_model()

    def test_basic_convert(self):
        config = textwrap.dedent(
            """
            config
                authority
                exit
            exit"""
        )

        given = etree.tostring(self.t128_model.convert_config_to_netconf_xml(config, tag="config"))

        expected = textwrap.dedent(
            """
            <ns0:config xmlns:ns0="urn:ietf:params:xml:ns:netconf:base:1.0">
                <t128:config xmlns:t128="http://128technology.com/t128">
                    <authy:authority xmlns:authy="http://128technology.com/t128/config/authority-config">
                    </authy:authority>
                </t128:config>
            </ns0:config>"""
        )

        self.assertXmlEquivalentOutputs(given, expected)

    def test_extra_exit_convert(self):
        config = textwrap.dedent(
            """
            config
                authority
                exit
                exit
            exit"""
        )

        with pytest.raises(netconfconverter.ConfigParseError):
            etree.tostring(self.t128_model.convert_config_to_netconf_xml(config, tag="config"))

    def test_missing_exit_convert(self):
        config = textwrap.dedent(
            """
            config
                authority
                exit"""
        )

        with pytest.raises(netconfconverter.ConfigParseError):
            etree.tostring(self.t128_model.convert_config_to_netconf_xml(config, tag="config"))

    def test_wrong_element_convert(self):
        config = textwrap.dedent(
            """
            config
                authority
                    name Authority128
                    service east
                        name east
                        service-policy tcpPolicy
                    exit
                    service west
                        WRONG_ELEMENT
                        service-policy tcpPolicy
                    exit
                    service-policy tcpPolicy
                        name tcpPolicy
                        transport-state-enforcement allow
                    exit
                exit
            exit"""
        )

        with pytest.raises(netconfconverter.ConfigParseError):
            etree.tostring(self.t128_model.convert_config_to_netconf_xml(config, tag="config"))

    def test_security_convert(self):
        config = textwrap.dedent(
            """
            config
                authority
                    name Authority128
                    security aes1
                        name aes1
                        encryption-cipher aes-cbc-256
                        encryption-iv f0f1f2f3f4f5f6f7f8f9fafbfcfdfef0
                        encryption-key 603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff0
                        hmac-key 4a656665
                        encrypt true
                        hmac true
                    exit
                exit
            exit"""
        )

        given = etree.tostring(self.t128_model.convert_config_to_netconf_xml(config, tag="config"))

        expected = textwrap.dedent(
            """
            <ns0:config xmlns:ns0="urn:ietf:params:xml:ns:netconf:base:1.0">
                <t128:config xmlns:t128="http://128technology.com/t128">
                    <authy:authority xmlns:authy="http://128technology.com/t128/config/authority-config">
                        <authy:name>Authority128</authy:name>
                        <authy:security>
                            <authy:name>aes1</authy:name>
                            <authy:encryption-cipher>aes-cbc-256</authy:encryption-cipher>
                            <authy:encryption-iv>f0f1f2f3f4f5f6f7f8f9fafbfcfdfef0</authy:encryption-iv>
                            <authy:encryption-key>603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff0</authy:encryption-key>
                            <authy:hmac-key>4a656665</authy:hmac-key>
                            <authy:encrypt>true</authy:encrypt>
                            <authy:hmac>true</authy:hmac>
                        </authy:security>
                    </authy:authority>
                </t128:config>
            </ns0:config>"""
        )

        self.assertXmlEquivalentOutputs(given, expected)

    def test_service_convert(self):
        config = textwrap.dedent(
            """
            config
                authority
                    name Authority128
                    service inet
                        name inet
                        id 10
                        service-group all
                        description service for everyone
                        enabled true
                        scope public
                        security aes1
                        address 0.0.0.0/0
                        access-policy 0.0.0.0/0
                            source 0.0.0.0/0
                            permission allow
                        exit
                    exit
                exit
            exit"""
        )

        given = etree.tostring(self.t128_model.convert_config_to_netconf_xml(config, tag="config"))

        expected = textwrap.dedent(
            """
            <ns0:config xmlns:ns0="urn:ietf:params:xml:ns:netconf:base:1.0">
                <t128:config xmlns:t128="http://128technology.com/t128">
                    <authy:authority xmlns:authy="http://128technology.com/t128/config/authority-config">
                        <authy:name>Authority128</authy:name>
                        <svc:service xmlns:svc="http://128technology.com/t128/config/service-config">
                            <svc:name>inet</svc:name>
                            <svc:id>10</svc:id>
                            <svc:service-group>all</svc:service-group>
                            <svc:description>service for everyone</svc:description>
                            <svc:enabled>true</svc:enabled>
                            <svc:scope>public</svc:scope>
                            <svc:security>aes1</svc:security>
                            <svc:address>0.0.0.0/0</svc:address>
                            <svc:access-policy>
                                <svc:source>0.0.0.0/0</svc:source>
                                <svc:permission>allow</svc:permission>
                            </svc:access-policy>
                        </svc:service>
                    </authy:authority>
                </t128:config>
            </ns0:config>"""
        )

        self.assertXmlEquivalentOutputs(given, expected)

    def test_routing_options(self):
        config = textwrap.dedent(
            """
            config
                authority
                    name Authority128
                    router combo1
                        name combo1
                        routing default-instance
                            type default-instance
                            static-route 66.151.176.0/24 1
                                destination-prefix 66.151.176.0/24
                                distance 1
                                next-hop 1.1.1.1
                            exit
                            routing-protocol bgp
                                type bgp
                                local-as 2
                                router-id 10
                                neighbor 172.16.1.3
                                    neighbor-address 172.16.1.3
                                    neighbor-as 2
                                    address-family ipv4-unicast
                                        afi-safi ipv4-unicast
                                    exit
                                    timers
                                          hold-time 90
                                          keepalive-interval 30
                                    exit
                                exit
                                neighbor 172.16.1.1
                                    neighbor-address 172.16.1.1
                                    neighbor-as 1
                                    timers
                                        hold-time 90
                                        keepalive-interval 30
                                    exit
                                    address-family ipv4-unicast
                                        afi-safi ipv4-unicast
                                    exit
                                exit
                            exit
                        exit
                    exit
                exit
            exit"""
        )

        given = etree.tostring(self.t128_model.convert_config_to_netconf_xml(config, tag="config"))

        expected = textwrap.dedent(
            """
            <ns0:config xmlns:ns0="urn:ietf:params:xml:ns:netconf:base:1.0">
            <t128:config xmlns:t128="http://128technology.com/t128">
                <authy:authority xmlns:authy="http://128technology.com/t128/config/authority-config">
                    <authy:name>Authority128</authy:name>
                    <authy:router>
                        <authy:name>combo1</authy:name>
                        <rt:routing xmlns:rt="http://128technology.com/t128/config/routing-config">
                            <rt:type>rt:default-instance</rt:type>
                            <rt:static-route>
                                <rt:destination-prefix>66.151.176.0/24</rt:destination-prefix>
                                <rt:distance>1</rt:distance>
                                <rt:next-hop>1.1.1.1</rt:next-hop>
                            </rt:static-route>
                            <rt:routing-protocol>
                                <rt:type>rt:bgp</rt:type>
                                <bgp:local-as xmlns:bgp="http://128technology.com/t128/config/bgp-config">2</bgp:local-as>
                                <bgp:router-id xmlns:bgp="http://128technology.com/t128/config/bgp-config">10</bgp:router-id>
                                <bgp:neighbor xmlns:bgp="http://128technology.com/t128/config/bgp-config">
                                    <bgp:neighbor-address>172.16.1.3</bgp:neighbor-address>
                                    <bgp:neighbor-as>2</bgp:neighbor-as>
                                    <bgp:address-family>
                                        <bgp:afi-safi>bgp:ipv4-unicast</bgp:afi-safi>
                                    </bgp:address-family>
                                    <bgp:timers>
                                        <bgp:hold-time>90</bgp:hold-time>
                                        <bgp:keepalive-interval>30</bgp:keepalive-interval>
                                    </bgp:timers>
                                </bgp:neighbor>
                                <bgp:neighbor xmlns:bgp="http://128technology.com/t128/config/bgp-config">
                                    <bgp:neighbor-address>172.16.1.1</bgp:neighbor-address>
                                    <bgp:neighbor-as>1</bgp:neighbor-as>
                                    <bgp:timers>
                                        <bgp:hold-time>90</bgp:hold-time>
                                        <bgp:keepalive-interval>30</bgp:keepalive-interval>
                                    </bgp:timers>
                                    <bgp:address-family>
                                        <bgp:afi-safi>bgp:ipv4-unicast</bgp:afi-safi>
                                    </bgp:address-family>
                                </bgp:neighbor>
                            </rt:routing-protocol>
                        </rt:routing>
                    </authy:router>
                </authy:authority>
            </t128:config>
            </ns0:config>"""
        )

        self.assertXmlEquivalentOutputs(given, expected)

    def test_routing_convert(self):
        config = textwrap.dedent(
            """
            config
                authority
                    name Authority128
                    router combo1
                        name combo1
                        routing default-instance
                            type default-instance
                            routing-protocol bgp
                                type bgp
                                local-as 2
                                router-id 10
                                neighbor 172.16.1.3
                                    neighbor-address 172.16.1.3
                                    neighbor-as 2
                                    address-family ipv4-unicast
                                        afi-safi ipv4-unicast
                                    exit
                                    timers
                                          hold-time 90
                                          keepalive-interval 30
                                    exit
                                exit
                                neighbor 172.16.1.1
                                    neighbor-address 172.16.1.1
                                    neighbor-as 1
                                    timers
                                        hold-time 90
                                        keepalive-interval 30
                                    exit
                                    address-family ipv4-unicast
                                        afi-safi ipv4-unicast
                                    exit
                                exit
                            exit
                        exit
                    exit
                exit
            exit"""
        )

        given = etree.tostring(self.t128_model.convert_config_to_netconf_xml(config, tag="config"))

        expected = textwrap.dedent(
            """
            <ns0:config xmlns:ns0="urn:ietf:params:xml:ns:netconf:base:1.0">
                <t128:config xmlns:t128="http://128technology.com/t128">
                    <authy:authority xmlns:authy="http://128technology.com/t128/config/authority-config">
                        <authy:name>Authority128</authy:name>
                        <authy:router>
                            <authy:name>combo1</authy:name>
                            <rt:routing xmlns:rt="http://128technology.com/t128/config/routing-config">
                                <rt:type>rt:default-instance</rt:type>
                                <rt:routing-protocol>
                                    <rt:type>rt:bgp</rt:type>
                                    <bgp:local-as xmlns:bgp="http://128technology.com/t128/config/bgp-config">2</bgp:local-as>
                                    <bgp:router-id xmlns:bgp="http://128technology.com/t128/config/bgp-config">10</bgp:router-id>
                                    <bgp:neighbor xmlns:bgp="http://128technology.com/t128/config/bgp-config">
                                        <bgp:neighbor-address>172.16.1.3</bgp:neighbor-address>
                                        <bgp:neighbor-as>2</bgp:neighbor-as>
                                        <bgp:address-family>
                                            <bgp:afi-safi>bgp:ipv4-unicast</bgp:afi-safi>
                                        </bgp:address-family>
                                        <bgp:timers>
                                            <bgp:hold-time>90</bgp:hold-time>
                                            <bgp:keepalive-interval>30</bgp:keepalive-interval>
                                        </bgp:timers>
                                    </bgp:neighbor>
                                    <bgp:neighbor xmlns:bgp="http://128technology.com/t128/config/bgp-config">
                                        <bgp:neighbor-address>172.16.1.1</bgp:neighbor-address>
                                        <bgp:neighbor-as>1</bgp:neighbor-as>
                                        <bgp:timers>
                                            <bgp:hold-time>90</bgp:hold-time>
                                            <bgp:keepalive-interval>30</bgp:keepalive-interval>
                                        </bgp:timers>
                                        <bgp:address-family>
                                            <bgp:afi-safi>bgp:ipv4-unicast</bgp:afi-safi>
                                        </bgp:address-family>
                                    </bgp:neighbor>
                                </rt:routing-protocol>
                            </rt:routing>
                        </authy:router>
                    </authy:authority>
                </t128:config>
            </ns0:config>"""
        )

        self.assertXmlEquivalentOutputs(given, expected)

    def test_delete_description(self):
        config = textwrap.dedent(
            """
            config
                authority
                    tenant Foo
                        delete description force
                        member internet
                            delete address force 1.1.1.1/16
                        exit
                    exit
                exit
            exit"""
        )

        given = etree.tostring(self.t128_model.convert_config_to_netconf_xml(config, tag="config"))

        expected = textwrap.dedent(
            """
            <ns0:config xmlns:ns0="urn:ietf:params:xml:ns:netconf:base:1.0">
                <t128:config xmlns:t128="http://128technology.com/t128">
                    <authy:authority xmlns:authy="http://128technology.com/t128/config/authority-config">
                        <authy:tenant>
                            <authy:description ns0:operation="delete">force</authy:description>
                            <authy:member>
                                <authy:address ns0:operation="delete">force 1.1.1.1/16</authy:address>
                            </authy:member>
                        </authy:tenant>
                    </authy:authority>
                </t128:config>
            </ns0:config>"""
        )

        self.assertXmlEquivalentOutputs(given, expected)

    def test_basic_attr(self):
        config = textwrap.dedent(
            """
            config
                authority
                exit
            exit"""
        )

        given = etree.tostring(
            self.t128_model.convert_config_to_netconf_xml(
                config, tag="config", attributes={"test": "test"}
            )
        )

        expected = textwrap.dedent(
            """
            <ns0:config xmlns:ns0="urn:ietf:params:xml:ns:netconf:base:1.0" test="test">
                <t128:config xmlns:t128="http://128technology.com/t128">
                    <authy:authority xmlns:authy="http://128technology.com/t128/config/authority-config">
                    </authy:authority>
                </t128:config>
            </ns0:config>"""
        )

        self.assertXmlEquivalentOutputs(given, expected)

    def test_empty_attr(self):
        config = textwrap.dedent(
            """
            config
                authority
                    router
                        name all
                        service-route west
                            name west
                            service-name west
                            routing-stack
                        exit
                    exit
                exit
            exit"""
        )

        given = etree.tostring(
            self.t128_model.convert_config_to_netconf_xml(
                config, tag="config", attributes={"type": "subtree"}
            )
        )

        expected = textwrap.dedent(
            """
            <ns0:config xmlns:ns0="urn:ietf:params:xml:ns:netconf:base:1.0" type="subtree">
                <t128:config xmlns:t128="http://128technology.com/t128">
                    <authy:authority xmlns:authy="http://128technology.com/t128/config/authority-config">
                        <authy:router>
                            <authy:name>all</authy:name>
                            <svc:service-route xmlns:svc="http://128technology.com/t128/config/service-config">
                                <svc:name>west</svc:name>
                                <svc:service-name>west</svc:service-name>
                                <svc:routing-stack/>
                            </svc:service-route>
                        </authy:router>
                    </authy:authority>
                </t128:config>
            </ns0:config>"""
        )

        self.assertXmlEquivalentOutputs(given, expected)

    def test_get_request_filter(self):
        request = textwrap.dedent(
            """
            config
                authority
                    router {router}
                        name {router}
                        node {dut_node}
                            name {dut_node}
                            top-sessions
                                bandwidth
                                exit
                            exit
                        exit
                    exit
                exit
            exit"""
        )

        given = etree.tostring(
            self.t128_model.convert_config_to_netconf_xml(
                request, tag="filter", attributes={"type": "subtree"}
            )
        )

        expected = textwrap.dedent(
            """
            <ns0:filter xmlns:ns0="urn:ietf:params:xml:ns:netconf:base:1.0" type="subtree">
                <t128:config xmlns:t128="http://128technology.com/t128">
                    <authy:authority xmlns:authy="http://128technology.com/t128/config/authority-config">
                        <authy:router>
                            <authy:name>{router}</authy:name>
                            <sys:node xmlns:sys="http://128technology.com/t128/config/system-config">
                                <sys:name>{dut_node}</sys:name>
                                <al:top-sessions xmlns:al="http://128technology.com/t128/analytics">
                                    <al:bandwidth>
                                    </al:bandwidth>
                                </al:top-sessions>
                            </sys:node>
                        </authy:router>
                    </authy:authority>
                </t128:config>
            </ns0:filter>"""
        )

        self.assertXmlEquivalentOutputs(given, expected)


def get_resource_path(resource_filename):
    return os.path.join(os.path.dirname(__file__), "resources", resource_filename)
