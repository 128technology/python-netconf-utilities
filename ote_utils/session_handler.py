import time

from ote_restlib.rest_client import RestClient
from ncclient import manager, operations, NCClientError
from ncclient.operations.errors import TimeoutExpiredError
from ote_utils.netconfutils import rpc
from ote_utils.ote_logger import OteLogger

logger = OteLogger(__name__)

class SessionHandler(object):    
    def __init__(self, nc_conn, update_timout_window, active_timout_dip_threshold):
        self.nc_conn = nc_conn
        self.update_timout_window = update_timout_window
        self.active_timout_dip_threshold = active_timout_dip_threshold
        self.active_nodes = []

    def compare_states(self, expected_active_nodes):
        """Compares list of nodes with active sessions to the expected active nodes

        Args:
            expected_active_nodes - list of nodes expected to have active sessions

        Returns:
            bool - True if the session is active on the expected nodes
        """
        return expected_active_nodes == self.active_nodes
    
    def find_flow(self, flows, session_tuple):
        """Finds a flow in a list of flows that matches the filters

        Args:
            flows - list of flows
            session_tuple - tuple of src ip, dest ip, src port, dest port, protocol
        Returns:
            Session - a Session object generated from the found flow
        """
        matched_flow = None
        for flow in flows:
            matches = [kw for kw in session_tuple if kw in flow and str(session_tuple[kw]) in flow[kw]]
            if len(matches) == len(session_tuple):
                matched_flow = Session(flow)
        return matched_flow
    
    def track_session(self, session, router_node_host_tuples):
        """Finds all nodes with an active session

        Args:
            session - a Session object that abstracts the session to be tracked
            router_node_host_tuples - a tuple of the format:
                [
                    {'dut': <dut-name>, 'node': <dut's-node-name>, 'router': <dut's-router-name>, 'host': <dut's-host-address>},
                    ...
                ]
        Returns:
            array - a list of all nodes with an active session
        """
        self.active_nodes = []
        for router_node_host_dict in router_node_host_tuples:
            if self._active_session_exists(router_node_host_dict['host'],
                                          router_node_host_dict['router'], 
                                          router_node_host_dict['node'], 
                                          'admin', 
                                          '128Tadmin', 
                                          session):
                self.active_nodes.append(router_node_host_dict['node'])
        return self.active_nodes

    def _active_session_exists(self, host, router, node, username, password, session):
        session_exists = False 
        response = self._make_flow_request(host, router, node, username, password, session.session_id)
        if len(response) > 0:
            session_active = True
            for flow in response:
                session = Session(flow)
                session_active = session_active and self._session_is_active(session, host, router, node, username, password)
            return session_active
        return False

    def _make_flow_request(self, host, router, node, username, password, session_id):
        logger.debug('make flow request for session-id: {}'.format(session_id))
        rest_conn = RestClient()
        rest_conn.connect(host, username, password, port=443)        
        endpoint = '/api/v1/router/{}/node/{}/traffic/flows?filter=""~"{}"'.format(router, node, session_id)
        logger.debug('endpoint: {}'.format(endpoint))
        response = rest_conn.make_request('get', endpoint)
        logger.debug('Test no flows response: {}'.format(response))
        return response

    def _session_is_active(self, session, host, router, node, username, password):
        # Session timout is polled and updated every 1 sec. 
        # To ensure we get an updated session timout, we wait a default of at least 3 sec
        time.sleep(self.update_timout_window)
        flows = self._make_flow_request(host, router, node, username, password, session.session_id)
        update_flow = [flow for flow in flows if flow['devicePort'] == session.device_port][0]
        updated_session = Session(update_flow)

        if updated_session.timout > session.timout:
            return True
        else:
            return (session.timout - updated_session.timout) < self.active_timout_dip_threshold


class Session(object):

    def __init__(self, flow):
        if 'session-uuid' in flow:
            # parse flow retreived via netconf
            self.session_id = flow['session-uuid'][0]
            self.src_ip = flow['source-ip'][0]
            self.dest_ip = flow['dest-ip'][0]
            self.src_port = flow['source-port'][0]
            self.dest_port = flow['dest-port'][0]
            self.device_port = flow['device-port'][0]
            self.protocol = flow['protocol'][0]
            self.timout = flow['inactivity-timeout'][0]
            self.uptime = flow['start-time'][0]
        else:
            # parse flow retreived via rest API
            self.session_id = flow['sessionUuid']
            self.src_ip = flow['sourceIp']
            self.dest_ip = flow['destIp']
            self.src_port = flow['sourcePort']
            self.dest_port = flow['destPort']
            self.device_port = flow['devicePort']
            self.protocol = flow['protocol']
            self.timout = flow['inactivityTimeout']
            self.uptime = flow['startTime']
    
    def __str__(self):
        ret = 'Session ID: {}\n'.format(self.session_id)
        ret += 'Source IP: {}\n'.format(self.src_ip)
        ret += 'Destination IP: {}\n'.format(self.dest_ip)
        ret += 'Source Port: {}\n'.format(self.src_port)
        ret += 'Destination Port: {}\n'.format(self.dest_port)
        ret += 'Device Port: {}\n'.format(self.device_port)
        ret += 'Protocol: {}\n'.format(self.protocol)
        ret += 'Timout: {}\n'.format(self.timout)
        ret += 'Uptime: {}\n'.format(self.uptime)
        return ret

