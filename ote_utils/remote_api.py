from ote_sshlib_clients import linux
from ote_sshlib import SSHClient


class RemoteAPI(object):
    def __init__(self):
        self.CLIENT = None

    def connect_to_host(self, address, username, password, **args):
        """
        Connects to host and logs in
        Args:
            address: Host IP
            username: User to login as
            password: Password for user
            **args: catch all for alternate dict keyowrds from `connect_to_host_with_dictionary`
        """
        if hasattr(self, 'CLIENT') and self.CLIENT is not None:
            raise RemoteAPIException('Client is already connected.  Close connection before calling connect again.')

        if isinstance(self, LinuxAPI):
            self.CLIENT = linux.Linux(address)
        elif isinstance(self, SSHClientAPI):
            self.CLIENT = SSHClient(address)

        self.CLIENT.login(username, password)

    def connect_to_host_with_dictionary(self, host_details):
        """
        Connects and logs into host with details in 'host_details'

        Args:
            host_details: dictionary with host details
                          Format:
                          {'address':'<host_ip>',
                           'username':'<username>',
                           'password':'<password>'}

        Returns: None
        """
        self.connect_to_host(**host_details)

    def close_connection(self):
        """
        Closes connection.

        Returns: None

        """
        if hasattr(self, 'CLIENT') and self.CLIENT is not None:
            self.CLIENT.close()
        self.CLIENT = None


class RemoteAPIException(BaseException):
    pass


class LinuxAPI(RemoteAPI):
    pass


class SSHClientAPI(RemoteAPI):
    pass