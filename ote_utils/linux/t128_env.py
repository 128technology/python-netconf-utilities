import glob
import json
import logging
import os
import os.path
import re
import shutil
import stat
import tempfile
import time
import yaml

from ote_sshlib_clients.initializer import InitializerClient
from ote_sshlib_clients.linux import LinuxClientException
from ote_sshlib_clients.ztpbase import ApplicationNotFoundError
from ote_utils.remote_api import LinuxAPI
from ote_utils.ote_logger import OteLogger
from ote_utils.linux.yum import Yum
from ote_sshlib import SSHClientException

t128_env_logger = OteLogger(__name__)

SALT_MINION_CONFIG_FILE = '/etc/salt/minion'
SALT_MASTER = 'salt-master'
SALT_MINION = 'salt-minion'
SALT_REPO_FILE = 'saltstack.repo'
SALT_RPM_IMPORT_COMMAND = 'sudo rpm --import https://repo.saltstack.com/yum/redhat/7/x86_64/archive/2016.11.5/SALTSTACK-GPG-KEY.pub'
TEMPORARY_JSON_FILE = 'NewData.json'


class T128EnvException(Exception):
    """Exception class for T128 Env specific errors
    """
    pass


class T128Env(LinuxAPI):
    """Functions related to t128 environent
    ... operations on linux host

    Attributes:
        CLEANUP_PROCESS_STRS (list): Proccesses to be manually killed
        DEFAULT_SHUTDOWN_TIMEOUT (int): wait (seconds) for shutdown
        DEFAULT_STARTUP_TIMEOUT (int): wait (seconds) for startup
        host (string): address or name of the host
        host_dict (dict): stores information about linux host
        image_dict (TYPE): stores information about the t128 service and image
        STARTUP_CONFIG_FILES (list): 128T files used to set loggin information
        startup_timeout (int): wait (seconds) for 128T to start
        T128_CONFIGURATION_DIRECTORY (str): config path
        T128_GLOBAL_FILE (str): 128T global.init with path
        T128_LOCAL_FILE (str): 128T local.init with path
        T128_LOG_DIRECTORY (str): 128T log path
        T128_PM_PROCLIST_FILE (str): 128T individual process startup file
        T128_PRODUCT_NAME (str): name of 128T service
        T128_SERVICE_FILE (str): 128T systemd service file
        T128_YIN_DIRECTORY (str): 128T yin model path
    """
    DEFAULT_STARTUP_TIMEOUT = 90
    DEFAULT_SHUTDOWN_TIMEOUT = 180
    CLEANUP_PROCESS_STRS = [
        'pdmTransportAgent'
    ]

    T128_SERVICE_FILE = '/usr/lib/systemd/system/128T.service'
    T128_LOG_DIRECTORY = '/var/log/128technology'
    T128_LIB_DIRECTORY = '/var/lib/128technology'
    T128_CONFIGURATION_DIRECTORY = '/etc/128technology'
    T128_CASSANDRA_DATA_PATH = '/usr/libexec/apache-cassandra/data/'
    T128_CASSANDRA_LOG_PATH = '/usr/libexec/apache-cassandra/logs/'
    T128_PM_PROCLIST_FILE = '/etc/128technology/processManagerProcessList.json'
    T128_GLOBAL_FILE = '/etc/128technology/global.init'
    T128_LOCAL_FILE = '/etc/128technology/local.init'
    T128_YIN_DIRECTORY = '/var/model'
    T128_PRODUCT_NAME = '128T'
    T128_DEFAULT_CONTROL_QUORUM_PORT = '2222'
    T128_DEFAULT_CONTROL_ELECTION_PORT = '2223'
    T128_RELEASE_REPO = \
        '''
[128techRelease]
name=128 Technology $releasever - $basearch
failovermethod=priority
sslverify=0
sslclientcert=/etc/pki/128tech/software_engineering.pem
baseurl=https://east.yum.128technology.com/repo/Release/CentOS/$releasever/$basearch/
enabled=0
metadata_expire=1h
gpgcheck=0
skip_if_unavailable=False
'''

    STARTUP_CONFIG_FILES = [T128_SERVICE_FILE, T128_PM_PROCLIST_FILE]
    CASSANDRA_PATHS = [T128_CASSANDRA_DATA_PATH, T128_CASSANDRA_LOG_PATH]

    startup_timeout = DEFAULT_STARTUP_TIMEOUT

    def __init__(self, device_dict):
        """Init

        Args:
            device_dict (dict): pupulate dictionaries that describe 128T Env
        """
        self.device_dict = device_dict
        self.host_dict = device_dict['host']
        self.image_dict = device_dict['image']
        self.host = self.host_dict['address']
        self.username = self.host_dict['username']
        self.password = self.host_dict['password']

    def set_t128_startup_timeout(self, timeout):
        """ Set the timeout value for starting up T128.

        Args:
            timeout (int): override global timeout

        Returns:
            int: startup_timeout
        """
        self.startup_timeout = timeout

    def deploy_t128(self, deployment_type, rpm_type=None):
        rpm = self._get_rpm(rpm_type)
        if deployment_type == 'install':
            self.install_t128(rpm)
        elif deployment_type == 'upgrade':
            self.upgrade_t128(rpm)
        elif deployment_type == 'downgrade':
            raise NotImplementedError('Downgrade not supported')
        else:
            raise T128EnvException('Deployment type not [install, upgrade, downgrade]: {} given'
                                   .format(deployment_type))

    def install_t128(self, rpm):
        """Deploys a T128 RPM. It gets most information from dictionary
        ... passed on during init of T128Env object
        """
        self._run_rpm_install(rpm)
        self._get_yin_files()
        self._enable_verbose_output()

    def initialize_128t(self, preference_data):
        """Runs the 128T Initializer with a specified templated preference data to
        ... configure the system

        Args:
            preference_data: A string of JSON representing a valid templated Initalizer
                preference file.

        Raises:
            ZtpRuntimeError: An error occurred during 128T initialization.
            KeyError: Preference data is improperly formatted.
            OSError: Could not write preference data to the remote system.
        """
        with InitializerClient(self.device_dict) as initializer_client:
            initializer_client.set_preference_data(str(preference_data))
            try:
                initializer_client.run()
            except ApplicationNotFoundError:
                t128_env_logger.debug(
                    'The Initializer was not found on the system; if this RPM '
                    "isn't CapeCod or earlier, expect some trouble"
                )

    def upgrade_t128(self, rpm):
        """Follows the 128T upgrade procedure

        Args:
            rpm (str): 128T rpm to upgate to
        """
        self._run_rpm_upgrade(rpm)
        self._get_yin_files()
        self._enable_verbose_output()

    def downgrade_t128(self, rpm):
        """Follow the 128T downgrade procedure
        Args:
            rpm (str): rpm to downgrade to
        Raises:
            NotImplementedError
        """
        raise NotImplementedError('Downgrade not supported')

    def generate_global_init_file(self, node_info):
        """Use json lib to replace info in global init file to match
        ... t128 configuration

        Args:
            node_info (list): contains all info to populate the global file
        """
        with open("global.init", "w") as f:
            t128_env_logger.debug('node_info for global init is: {}'.format(node_info))
            tab = '    '
            f.write('{\n' + tab + '"init":{\n')

            if node_info['router_name']:
                f.write(tab + tab + '"routerName": ' +
                        '"' + node_info['router_name'] + '"' + ',\n')

            f.write(tab + tab + '"control": {\n')
            first_node = True
            for control in node_info['controls']:
                if first_node:
                    first_node = False
                else:
                    f.write(',')
                f.write(tab + tab + tab + '"' + control['node_name'] + '": {\n')
                f.write(tab + tab + tab + tab + '"host": "' + control['address'] + '"')
                if control['quorum_port']:
                    f.write(',\n' + tab + tab + tab + tab + '"quorumPort": ' +
                            control['quorum_port'])
                if control['election_port']:
                    f.write(',\n' + tab + tab + tab + tab + '"leaderElectPort": ' +
                            control['election_port'])
                f.write('\n' + tab + tab + tab + '}\n')

            f.write(tab + tab + '},\n' + tab + tab + '"conductor": {\n')

            first_node = True
            for conductor in node_info['conductors']:
                if first_node:
                    first_node = False
                else:
                    f.write(',')
                f.write(tab + tab + tab + '"' + conductor['node_name'] + '": {\n')
                f.write(tab + tab + tab + tab + '"host": "' + conductor['address'] + '"')
                if conductor['quorum_port']:
                    f.write(',\n' + tab + tab + tab + tab + '"quorumPort": ' +
                            conductor['quorum_port'])
                if conductor['election_port']:
                    f.write(',\n' + tab + tab + tab + tab + '"leaderElectPort": ' +
                            conductor['election_port'])
                f.write('\n' + tab + tab + tab + '}\n')

            f.write(tab + tab + '}\n' + tab + '}\n}\n')

        self.CLIENT.put_file("./global.init", T128Env.T128_CONFIGURATION_DIRECTORY)
        os.remove("./global.init")

    def set_t128_local_node_name(self, current_name, new_name):
        """Use Sed to replace node name in local init file

        Args:
            current_name (str): current name in the file
            new_name (str): replacement name to be put in the file
        """
        file_with_path = T128Env.T128_LOCAL_FILE
        self.CLIENT.sed_string_replace(current_name, new_name, file_with_path)

    def start_t128(self):
        """Starts T128 using systemd
        """
        if self.image_dict['type'] == 'deploy':
            self.CLIENT.start_service(T128Env.T128_PRODUCT_NAME)
        elif self.image_dict['type'] == 'staging':
            self._run_t128_staging(image_dict)

    def stop_t128(self):
        """Stops T128
        """
        shutdown_success = True
        try:
            self.image_dict['type']
        except KeyError:
            t128_env_logger.debug('128T shutdown called but no type')
        else:
            try:
                if self.image_dict['type'] == 'deploy':
                    if self.CLIENT.is_service_running(T128Env.T128_PRODUCT_NAME):
                        self.CLIENT.stop_service(T128Env.T128_PRODUCT_NAME,
                                                 T128Env.DEFAULT_SHUTDOWN_TIMEOUT)
                elif self.image_dict['type'] == 'staging':
                    self._stop_t128_staging()
            except (T128EnvException, LinuxClientException) as error:
                t128_env_logger.debug('error returned is: {}'.format(error))
                shutdown_success = False
        return shutdown_success

    def restart_t128(self):
        """restarts T128 service
        """
        self.CLIENT.restart_service(T128Env.T128_PRODUCT_NAME)

    def enable_t128(self):
        """
        enables T128 service
        """
        self.CLIENT.enable_service(T128Env.T128_PRODUCT_NAME)

    def cleanup_t128_processes(self):
        """Kills leftover T128 processes.
        ... This should not be the case in normal operation
        """
        for process_name in T128Env.CLEANUP_PROCESS_STRS:
            self.CLIENT.kill_linux_process(process_name)

    def get_t128_log_files(self, output_dir=None, file_name=None):
        """Sftp 128T logs. Mostly used to collect logs on failure.

        Args:
            output_dir (None, optional): where to put the files
            file_name (None, optional): how to name the local folder

        Returns:
            string: directory name to which log files were copied
        """
        if output_dir is None:
            output_dir = self.image_dict['base_directory']

        if file_name is None:
            file_name = 'output'

        local_log_directory = self._create_local_directory(
            output_dir, 'logfiles', file_name)
        self.CLIENT.get_directory(T128Env.T128_LOG_DIRECTORY, local_log_directory)
        return local_log_directory

    def get_huge_page_allocation(self):
        """
        Gets the DUT's hugepage allocation and returns it as a string
        """
        try:
            return self.CLIENT.execute_command('sudo cat /etc/128technology/local.init | grep \'huge_1G\' -A 1')
        except SSHClientException:
            return 'huge_1G: 0\nhuge_2M: 2G'

    def clean_t128_logs(self):
        """Delete T128 logs.
        """
        wildcard_log_directory = os.path.join(
            T128Env.T128_LOG_DIRECTORY, '*')
        self.CLIENT.execute_command(
            'sudo rm ' + wildcard_log_directory + ' -rf')

    def clean_t128_lib(self):
        """Delete T128 lib folder.
        """
        wildcard_log_directory = os.path.join(
            T128Env.T128_LIB_DIRECTORY, '*')
        self.CLIENT.execute_command(
            'sudo rm ' + wildcard_log_directory + ' -rf')

    def clean_cassandra_paths(self):
        for path in T128Env.CASSANDRA_PATHS:
            path = os.path.join(path, '*')
            self.CLIENT.execute_command(
                'sudo rm ' + path + ' -rf')

    def check_t128_rpm_is_installed(self):
        """Verifies if the rpm on the DUT is active and matches the
        rpm in the base dir

        Returns:
            bool: True if rpm is installed
        """
        rpm_path = self.image_dict['base_directory']
        rpm_name = re.sub('\.rpm$', '', find_local_rpm(rpm_path))

        output_rpm, err, rc = self.CLIENT.execute_command('yum list installed 128T')
        try:
            base_rpm_installed = re.search(r'(\d\.[^\s]*(.centos|.fc21))', output_rpm).group(0)
            return bool(re.search(base_rpm_installed, rpm_name))
        except AttributeError:
            return False

    def check_t128_rpm_matches_os(self):
        """Checks /etc/redhat-release for Red Hat|CentOS|Fedora
        ... and makes sure the rpm matches for system
        Raises:
            T128EnvException: in case of no match
        """
        rpm = find_local_rpm(self.image_dict['base_directory'])

        output_os, err, rc = self.CLIENT.execute_command('cat /etc/redhat-release')
        os_match = re.search(r'(Red Hat|CentOS|Fedora)', output_os).group(0)

        if os_match == 'Red Hat':
            system_os = 'el7'
        elif os_match == 'CentOS':
            system_os = 'centos'
        else:
            system_os = 'fc21'

        if not bool(re.search(system_os, rpm)):
            raise T128EnvException('{} system OS doesn\'t match rpm OS'.format(os_match))

    def modify_t128_local_init(self, name='linecard-test', num_cores=None, huge_2m=None):
        """Modifies the remote local.init for a 128T machine

        Args:
            name (str, optional): default node name
            num_cores (None, optional): number of data cores needed
            huge_2m (None, optional): amount of huge page memory to be allocated

        """
        local_str = self._get_file_as_text(T128Env.T128_LOCAL_FILE)
        local_init = dict(json.loads(local_str))
        local_init = self.modify_t128_local_init_name(local_init, name)

        if num_cores is not None:
            local_init = self.modify_t128_number_of_fastlane_cores(local_init, num_cores)
        if huge_2m is not None:
            local_init = self.modify_t128_number_of_huge_2m(local_init, huge_2m)

        local_init = str(json.dumps(local_init, ensure_ascii=False,
                                    sort_keys=True, indent=4, separators=(',', ': ')))
        self.CLIENT.execute_command('echo  \'{}\' > {}'.format(
            local_init, T128Env.T128_LOCAL_FILE))

    def modify_t128_number_of_fastlane_cores(self, local_init, num_cores):
        """Modifies then number of fastlane cores to be used.  This
        ... would need to be issued after RPM deployment but before starting.

        Args:
            local_init (dict): fields of local init file
            num_cores (int): number of data cores to add

        Returns:
            dict: 128T local init data
        """
        try:
            local_init['cpuProperties']
        except KeyError:
            local_init['cpuProperties'] = {}
        finally:
            local_init['cpuProperties']['cores'] = num_cores
        return local_init

    def modify_t128_number_of_huge_2m(self, local_init, huge_2m):
        """Modifies then number of huge page 2M to be allocated.

        Args:
            local_init (dict): fields of local init file
            huge_2m (str): value of huge pages to be set

        Returns:
            dict: updated 128T local init file
        """
        try:
            local_init['memdomains']
        except KeyError:
            local_init['memdomains'] = [{"huge_1G": "0", "huge_2M": "2G", "name": "global"}]
        finally:
            for mem_ele in local_init['memdomains']:
                mem_ele["huge_2M"] = huge_2m
        return local_init

    def modify_t128_local_init_name(self, local_init, name):
        """Modifies node name in local init file.  This
        ... would need to be issued after RPM deployment but before starting.

        Args:
            local_init (dict): fields of local init file
            name (str): 128T node name

        Returns:
            dict: updated 128T local init file
        """
        try:
            local_init['init']
        except KeyError:
            local_init['init'] = {}
        finally:
            local_init['init']['id'] = name
        return local_init

    def check_for_t128_log_pattern(self, log_file, exp_pattern, follow_rotate=False, timeout=100):
        """tails specific log file in default T128 log folder and checks \
        for `exp_pattern` match. If match is found, retruns True, otherwise false.

        Args:
            log_file (str): log file path
            exp_pattern (str): matching value to be caught in the log file
            follow_rotate (bool): if true, the tail command will work across file rotation.
                                  if false the tail will stop if the file is rotated out from
                                  under it. (default: False)
            timeout (int, optional): how long to wait (seconds)

        Returns:
            bool: True if pattern is found in logfile, false otherwise
        """
        try:
            match = self.wait_for_t128_log_pattern(log_file, exp_pattern, follow_rotate, timeout)
        except T128EnvException as e:
            t128_env_logger.debug(e)
            return False
        return True

    def wait_for_t128_log_pattern(self, log_file, exp_pattern, follow_rotate=False, timeout=100):
        """tails specific log file in default T128 log folder and checks \
        for `exp_pattern` match or bails and raises error if timeout occurs

        Args:
            log_file (str): log file path
            exp_pattern (str): matching value to be caught in the log file
            follow_rotate (bool): if true, the tail command will work across file rotation.
                                  if false the tail will stop if the file is rotated out from
                                  under it. (default: False)
            timeout (int, optional): how long to wait (seconds)

        Returns:
            str: matching line in logFile

        Raises:
            T128EnvException: in case no match
        """
        follow_option = '-f'
        if follow_rotate is True:
            follow_option = '-F'

        cmd = 'sudo tail -n +0 {} {}'.format(follow_option,
                                             os.path.join(T128Env.T128_LOG_DIRECTORY,
                                             log_file))
        t128_env_logger.debug("Command: {}".format(cmd))
        self.CLIENT.write(cmd, add_newline=True)

        exp_patterns = [exp_pattern]
        match = None
        for i in range(timeout):
            for line in self.CLIENT.read(1).splitlines():
                present, missing_pattern = self._match_all_patterns(exp_patterns, ''.join(line))
                t128_env_logger.debug('looking for tail match in: {}'.format(line))
                if present:
                    match = line
                    break
            if match is not None:
                break
        t128_env_logger.debug('match: {}'.format(match))

        self.CLIENT.write('\x03')
        self.CLIENT.read()

        if not present:
            raise T128EnvException('Timeout waiting on T128 log {}. Missing pattern: {}'.format(
                                   log_file, missing_pattern))
        return match

    def clean_t128_users(self):
        t128_env_logger.debug('Removing 128T admin and user on ')
        self.CLIENT.execute_command('sudo userdel -r admin')
        self.CLIENT.execute_command('sudo userdel -r user')

    def enable_128tok_startup_bypass(self):
        t128_env_logger.debug('Adding 128t bypass file ')
        self.CLIENT.execute_command('sudo touch /etc/128technology/128tok_startup_bypass')

    def disable_128tok_startup_bypass(self):
        t128_env_logger.debug('remove 128tok bypass file')
        self.CLIENT.execute_command('sudo rm -f /etc/128technology/128tok_startup_bypass')

    def enable_power_saver_mode(self):
        """
        Enables the "Power Saver" Mode
        """
        temp_str = self._get_file_as_text(T128Env.T128_PM_PROCLIST_FILE)
        dict_data = dict(json.loads(temp_str))
        for line in dict_data['application']['processes']:
            if line['label'] == 'Fast Lane':
                line['args'].append("--power-saver")
        with open(TEMPORARY_JSON_FILE, 'w') as f:
            json.dump(dict_data, f, indent=4, sort_keys=True)
        self.CLIENT.put_file(TEMPORARY_JSON_FILE, T128Env.T128_PM_PROCLIST_FILE)
        os.remove(TEMPORARY_JSON_FILE)

    def install_salt_minion(self, dut_dict, host_addresses):
        """ Installs, configures, and starts the salt-minion service

        Args:
            dut_dict (dict): dut dictionary entries
            host_addresses (list): A list of IP addresses used for the salt-minion configuration file
        """
        self.prepare_device_for_salt_install(dut_dict)
        self.install_salt_minion_rpm(dut_dict)
        self.write_salt_minion_config(dut_dict, host_addresses)
        self.start_salt_minion_service()
        self.verify_salt_minion_service_is_running()

    def prepare_device_for_salt_install(self, dut_dict):
        """ Setup the salt repo and uninstall any existing salt-master
        ...  and salt-minion packages

        Args:
            dut_dict (dict): dut dictionary entries
        """
        self.uninstall_salt_master(dut_dict)
        self.uninstall_salt_minion(dut_dict)
        self.CLIENT.execute_command('rm -rf /etc/salt/pki/minion/minion_master.pub')
        self.setup_salt_repo(dut_dict)

    def uninstall_salt_master(self, dut_dict):
        """ Uninstalls the salt-master service

        Args:
            dut_dict (dict): dut dictionary entries
        """
        connection = self.create_yum_connection_to_host(dut_dict)
        connection.execute_yum_remove(SALT_MASTER)
        connection.close_connection()

    def uninstall_salt_minion(self, dut_dict):
        """ Uninstalls the salt-minion service

        Args:
            dut_dict (dict): dut dictionary entries
        """
        connection = self.create_yum_connection_to_host(dut_dict)
        connection.execute_yum_remove(SALT_MINION)
        connection.close_connection()

    def uninstall_128T(self, dut_dict):
        """ Uninstalls 128T

            == Args ==
            - dut_dict (dict) - dut dictionary entries
        """
        connection = self.create_yum_connection_to_host(dut_dict)
        connection.execute_yum_remove('128T')
        connection.close_connection()

    def setup_salt_repo(self, dut_dict):
        """ Executes the salt rpm import command and calls to create the salt repo file

        Args:
            dut_dict (dict): dut dictionary entries
        """
        self.CLIENT.execute_command(SALT_RPM_IMPORT_COMMAND)
        self.create_salt_repo_file(dut_dict)

    def create_salt_repo_file(self, dut_dict):
        """ Creates the salt repo file

        Args:
            dut_dict (dict): dut dictionary entries
        """
        connection = self.create_yum_connection_to_host(dut_dict)
        contents = get_salt_repo_contents_from_local_file()
        connection.create_yum_repo_file(SALT_REPO_FILE, '/etc/yum.repos.d/', contents)
        connection.close_connection()

    def install_salt_minion_rpm(self, dut_dict):
        """ Installs the salt minion rpm

        Args:
            dut_dict (dict): dut dictionary entries
        """
        connection = self.create_yum_connection_to_host(dut_dict)
        connection.execute_yum_install(SALT_MINION, True)
        connection.close_connection()

    def create_yum_connection_to_host(self, dut_dict):
        """ Creates a yum connection to the given dut_dict's host

        Args:
            dut_dict (dict): dut dictionary entries

        Returns:
            connection: yum host connection
        """
        connection = Yum()
        connection.connect_to_host_with_dictionary(dut_dict['host'])
        return connection

    def write_salt_minion_config(self, dut_dict, host_addresses):
        """ Writes the salt minion configuration file

        Args:
            dut_dict (dict): dut dictionary entries
            host_addresses (list): A list of IP addresses used for the salt-minion configuration file
        """
        config_dict = self.get_salt_minion_config()
        config_dict = self._write_salt_minion_config_entry(config_dict, 'master', host_addresses)
        config_dict = self._write_salt_minion_config_entry(
            config_dict, 'grains', {'node-ip' : dut_dict['host']['mgmt_address']})
        config_dict = self._write_salt_minion_config_entry(config_dict, 'log_level_logfile', 'debug')
        config_dict = self._write_salt_minion_config_entry(config_dict, 'transport', 'tcp')

        self._write_yaml_file(SALT_MINION_CONFIG_FILE, config_dict)

    def get_salt_minion_config(self):
        """ Retrieves the contents to the salt-minion configuration file

        Returns:
             a dict representing the contents of the salt-minion config file
        """
        with self.CLIENT.sftp_client.open(SALT_MINION_CONFIG_FILE, 'r') as f:
            try:
                return yaml.load(f)
            except yaml.YAMLError as error:
                raise T128EnvException(
                    'An error occurred while trying to read the {file} file. Error: {err}'.format(
                        file=SALT_MINION_CONFIG_FILE, err=error))

    def start_salt_minion_service(self):
        """
        Starts the salt-minion service
        """
        self.CLIENT.start_service('salt-minion')

    def verify_salt_minion_service_is_running(self):
        """ Verifies that the salt-minion service is running

        Raises:
            T128EnvException: occurs when the salt-minion service is not running
        """
        if not self.CLIENT.is_service_running(SALT_MINION):
            raise T128EnvException('{service} service failed to start'.format(service=SALT_MINION))

    def transfer_local_file(self, local_file, remote_file):
        """
        Transfers a local file to a remote device
        """
        self.CLIENT.put_file(local_file, remote_file)

    def _run_t128_staging(self):
        # Not working keeping here for future
        self._switch_device(T128.current_active_name)
        install_dir = os.path.join(image_dict.base_directory,
                                   image_dict.install_directory)
        self._run_command_in_background('cd ' + install_dir + '; ./' +
                                        image_dict.staging_executable)
        output_strings = []
        complete = False
        for i in range(T128.startup_timeout):
            output_strings.append(self._read_background_output(1))
            complete, missing_pattern = self._is_startup_complete(
                ''.join(output_strings))
            if complete:
                break
        t128_env_logger.debug(''.join(output_strings))
        if not complete:
            raise T128EnvException(
                'Timeout starting 128T ' + T128.current_active_name +
                ' missing pattern: ' + str(missing_pattern))

    def _match_all_patterns(self, patterns, output):
        for pattern in patterns:
            if re.search(pattern, output) is None:
                return False, pattern
        return True, None

    def _get_file_as_text(self, file):
        text, err, rc = self.CLIENT.execute_command('cat {}'.format(file))
        return text

    def _get_yin_files(self, output_dir=None):
        if output_dir is None:
            output_dir = self.image_dict['base_directory']

        yin_dir_to_be_created = self._get_local_directory(output_dir, 'yin')
        if not os.path.exists(os.path.abspath(yin_dir_to_be_created)):
            local_yin_directory = self._create_local_directory(output_dir,
                                                               'yin')
            self.CLIENT.get_directory(T128Env.T128_YIN_DIRECTORY,
                                      local_yin_directory)

    def _get_local_directory(self, output_dir, name, test_name=None):
        if test_name is None:
            local_directory_name = (name + '-' + self.image_dict['rpm_name'])
        else:
            local_directory_name = (name + '-' +
                                    self.device_dict['name'] +
                                    '-' + test_name)
        local_directory_path = os.path.join(
            output_dir, local_directory_name)

        local_directory_path = os.path.join(output_dir, local_directory_name)

        return local_directory_path

    def _create_local_directory(self, output_dir, name, test_name=None):
        local_directory_path = self._get_local_directory(output_dir,
                                                         name,
                                                         test_name)

        shutil.rmtree(local_directory_path, ignore_errors=True)
        os.makedirs(local_directory_path)

        return local_directory_path

    def _get_rpm(self, rpm_type):
        if rpm_type == 'local':
            return self._get_local_rpm()
        elif rpm_type == 'latest':
            return self._get_latest_rpm()
        else:
            return self._get_versioned_rpm(rpm_type)

    def _get_local_rpm(self):
        rpm_name = self.image_dict['rpm_name']
        rpm_path = self.image_dict['rpm_path']

        if not rpm_path:
            rpm_path = self.image_dict['base_directory']

        if not rpm_name:
            rpm_name = find_local_rpm(rpm_path)
            self.image_dict['rpm_name'] = re.sub('\.rpm$', '', rpm_name)
        else:
            rpm_name = '{}.rpm'.format(rpm_name)

        rpm = os.path.join(rpm_path, rpm_name)
        t128_env_logger.debug('Installing {}'.format(rpm))
        self._clean_old_rpm()
        self.CLIENT.put_file(rpm, tempfile.gettempdir())
        remote_rpm = os.path.join(tempfile.gettempdir(), rpm_name)

        return remote_rpm

    def _get_latest_rpm(self):
        rpm, _, _ = self.CLIENT.execute_command('yum list 128T | grep 128T')
        rpm = rpm.split()[1]
        return '128T-{}'.format(rpm)

    def _get_versioned_rpm(self, version):
        self._set_yum_repo()
        rpm_block, _, _ = self.CLIENT.execute_command(
            'yum list available 128T {} {} {} | grep {}'
            .format('--disablerepo=*', '--enablerepo=128techRelease', '--showduplicates', version))
        rpm_list = rpm_block.strip().split('\n')
        rpm = '128T-{}'.format(rpm_list[-1].split()[1])
        return rpm

    def _set_yum_repo(self):
        _, _, rc = self.CLIENT.execute_command(
            'grep \'128techRelease\'  /etc/yum.repos.d/128.repo')
        if rc != 0:
            self.CLIENT.execute_command('echo \'{}\' >> /etc/yum.repos.d/128.repo'
                                        .format(self.T128_RELEASE_REPO))

    def _clean_old_rpm(self):
        t128_env_logger.debug('Removing rpm on ')
        try:
            output, err, rc = self.CLIENT.execute_command('sudo yum -y remove 128T')
        except EOFError:
            pass
        t128_env_logger.debug(output)

    def _run_rpm_install(self, rpm, previous_conflict=''):
        t128_env_logger.debug('Installing new rpm from {}'.format(rpm))
        output, err, rc = self.CLIENT.execute_command('sudo yum -y install {}'.format(rpm))
        if rc != 0:
            t128_env_logger.debug('Error installing T128: {}. Attempting to resolve'.format(err))
            requires_line_index = [err.splitlines().index(delimiter)
                                   for delimiter in err.splitlines() if 'Requires:' in delimiter]
            conflicts_line_index = [err.splitlines().index(delimiter)
                                    for delimiter in err.splitlines() if 'conflicts' in delimiter]
            if requires_line_index:
                t128_env_logger.debug('Requires Conflict {}'.format(err))
                requires_line = err.splitlines()[requires_line_index[0]]
                if requires_line == previous_conflict:
                    raise T128EnvException(
                        'Failed to resolve dependency while installing 128T: {}'.format(
                            requires_line))
                requires_pkg = requires_line.split()
                requires_pkg = requires_pkg[1]
                # this is here due to yum bug
                self.CLIENT.execute_command('rm -f ' + requires_pkg + '*')

                self.CLIENT.execute_command('sudo yum -y remove ' + requires_pkg)
                if 'dpdk' in requires_pkg:
                    self.CLIENT.execute_command('rmmod igb_uio')
                    self.CLIENT.execute_command('rmmod rte_kni')
                self._run_rpm_install(rpm, requires_line)
            elif conflicts_line_index:
                t128_env_logger.debug('Error Conflict {}'.format(err))
                for conflict_index in conflicts_line_index:
                    conflict_line = err.splitlines()[conflict_index]
                    if conflict_line == previous_conflict:
                        raise T128EnvException(
                            'Failed to resolve conflict while install 128T: {}'.format(
                                conflict_line))
                    old_pkg = conflict_line.split()[1]
                    new_pkg = conflict_line.split()[-1]
                    self.CLIENT.execute_command('sudo yum -y remove ' + old_pkg)
                    self.CLIENT.execute_command('sudo yum -y remove ' + new_pkg)
                    old_output, old_err, old_rc = self.CLIENT.execute_command(
                        'sudo rpm --query --queryformat \"\" ' + old_pkg)
                    new_output, new_err, new_rc = self.CLIENT.execute_command(
                        'sudo rpm --query --queryformat \"\" ' + new_pkg)
                    if new_rc == 0 or old_rc == 0:
                        t128_env_logger.debug('Failed to remove conflicting package.')
                        t128_env_logger.debug('Error: {}'.format(yum_err))
                    if 'dpdk' in old_pkg:
                        # this is here due to yum bug
                        self.CLIENT.execute_command('rm -f kmod-dpdk*')

                        dpdk_output, dpdk_err, dpdk_rc = self.CLIENT.execute_command(
                            'sudo yum -y remove kmod-dpdk*')
                        t128_env_logger.debug('Removing {}'.format(dpdk_output))
                        self.CLIENT.execute_command('rmmod igb_uio')
                        self.CLIENT.execute_command('rmmod rte_kni')
                self._run_rpm_install(rpm, conflict_line)
            else:
                t128_env_logger.debug('error is : {}'.format(err))
                raise T128EnvException('unable to install 128T rpm: ' + rpm)

    def _run_rpm_upgrade(self, rpm):
        t128_env_logger.debug('Upgrading rpm to {}'.format(rpm))
        self.stop_t128()
        self.CLIENT.execute_command('sudo yum -y upgrade {}'.format(rpm), expected_rc=0)
        # self.CLIENT.execute_command('sudo yum -y upgrade {}'.format('128T'), expected_rc=0)
        self.start_t128()
        return 'complete'

    def _enable_verbose_output(self):
        current_line = 'Debug'
        try:
            new_line = self.image_dict['init_log_level']
        except KeyError:
            new_line = 'Trace'

        for file_with_path in T128Env.STARTUP_CONFIG_FILES:
            self.CLIENT.sed_string_replace(current_line, new_line, file_with_path)

    def _write_salt_minion_config_entry(self, config_dict, config_key, entry):
        if not find_key(config_key, config_dict):
            new_dict = append_to_dict(config_key, entry, config_dict)
        else:
            new_dict = rewrite_key_value(config_key, entry, config_dict)

        return new_dict

    def _write_yaml_file(self, file, file_dict):
        with self.CLIENT.sftp_client.open(file, 'w') as f:
            yaml.safe_dump(file_dict, f, default_flow_style=False)

    def copy_local_installer_to_dut(self):
        """ Copies the Installer generated from the Python build on the local
        ... system to the DUT's temp directory and sets execute permission
        ... for the user

        Returns: The file path to the Installer on the DUT
        """
        installer_path = os.path.join(
            self.image_dict['base_directory'],
            'python',
            'installer',
            'exe',
            'install128t'
        )
        remote_installer_path = os.path.join(
            tempfile.gettempdir(),
            os.path.basename(installer_path)
        )

        if not os.path.isfile(installer_path):
            raise FileNotFoundError(
                'Cannot find the Installer on the local system'
            )

        t128_env_logger.debug(
            'Copying installer (from "{}") to DUT...'.format(installer_path)
        )
        self.transfer_local_file(installer_path, tempfile.gettempdir())
        self.CLIENT.sftp_client.chmod(
            remote_installer_path,
            self.CLIENT.sftp_client.stat(remote_installer_path) | stat.S_IEXEC
        )

        return remote_installer_path


def find_local_rpm(rpm_path):
    rpm_pattern = os.path.join(rpm_path, '128T*.rpm')
    rpm_files = glob.glob(rpm_pattern)
    rpm_files.sort(key=os.path.getmtime)

    if not rpm_files:
        raise T128EnvException('no RPM in ' + rpm_path)

    rpm_file = rpm_files[-1]
    t128_env_logger.debug(os.path.basename(rpm_file))
    t128_env_logger.debug('128T deployment RPM is: {}'.format(rpm_file))
    return os.path.basename(rpm_file)


def get_salt_repo_contents_from_local_file():
    contents = get_local_file_contents(
        'tools/{repo_file}'.format(repo_file=SALT_REPO_FILE))
    return contents.replace('$', '\$')


def get_local_file_contents(file):
    with open(file) as f:
        return f.read()

def find_key(key, file_dict):
    return file_dict and key in file_dict

def rewrite_key_value(key, value, file_dict):
    if file_dict:
        for dict_key in file_dict.keys():
            if dict_key == key:
                file_dict[dict_key] = value

    return file_dict

def append_to_dict(key, value, file_dict):
    if file_dict:
        file_dict[key] = value
    else:
        file_dict = {key : value}

    return file_dict
