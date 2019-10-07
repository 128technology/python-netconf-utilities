# 128T Python NETCONF Utilities #
This repo contains libraries and scripts to simplify working with the configuration of 128T Routers over the NETCONF interface.  The majority of the files from this project are copied directly from the Engineering i95 repo under /i95/tools/python_distributions directory.  In addition, the Class for modeling 128T configuration has been copied from the i95 repo /i95/robot/lib/libraries/Config.py to /ote_utils/utils/Config.py in this repo for simplicity.  In the future, these utilities may be reloacted to a shared location in order to avoid divergence away from Engineering.

## Local Packaging ##
To create locally packaged wheel house with all netconf_utils requirments:
run `python3.6 setup.py package` -> Creates local dependancies in `wheelhouse` dir
Now tar the repo: `tar -zcvf netconf_utils.tar.gz python-netconf-utilities`

!! Note !!
This script collects the installed (compiled) requirements from where it runs, this means that if your requirements.txt contains any requirements that are based on C-extensions such as psycopg for example, the compiled package will be collected.
When you unpack the archive at the destination if the system is different than the system you collected the package from it will not work as intended and even crash.

ubuntu != centos != macOS
python2.6 != python2.7 != python3.6 etc...

Now to install: Untar package `tar -xzf netconf_utils.tar.gz`
And install with locals `pip install -r requirements.txt  --no-index --find-links wheelhouse`


## Installation ##
These utilities should be installed on a 128T Router or Conductor or another system that will interact with a remote 128T Router or Conductor's NETCONF interface.  After cloning the repo, run the following commands to install the libraries and other required dependencies.
```
yum -y install python-ncclient
pip install yinsolidated
pip install <path/to/clone/location>
```

## Applying a configuration ##
A simple shell script has been provided which can be used to apply a full textual configuration to a 128T Router or Conductor.  The format of this text file should match the format provided by `show configuration running` on the CLI.
```
cd <path/to/clone/location>
./apply.py <path/to/config/text/file>
```

## Using the libraries in your code ##
Below you will find some example code to get you started working with these libraries.

### Importing the modules ###
In order to interact with a 128T Router or Condcutor over NETCONF, you must import a manager from the [Python ncclient library](https://ncclient.readthedocs.io/en/latest/).  To convert the textual representation of the 128T cnfiguration to XML so that it can be pushed over NETCONF, you need to import the Config module.
```
from ncclient import manager
from ote_utils import utils.Config
```

When working with the XML configuration, it is often useful to use the [Python lxml library](http://lxml.de).  Many of the further examples will make use of this library.  A full explanation of using this library is out of scope for this guide.
```
from lxml import etree
```

### Useful constants ###
When working with the various XML namespaces in the 128T configuration, these constants can be handy.
```
T128_NS = {'t128':'http://128technology.com/t128'}
AUTHORITY_NS = {'authority-config':'http://128technology.com/t128/config/authority-config'}
SYSTEM_NS = {'system-config':'http://128technology.com/t128/config/system-config'}
INTERFACE_NS = {'interface-config':'http://128technology.com/t128/config/interface-config'}
SERVICE_NS = {'service-config':'http://128technology.com/t128/config/service-config'}
```

### Helper classes and functions ###
This function can be used to pull the current XML configuration over NETCONF for further parsing.  The first two lines of code give an example for connecting to the 128T instance via the manager module of the ncclient library.
```
def _get_current_config_text(host='127.0.0.1', port='830', username='root', key_filename='/etc/128technology/ssh/pdc_ssh_key'):
  with manager.connect(host=host, port=port, username=username, key_filename=key_filename, allow_agent=True, look_for_keys=False, hostkey_verify=False) as m:
    c = m.get_config(source='running').data
  return c.find('t128:config', namespaces=T128_NS)
```

The ncclient session can also be wrapped around a helper class like the one below.  Note that this class accepts an option of `validationType` when running the function `commitConfig`.  The supported values of this option are `distributed` (the default) and `local`.  When encountering issues with distributed validate, it may be useful to commit the configuration with `local`.  Please note, this option is only available on a Conductor.
```
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

    def commitConfig(self, validationType='distributed'):
        if validationType == 'distributed':
          commit_status = self.netconf_session.commit()
        else:
          commit_command = etree.Element('{urn:ietf:params:xml:ns:netconf:base:1.0}commit', {'nc':'urn:ietf:params:xml:ns:netconf:base:1.0'})
          vt = etree.Element('{urn:128technology:netconf:validate-type:1.0}validation-type', {'vt':'urn:128technology:netconf:validate-type:1.0'})
          vt.text = validationType
          commit_command.append(vt)
          commit_status = self.netconf_session.dispatch(commit_command)
        self.netconf_session.close_session()
        return commit_status
```

This agent can be further wrapped into a helper class like the one shown below.  This class provides two functions: `config` for updating the configuration and `commit` for commiting changes.  The `config` function takes in a `state` parameter which can be `edit`, to apply the passed in configuration string as an update to the confiugration, or `replace` to remove the existing configuration and apply the passed in fconfiguration string as a new configuration.  The `validationType` as mentioned above can be passed through here as well.
```
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

    def commit(self, validationType='distributed'):
        commit_status = self.config_agent.commitConfig(validationType=validationType)
        return commit_status
```

This function makes use of the above two classes to push and commit a configuration change.  It takes in an XML object for the configuration and applies it to the current 128T Router or Conductor (with status set to `edit`).  It accepts an option or `validationType` if present or uses the default value of `distributed`.
```
def _commit_config_xml(config_xml, t128_host='127.0.0.1', t128_port='830', t128_user='root', t128_publickey='/etc/128technology/ssh/pdc_ssh_key', validationType='distributed'):
    netconf_session = manager.connect(host=t128_host, port=t128_port, username=t128_user, key_filename=t128_publickey,
                                          allow_agent=True, look_for_keys=False, hostkey_verify=False)

    ncclient_agent = ncclientAgent(netconf_session)
    t128_configurator = t128Configurator(ncclient_agent)
    config_status = t128_configurator.config(config_xml, 'edit')

    if config_status.ok:
        commit_status = t128_configurator.commit(validationType=validationType)
        if commit_status.ok:
            print "Configuration committed successfully"
        else:
            print "There was an error committing the config"
    else:
        print "There was an error adding the candidate config"
```

This code snippet will convert a text-based config into XML so that it can be applied over NETCONF.
```
cc = Config.Config()
cc.load_t128_config_model('/var/model/consolidatedT128Model.xml')
add_config_xml = cc.convert_config_to_netconf_xml(add_config.split('\n'))
```
