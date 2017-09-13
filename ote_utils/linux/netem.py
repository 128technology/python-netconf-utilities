from ote_utils.remote_api import LinuxAPI
from ote_utils.ote_logger import OteLogger

netem_logger = OteLogger(__name__)


class NetemError(Exception):
    """Main exception for Netem module.
    """
    pass

class TimeoutException(Exception):
    """Exception raise when a timeout is exceeded.
    """
    pass

class Netem(LinuxAPI):
    """
    Defines a class to directly interact with Netem traffic control module

    Uses a Linux connection object to run command over ssh connection

    Attributes:
        to a linux

    Deleted Attributes:
        CLIENT (connection object): A Linux connection object repr a connection
    """
    def set_interface_packet_drop(self, int_name, drop_percent):
        """Set percentage of packets to be dropped on specific interface

        Args:
            int_name (string): linux name of the interface
            drop_percent (string): percent should be in range 0-100
        """
        self._send_netem_command('add', int_name, 'loss', drop_percent)

    def set_interface_packet_corruption(self, int_name, corrupt_percent):
        """Set percentage of packets to be corrupted on specific interface

        Args:
            int_name (string): linux name of the interface
            corrupt_percent (string): percent should be in range 0-100
        """
        self._send_netem_command('add', int_name, 'corrupt', corrupt_percent)

    def set_interface_packet_delay(self, int_name, delay, variance=None):
        """Set delay to the packets outgoing on specific interface

        Args:
            int_name (string): linux name of the interface
            delay (string): should be in the form of 100ms
            variance (None, optional): add random variation to delay in form 10ms

        """
        if variance:
            self._send_netem_command('add', int_name, 'delay', delay, variance)
        else:
            self._send_netem_command('add', int_name, 'delay', delay)

    def clear_interface_packet_drop(self, int_name, drop_percent):
        """clear drop settings on the interface

        Args:
            int_name (string): linux name of the interface
            drop_percent (string): percent should be in range 0-100

        """
        self._send_netem_command('del', int_name, 'loss', drop_percent)

    def clear_interface_packet_corruption(self, int_name, corrupt_percent):
        """clear corruption settings on the interface

        Args:
            int_name (string): linux name of the interface
            corrupt_percent (string): percent should be in range 0-100

        """
        self._send_netem_command('del', int_name, 'corrupt', corrupt_percent)

    def clear_interface_packet_delay(self, int_name, delay, variance=None):
        """clear delay on the interface

        Args:
            int_name (string): linux name of the interface
            delay (string): should be in the form of 100ms
            variance (None, optional): add random variation to delay in form 10ms

        """
        if variance:
            self._send_netem_command('del', int_name, 'delay', delay, variance)
        else:
            self._send_netem_command('del', int_name, 'delay', delay)

    def clear_interface_netem_settings(self, intf_name):
        """clear all netem setting on the interface

        Args:
            int_name (string): linux name of the interface

        """
        output, err, rc = self.CLIENT.execute_command(
            'tc qdisc del dev {} root'.format(intf_name))
        netem_logger.debug('output of clear command {}'.format(output))

    def _send_netem_command(self, mode, intf_name, command, value=' '):
        netem_logger.debug('input: tc qdisc {} dev {} root netem {} {}'.format(mode, intf_name, command, value))
        output, err, rc = self.CLIENT.execute_command(
            'tc qdisc {} dev {} root netem {} {}'.format(mode, intf_name, command, value))
        netem_logger.debug('output of send command {} {} {}'.format(output, err, rc))
