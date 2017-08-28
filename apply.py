#!/bin/python
from sys import argv
import os
from ncclient import manager
from netconfutils import netconfconverter

class t128ConfigUtils(object):
    def __init__(self):
        return
    def readFile(self, filedir):
        string = ""
        with open(filedir, "r") as f:
            for line in f:
                string = string + line
        f.close()
        return string
    def writeFile(self, filedir, string):
        with open(filedir, "w") as f:
            f.write(string)
        f.close()
    def readConfig(self, config_filedir):
        if os.path.isfile(config_filedir):
            config_str = self.readFile(config_filedir)
        else:
            self.initializeConfigFile(config_filedir)
            config_str = self.readFile(config_filedir)
        return config_str
    def writeConfig(self, config_filedir, config_xml):
        try:
            config_xml = etree.tostring(config_xml, pretty_print=True)
        except TypeError:
            self.writeFile(config_filedir, config_xml)
            return True
        self.writeFile(config_filedir, config_xml)
        return True
    def initializeConfigFile(self, config_filedir):
        self.writeFile(config_filedir, "Thank you for using 128T Router")
    def isSameConfig(self, new_config, current_config):
        return True if new_config == current_config else False

class NetconfConverterAgent(object):
    def __init__(self, netconf_converter):
        self.netconf_converter = netconf_converter
    def configStringToCommands(self, config_str):
        config_commands = config_str.split("\n")
        config_commands = list(command.strip(' \t') for command in config_commands)
        config_commands = filter(None, config_commands)
        return config_commands
    def configToXML(self, config_model, config_commands):
        self.netconf_converter.load_config_model(config_model, config_prefix='t128')
        config_xml = self.netconf_converter.convert_config_to_netconf_xml(config_commands, "config")
        return config_xml

class t128Converter(object):
    def __init__(self, converter_agent):
        self.converter_agent = converter_agent
    def produceConfigXML(self, config_model_filedir, candidate_config):
        candidate_config_xml = self.converter_agent.configToXML(config_model_filedir, candidate_config)
        return candidate_config_xml

class ncclientAgent(object):
    def __init__(self, ncclient_manager):
        self.netconf_session = ncclient_manager
    def editConfig(self, target_config, config_xml):
        edit_status = self.netconf_session.edit_config(target=target_config, config=config_xml)
        return edit_status
    def replaceConfig(self, target_config, config_xml):
        replace_status = self.netconf_session.edit_config(target=target_config, config=config_xml, default_operation="replace")
        return replace_status
    def removeConfig(self, target_config, config_xml):
        remove_status = self.netconf_session.delete_config(source=config_xml, target=target_config)
        return remove_status
    def commitConfig(self):
        commit_status = self.netconf_session.commit()
        self.netconf_session.close_session()
        return commit_status


class t128Configurator(object):
    def __init__(self, config_agent):
        self.config_agent = config_agent
    def config(self, candidate_config_xml, state):
        action_status = "None"
        if state == "edit":
            action_status = self.config_agent.editConfig("candidate", candidate_config_xml)
        if state == "replace":
            action_status = self.config_agent.replaceConfig("candidate", candidate_config_xml)
        return action_status
    def commit(self):
        commit_status = self.config_agent.commitConfig()
        return commit_status

def _create_config_xml(config_text, config_model_filedir='/var/model/*.yin', host='127.0.0.1', port='830', username='root', key_filename='/etc/128technology/ssh/pdc_ssh_key'):
  with manager.connect(host=host, port=port, username=username, key_filename=key_filename, allow_agent=True, look_for_keys=False, hostkey_verify=False) as m:
    c = m.get_config(source='running').data
  netconf_converter = netconfconverter.NetconfConverter()
  nc_converter_agent = NetconfConverterAgent(netconf_converter)
  t128_converter = t128Converter(nc_converter_agent)
  return t128_converter.produceConfigXML(config_model_filedir, config_text)

def _commit_config_xml(config_xml, t128_host='127.0.0.1', t128_port='830', t128_user='root', t128_publickey='/etc/128technology/ssh/pdc_ssh_key'):
    netconf_session = manager.connect(host=t128_host, port=t128_port, username=t128_user, key_filename=t128_publickey,
                                          allow_agent=True, look_for_keys=False, hostkey_verify=False)
    ncclient_agent = ncclientAgent(netconf_session)
    t128_configurator = t128Configurator(ncclient_agent)
    config_status = t128_configurator.config(config_xml, 'edit')

    if config_status.ok:
        commit_status = t128_configurator.commit()
        if commit_status.ok:
            print "Configuration committed successfully"
        else:
            print "There was an error committing the config"
    else:
        print "There is an adding the config"

if len(argv) < 2:
  print "This tool will apply a 128T configuration to the local router/conductor over the NETCONF interface. The configuration must be saved to a file in flat-text format"
  print "Usage: {0} filename".format(argv[0])
else:
  with open(argv[1], 'r') as config:
    config_text = config.read()
  config_text_xml = _create_config_xml(config_text)
  _commit_config_xml(config_text_xml)
