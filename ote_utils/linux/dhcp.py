import iscconf

from ote_utils.remote_api import LinuxAPI
from ote_utils.ote_logger import OteLogger

class DhcpException(Exception):
    '''
    Exception class for dhcp errors
    '''
    pass

class Dhcp(LinuxAPI):
    """
    Uses a linux connection object to collect
    dhcp.conf files, write dhcp.conf files and interact
    with the isc-dhcp-server service

    host = {'address':'172.17.19.101', 'username':'root','password':'pswrd'}
    td = Dhcp(host)
    dhcp_dict = td.read_dhcp_conf()
    server1 = td.create_server_block()
    server2 = td.create_server_block('172.16.2.0', '255.255.255.0', '172.16.2.1 172.16.2.1', '172.16.2.254', '255.255.255.0')
    td.write_dhcp_conf(td.create_dhcp_conf(72, 60, server1, server2))
    td.put_dhcp_conf()
    td.set_dhcp_state('restart')
    """
    _conf_file = '/etc/dhcp/dhcpd.conf'
    _leases_file = '/var/lib/dhcp/dhcpd.leases'

    def get_dhcp_conf(self, file=_conf_file):
        """Collects the remote dhcp.conf from the host
        Args:
            file (str, optional): Path to dhcp.conf
        """
        self.CLIENT.get_file(file)

    def put_dhcp_conf(self, src_file='dhcpd.conf', dest_file=_conf_file):
        """Moves a local dhcp config to the remote client

        Args:
            src_file (str, optional): local file to move
            dest_file (str, optional): path/file to moce the local file
        """
        self.CLIENT.put_file(src_file, dest_file)

    def read_dhcp_conf(self, file='dhcpd.conf'):
        """ Reads a local dhcp.conf file and converts into
            a useable dict
        Args:
            file (str, optional): local file to convert

        Returns:
            dict: Nested dictonary that holds conf info
        """
        try:
            with open(file, 'r') as f:
                return self._join_sets(iscconf.parse(f.read()))
        except iscconf.parser.SyntaxError as ex:
            raise DhcpException('Dhcp configuration file is invalid: {}'.format(ex))

    def write_dhcp_conf(self, dhcp_dict, output_file='dhcpd.conf'):
        """ Writes lines of dhcp_dict to a file
        Args:
            dhcp_dict (TYPE): Dictionary generated through create_dhcp_conf
            ofile (str, optional): name of file to save config to
        """
        file = open(output_file, 'w')
        for line in self._create_conf_list(dhcp_dict):
            file.write(line)
        file.close()

    def create_server_block(self, subnet='172.16.1.0',
                                  netmask='255.255.255.0',
                                  range='172.16.1.1 172.16.1.1',
                                  routers='172.16.1.254'):
        """Given some basic paramters, creates a dict that
        represents a basic dhcp server config

        Args:
            subnet (str, optional): Subnet server acts on
            netmask (str, optional): Netmask of the server's subnet
            range (str, optional): Begining and End IP of ip pool
            routers (str, optional): IP of dhcp server

        Returns:
            dict: representation of a dhcp server in the config file
        """
        server_dict = {}
        server_dict['subnet {} netmask {}'.format(subnet, netmask)] = \
                    {'range': range,
                     'option routers': routers,
                     'option subnet-mask': netmask}

        return server_dict

    def create_dhcp_conf(self, mlt, dlt, *server_blocks):
        """Combines dhcp conf attributes into basic dhcp config
        Args:
            mlt (int): Max Lease Time
            dlt (int): Default Lease Time
            *server_blocks: dictionaries that represent server blocks

        Returns:
            dict: full dictionary representing minimal dhcp config
        """
        dhcp_conf={'ddns-update-style': 'none',
                   'max-lease-time': mlt,
                   'default-lease-time': dlt,
                   'log-facility': 'local7'}
        for block in server_blocks:
            dhcp_conf.update(block)
        return dhcp_conf

    def start_dhcp_server(self):
        """Starts the dhcp server
            on client
        """
        self.CLIENT.execute_command('service isc-dhcp-server start', expected_rc=0)

    def stop_dhcp_server(self):
        """Stops the dhcp server
            on client
        """
        self.CLIENT.execute_command('service isc-dhcp-server stop', expected_rc=0)

    def restart_dhcp_server(self):
        """Restarts the dhcp server
            on client
        """
        self.CLIENT.execute_command('rm -rf {}'.format(self._leases_file), expected_rc=0)
        self.CLIENT.execute_command('service isc-dhcp-server restart', expected_rc=0)

    def set_interface_ip(self, interface, ip, netmask='255.255.255.0'):
        """Set a given interface to a given ip

        Args:
            interface (TYPE): Description
            ip (TYPE): Description
        """
        self.CLIENT.execute_command('ifconfig {} {} netmask {}'.format(interface, ip, netmask))

    def get_leases_dict(self, num_leases):
        """Get the most recent leases from dhcp server

        Args:
            num_leases (int): How many leases to return
        """
        leases_command = 'tac {} | grep -m {} -B 9  "lease" | tac'.format(self._leases_file, num_leases)
        ethernet_key = 'hardware ethernet'
        leases_dict = {}

        contents, _, _ = self.CLIENT.execute_command(leases_command)
        lease_strings = contents.split('lease')[1:]
        for lease in lease_strings:
            ip = lease.split('{')[0].rstrip().lstrip()
            for field in lease.split('\n'):
                index = field.find(ethernet_key)
                if index != -1:
                    mac = field[index + len(ethernet_key):].lstrip().rstrip()[:-1]
                    leases_dict[mac] = ip
        return leases_dict

    def _create_conf_list(self, dhcp_dict):
        output = []
        for key, value in dhcp_dict.iteritems():
            if type(value) != dict:
                output.append(('{} {};').format(key, value))
                output.append('\n')
            else:
                output.append(('{} {{\n\t{}}}\n').format(key, '\t'.join(self._create_conf_list(value))))
        return output

    def _join_sets(self, dhcp_dict):
        for key in dhcp_dict:
            if type(dhcp_dict[key]) == dict:
                dhcp_dict[key] = self._join_sets(dhcp_dict[key])
            if type(key) == tuple:
                dhcp_dict[' '.join(key)] = dhcp_dict.pop(key)
        return dhcp_dict
