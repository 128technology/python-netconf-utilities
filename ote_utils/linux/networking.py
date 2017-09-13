from ote_utils.remote_api import LinuxAPI
from ote_utils.ote_logger import OteLogger

logger = OteLogger(__name__)

class NetworkingException(Exception):
    """Exception for Networkingclass"""
    pass

class Networking(LinuxAPI):
    def bring_down_interface(self, intf):
        """
        Administratively downs interface
        Args:
            intf: interface to bring down
        """
        self.CLIENT.execute_command('ifdown {}'.format(intf))

    def bring_up_interface(self, intf, address=None):
        """
        Administratively ups interface
        Args:
            intf: interface to bring up
            address (optional): address/netmask to assign to interface
        """
        if address is not None:
            self.configure_interface_ip(intf, address)
        else:
            cmd = 'ifup {}'.format(intf)
            self.CLIENT.execute_command(cmd)

    def configure_interface_ip(self, intf, address):
        """
        Configures address on given interfaces
        Args:
            intf: interface to configure
            address: address/netmask to assign to interface
        """
        cmd = 'ifconfig {} {}'.format(intf, address)
        self.CLIENT.execute_command(cmd)

    def configure_interface_vlan(self, intf, vlan, address):
        """
        Creates VLAN with given address on an interface
        Args:
            intf: base interface on which to create vlan interface
            vlan: vlan id
            address: address/netmask to assign to new vlan interface
        """
        cmd = 'ip link add link {} name {}.{} type vlan id {}'.format(intf, intf, vlan, vlan)
        self.CLIENT.execute_command(cmd)
        self.configure_interface_ip('{}.{}'.format(intf, vlan), address)

    def enable_forwarding(self):
        """
        Enables IPV4 IP Forwarding
        """
        self.CLIENT.execute_command('sysctl -w net.ipv4.ip_forward=1')

    def disable_forwarding(self):
        """
        Disables IPV4 IP Forwarding
        """
        self.CLIENT.execute_command('sysctl -w net.ipv4.ip_forward=0')

    def enable_send_redirects(self, intf='*'):
        """
        Enables IPV4 Send Redirects on given interfaces
        Args:
            intf: interface to enable redirects on.  Defaults to * (all)
        """
        self.CLIENT.execute_command('echo 1 > /proc/sys/net/ipv4/conf/{}/send_redirects'.format(intf))

    def disable_send_redirects(self, intf='*'):
        """
        Disables IPV4 Send Redirects on given interfaces
        Args:
            intf: interface to disable redirects on.  Defaults to * (all)
        """
        self.CLIENT.execute_command('echo 0 > /proc/sys/net/ipv4/conf/{}/send_redirects'.format(intf))

    def add_route(self, network, interface, gateway=None):
        """
        Add ip static route
        Args:
            network: destination network address/subnet
            interface: interface to use to reach next hop
            gateway: (optional) next hop gateway
        """
        self._update_route('add', network, interface, gateway)

    def del_route(self, network, interface, gateway=None):
        """
        Delete ip static route
        Args:
            network: destination network address/subnet
            interface: interface to use to reach next hop
            gateway: (optional) next hop gateway
        """
        self._update_route('del', network, interface, gateway)

    def issue_ip_tables_rule(self, rule):
        """
        Issues iptables command given the options defined by rule
        Args:
            rule: argument string to pass to iptables
        """
        self.CLIENT.execute_command('iptables {}'.format(rule))
        self._bounce_forwarding()

    def flush_ip_tables(self):
        """
        Flushes ip tables
        """
        self.CLIENT.execute_command('iptables --flush')
        self._bounce_forwarding()

    def configure_pppoe_server(self, details):
        """
        Configures PPPoE Server Secrets File
        Args:
            details: dictionary in the following format
            {'USERNAME':<string> pppoe user
             'PASSWORD':<string> pppoe user's password
             'CLIENT_ADDRESS': <string> address to assign to client
             'AUTH_MODE': <string> pap or chap authentication}
        """
        self.CLIENT.execute_command('echo \"{} * {} {}\" > /etc/ppp/chap-secrets'.format(
            details['USERNAME'], details['PASSWORD'], details['CLIENT_ADDRESS']))
        self.CLIENT.execute_command('echo \"{} * {} {}\" > /etc/ppp/pap-secrets'.format(
            details['USERNAME'], details['PASSWORD'], details['CLIENT_ADDRESS']))
        self._configure_pppoe_auth_mode(details['AUTH_MODE'])

    def unconfigure_pppoe_server(self):
        """
        'Unconfigures' PPPoE Server by simply commenting out all lines in the pppoe
        secrets files and re-enable login.
        """
        self.CLIENT.execute_command('sed -i \'s/^#login/login/\' /etc/ppp/pppoe-server-options')
        self.CLIENT.execute_command('sed -i \'s/^/#/\' /etc/ppp/chap-secrets')
        self.CLIENT.execute_command('sed -i \'s/^/#/\' /etc/ppp/pap-secrets')

    def start_pppoe_server(self, details):
        """
        Starts PPPoE server on target interface with server address
        Args:
            details: dictionary in the following format
            {'TARGET_INTF':<string> pppoe target interface
             'SERVER_ADDRESS':<string> pppoe interface address}
        """
        self.CLIENT.execute_command('pppoe-server -I {} -L {} &'.format(
            details['TARGET_INTF'], details['SERVER_ADDRESS']))

    def stop_pppoe_server(self):
        """
        Stops all instances of pppoe-server process
        """
        self.CLIENT.kill_linux_process('pppoe-server')

    def close(self):
        """
        Closes connection to host
        """
        self.CLIENT.close()

    def _update_route(self, cmd, network, interface, gw):
        route_cmd = 'ip route {} {} dev {}'.format(cmd, network, interface)
        if gw is not None:
            route_cmd += ' via {}'.format(gw)

        self.CLIENT.execute_command(route_cmd)

    def _bounce_forwarding(self):
        #Used to disable and re-enable forwarding (if already enabled) to mitigate
        #linux bug where iptable rules aren't taken into effect until forwarding is bounced
        stdout, stderr, rc = self.CLIENT.execute_command('cat /proc/sys/net/ipv4/ip_forward')
        if stdout == '1':
            self.disable_forwarding()
            self.enable_forwarding()

    def _configure_pppoe_auth_mode(self, auth_mode):
        self.CLIENT.execute_command('sed -i \'s/^login/#login/\' /etc/ppp/pppoe-server-options')
        if auth_mode == 'chap':
            self.CLIENT.execute_command('sed -i \'s/^require-pap/require-chap/\' /etc/ppp/pppoe-server-options')
        elif auth_mode == 'pap':
            self.CLIENT.execute_command('sed -i \'s/^require-chap/require-pap/\' /etc/ppp/pppoe-server-options')
        else:
            raise NetworkingException('Unsupported PPPoE Authentication Mode: {}'.format(auth_mode))