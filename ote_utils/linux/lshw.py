import errno
import fnmatch
import json
import logging
import os.path
import re
import socket
import time

from ote_utils.remote_api import LinuxAPI
from ote_utils.ote_logger import OteLogger

logger = OteLogger(__name__)

class LshwException(Exception):
    """Exception for Lshwclass
    """
    pass


class Lshw(LinuxAPI):
    """A series of
    dictionaries are used to specify the host, deployment and other parameters.
    """

    def get_host_hw_info_file(self, file_name='lshw.json', output_dir='/tmp'):
        """Saves the lshw output as a json and moves it to a local
        /tmp/ dir

        Args:
            file_name (str, optional): json file containing output of lshw
            output_dir (str, optional): output path of lshw json file

        """
        temp_dir = self.CLIENT.create_tmp_directory()
        remote_file = os.path.join(temp_dir, file_name)
        self.CLIENT.execute_command('sudo lshw -json > ' + remote_file)
        self.CLIENT.execute_command('sudo chmod 0777 ' + remote_file)
        logger.debug('file is : {}'.format(remote_file))
        self.CLIENT.get_file(remote_file, output_dir + '/' + file_name)

def get_host_hw_dictionary(file_name, output_dir='build/'):
   """Converts Json lshw file to dict

   Args:
       file_name (str, optional): json file containing output of lshw
       output_dir (str, optional): output path of lshw json file

   Returns:
       dict: data from lshw json file
   """
   path = output_dir + file_name
   with open(path) as data_file:
       lshw_data = json.load(data_file)
   logger.debug('lshw data dictionary: {}'.format(lshw_data))
   return lshw_data
