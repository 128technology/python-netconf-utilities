#!/bin/python
from sys import argv
import os
from ncclient import manager
import Config

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
        print "There was an error adding the candidate config"

if len(argv) < 2:
  print "This tool will apply a 128T configuration to the local router/conductor over the NETCONF interface. The configuration must be saved to a file in flat-text format"
  print "Usage: {0} filename".format(argv[0])
else:
  with open(argv[1], 'r') as config:
    config_text = config.read()
  cc = Config.Config()
  cc.load_t128_config_model('/var/model/consolidatedT128Model.xml')
  config_text_xml = cc.convert_config_to_netconf_xml(config_text.split('\n'))
  _commit_config_xml(config_text_xml)
