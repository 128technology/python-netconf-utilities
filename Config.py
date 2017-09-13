from ote_utils.netconfutils import netconfconverter
from ote_utils.ote_logger import OteLogger

logger = OteLogger(__name__)


class Config(object):
    """
        Defines a class for producing and manipulating T128 configuration to
        expose to robot framework tests.
    """

    def __init__(self):
        self.ncconv = netconfconverter.NetconfConverter()

    def load_t128_config_model(self, model_file):
        """
            Loads the configuration model from the fully consolidated XML file.

            == Args ==
            - model_file (str) - the name of the xml file containing the config model

            == Example ==
            Load T128 Config Model    ${model_file}
        """
        logger.debug('model_file: {}'.format(model_file))
        return self.ncconv.load_config_model(model_file)

    def load_t128_user_config_model(self, model_file):
        """
            Loads the user model from the fully consolidated XML file.

            == Args ==
            - model_file (str) - the name of the xml file containing the user config model

            == Example ==
            Load T128 User Config Model    ${model_file}
        """
        logger.debug('model_file: {}'.format(model_file))
        return self.ncconv.load_user_model(model_file)

    def convert_config_to_netconf_xml(self, config_list, tag='config', attributes={}):
        """
            Converts a T128 configuration to [Netconf.html | Netconf] XML. The
            ``config_list`` should be specified as a list i.e. using a ``@{ _NAME_
            }`` type variable.  The first line must be ``config`` with a matching
            ``exit`` at the end.

            == Args ==
            - config_list (list) - list of config elements
            - tag (str) - (Default: config) a tag to tell that the file it is given is a config file
            - attributes (dict) - a dictionary containing additional tag attributes

            == Example ==
            Convert Config to Netconf xml    ${config_list}    ${tag}    ${attributes}
        """
        return self.ncconv.convert_config_to_netconf_xml(config_list, tag, attributes)
