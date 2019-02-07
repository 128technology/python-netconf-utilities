#!/bin/python
from sys import argv
import os
from ncclient import manager
from ote_utils.utils import Config
from lxml import etree

if len(argv) < 3:
  print "This tool will create an XML 128T configuration from a text config, for example the output of 'show config runnning'."
  print "Usage: {0} <text config filename> <xml config filename>".format(argv[0])
else:
  with open(argv[1], 'r') as config:
    config_text = config.read()
  cc = Config.Config()
  cc.load_t128_config_model('/var/model/consolidatedT128Model.xml')
  config_xml = cc.convert_config_to_netconf_xml(config_text.split('\n'))
  config_text_xml = etree.tostring(config_xml)
  with open(argv[2], 'w') as xml_file:
    xml_file.write(config_text_xml)
