"""Summary

Attributes:
    formatter (TYPE): Description
    handler (TYPE): Description
    logger (TYPE): Description
"""
import json
import os.path
import re
import time

from ote_utils.remote_api import LinuxAPI
from ote_utils.ote_logger import OteLogger

logger = OteLogger(__name__)


class GdbException(Exception):
    """
    Gdb Exception
    """

    pass


class Gdb(LinuxAPI):
    """Api to allow running gdb over ssh connection and report stack

    Attributes:
        command_timeout (TYPE): timeout value for gdb command seconds
        CORE_DIR (str): default value for core file directory
        core_exec_map (dict): store executable per core file
        core_files (list): all core files in core folder
        CORE_PATTERNS (list): catch incomplete and actual cores
        DEFAULT_COMMAND_TIMEOUT (int): gloabl static timeout
        DEFAULT_CORE_TIMEOUT (int): time to wait for incomplete cores to finish
        image_dict (dict): stores paths for where the binary location is
        INCOMPLETE_CORE_PATTERN (str): incomplete core pattern
    """

    CORE_PATTERNS = ["core.*", ".#core"]

    INCOMPLETE_CORE_PATTERN = ".#core.*"

    CORE_DIR = "/var/lib/systemd/coredump"
    DEFAULT_CORE_TIMEOUT = 180
    DEFAULT_COMMAND_TIMEOUT = 5
    command_timeout = DEFAULT_COMMAND_TIMEOUT
    core_files = []
    core_exec_map = {}

    def __init__(self, device_dict):
        """init

        Args:
            device_dict (dict): pupulate image_dict for binary path
        """
        self.host_dict = device_dict["host"]
        self.image_dict = device_dict["image"]
        self.host = self.host_dict["address"]
        self.username = self.host_dict["username"]
        self.password = self.host_dict["password"]

    def set_gdb_command_timeout(self, timeout):
        """Set the timeout value between commands to GDB.

        Args:
            timeout (int): seconds

        Returns:
            command_timeout(int): seconds
        """
        Gdb.command_timeout = timeout

    def start_gdb_with_core_file(self, core_file=None):
        """Prepares GDB for debugging a core file

        Args:
            core_file (None, optional): specifies
        the core file to be debugged.  If unspecified, robot will search for
        one in common locations.

        Returns:
            core_files(list): all core files in core folder
        """
        Gdb.core_file = core_file
        logger.debug("check core files")

        if core_file is None:
            Gdb.core_files = self._find_core_files()
        else:
            Gdb.core_files.append(core_file)

        for core_file in Gdb.core_files:
            logger.debug("core file in loop " + "".join(core_file))
            stripped_core_file = self._prepare_core_file(core_file)
            logger.debug("Core file " + stripped_core_file)
            executable_file = self._get_executable_from_core(
                stripped_core_file, self.image_dict["install_directory"]
            )
            Gdb.core_exec_map[stripped_core_file] = executable_file
            logger.debug("Executable: " + executable_file)

    def send_command_to_gdb(self, command="thread apply all bt"):
        """Send a debugger command to GDB and return the output as a string.

        Args:
            command (str, optional): gdb command to be executed

        """
        self.CLIENT.timeout_manager(Gdb.command_timeout)
        output_strings = []
        for stripped_core_file, executable_file in Gdb.core_exec_map.items():
            command_string = "sudo gdb -quiet -batch -ex '{cmd}' {exe} " "{core}".format(
                cmd=command, exe=executable_file, core=stripped_core_file
            )
            output, err, rc = self.CLIENT.execute_command(command_string)
            output_strings.append(output)
        logger.debug("gdb output " + "".join(output_strings))
        return output_strings

    def clean_core_files(self):
        """Remove all core files in default core folder

        """
        if self._find_core_files():
            for core_file_pattern in Gdb.CORE_PATTERNS:
                core_pattern = os.path.join(Gdb.CORE_DIR, core_file_pattern)
                logger.debug("sudo rm " + core_pattern)
                self.CLIENT.execute_command("sudo rm " + core_pattern)

    def has_gdb_core_files(self):
        """Check if any cores were found, to be run
        post start_gdb_with_core_file

        Returns:
            int: number of cores
        """
        return len(Gdb.core_files) != 0

    def get_gdb_core_files(self):
        """get the list of core files

        Returns:
            list: core files
        """
        return Gdb.core_files

    def _get_executable_from_core(self, core_file, install_dir):
        command_string = "sudo readelf -n {core} | grep {dir}".format(
            core=core_file, dir=install_dir
        )
        output, rc, err = self.CLIENT.execute_command(command_string)
        files = output.splitlines()
        if not files:
            raise GdbException("Could not find executable from core file for ")
        return files[0]

    def _find_core_files(self):
        core_files = []
        incomplete_core_pattern = os.path.join(Gdb.CORE_DIR, Gdb.INCOMPLETE_CORE_PATTERN)
        output, err, rc = self.CLIENT.execute_command("ls -t " + incomplete_core_pattern)

        if output:
            logger.debug("core in progress waiting " + str(Gdb.DEFAULT_CORE_TIMEOUT) + " seconds")
            time.sleep(Gdb.DEFAULT_CORE_TIMEOUT)

        for core_file_pattern in Gdb.CORE_PATTERNS:
            core_pattern = os.path.join(Gdb.CORE_DIR, core_file_pattern)
            output, err, rc = self.CLIENT.execute_command("ls -t " + core_pattern)
            files = output.splitlines()
            if Gdb.INCOMPLETE_CORE_PATTERN == core_file_pattern and files:
                raise GdbException(
                    "core incomplete something went wrong or increase timeout from: "
                    + str(Gdb.DEFAULT_CORE_TIMEOUT)
                    + " seconds"
                )
            else:
                core_files += files

        output_all, err, rc = self.CLIENT.execute_command("find " + Gdb.CORE_DIR + " -type f")
        all_files = output_all.splitlines()
        unknown_files = set(all_files) - set(core_files)
        if len(all_files) != len(core_files):
            raise GdbException("Unknown files found in coredump folder " + str(unknown_files))
        return core_files

    def _prepare_core_file(self, core_file):
        root, extension = os.path.splitext(core_file)
        return_name = core_file
        if extension == ".xz":
            self.CLIENT.execute_command("sudo xz -d " + core_file)
            return_name = root

        return return_name
