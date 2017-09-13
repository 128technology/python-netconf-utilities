import re

from ote_utils.remote_api import LinuxAPI
from ote_utils.ote_logger import OteLogger
from time import sleep

kvm_logger = OteLogger(__name__)

class KvmError(Exception):
    """Main exception for this module.
    """
    pass

class TimeoutException(Exception):
    """Exception raise when a timeout is exceeded.
    """
    pass

class Kvm(LinuxAPI):
    """
    Defines a class to directly interact with kvm opperations
    on a Hypervisor

    Uses a Linux connection object to run command over ssh connection

    Attributes:
        CLIENT (connection object): A Linux connection object repr a connection
        to a linux
    """

    def virsh(self, cmd, *args):
        """
        Runs a virsh command on CLIENT and returns stdout
        Args:
            cmd (str): base virsh command to run
            *args (str, optional): items to append to base cmd
            Ex. X.virsh('list','--all')

        Raises:
            KvmError: Indicates virsh command had a problem
        """
        kvm_logger.debug('virsh command: {} {}'.format(cmd, args))
        cmd = self.CLIENT._build_cmd('virsh', cmd, *args)
        stdout, stderr, rc = self.CLIENT.execute_command(cmd)
        if rc > 0:
            raise KvmError(stderr)
        stdout = stdout.splitlines()
        return stdout[:-1] if not stdout[-1] else stdout

    def clone_guest(self, image, guest, file, *args):
        """
        Clones a current image on kvm with name: guest

        Args:
            template (str): name of guest to clone
            guest (str): name of guest to be created
            image (str): path and file name of the qcow2 to create
            *args: optional start arguments
                {--force, --mac=RANDOM ,--replace}
        """
        with self.CLIENT.timeout_manager(timeout=200):
            cmd = self.CLIENT._build_cmd('virt-clone --original', image, '--name', guest, '--file', file, *args)
            kvm_logger.debug('running clone cmd: {}'.format(cmd))
            self.CLIENT.execute_command(cmd, expected_rc=0)

            # If using LVM for some reason the clone does not go to qcow2 natively.  Need to convert
            stdout, stderr, rc = self.CLIENT.execute_command('qemu-img info {}'.format(file))
            qemu_format = Kvm._parse_qemu_info(stdout)
            if qemu_format != 'qcow2':
                tmp_file = '{}.tmp'.format(file)
                self.CLIENT.execute_command('qemu-img convert -f raw {} -O qcow2 {}'.format(file, tmp_file))
                self.CLIENT.execute_command('mv -f {} {}'.format(tmp_file, file))

    def start_guest(self, guest, timeout=15):
        """
        Starts a kvm guest

        Args:
            guest (str): guest name to start
            timeout (int, optional): time for operation to complete
        """
        if 'runnning' != self.get_guest_state(guest):
            self.virsh('start', guest)
            self._verify_guest_state(guest, 'running', timeout)

    def reset_guest(self, guest, timeout=15):
        """
        Resets a kvm guest

        Args:
            guest (str): guest name to start
            timeout (int, optional): time for operation to complete
        """
        if 'runnning' != self.get_guest_state(guest):
            self.virsh('reset', guest)
            self._verify_guest_state(guest, 'running', timeout)

    def shutdown_guest(self, guest, timeout=15):
        """
        Graceful Shutdown of kvm guest

        Args:
            guest (str): guest name to shutdown
            timeout (int, optional): time for operation to complete
        """
        if 'shut off' != self.get_guest_state(guest):
            self.virsh('shutdown', guest)
            self._verify_guest_state(guest, 'shut off', timeout)

    def destroy_guest(self, guest, timeout=15):
        """
        Forceful Shutdown of kvm guest

        Args:
            guest (str): guest name to destory
            timeout (int, optional): time for operation to complete
        """
        if 'shut off' != self.get_guest_state(guest):
            self.virsh('destroy', guest)
            self._verify_guest_state(guest, 'shut off', timeout)

    def undefine_guest(self, guest, *args):
        """
        Undefines a kvm guest

        Args:
            guest (str): Description
            *args: optional arguments
               {--remove-all-storage: remove all associated storage volumes}
        """
        self.virsh('undefine', guest, *args)

    def remove_guest(self, guest):
        """
        Shutsdown and undefines a kvm guest

        Args:
            guest: guest name 'T16_DUT1'
        """
        self.destroy_guest(guest)
        self.undefine_guest(guest, '--remove-all-storage')

    def set_num_cpu_on_guest(self, guest, number, timeout=10):
        """
        Sets the number of CPUs on a guest
        * Will fail if cpu number is over limit

        Args:
            guest: guest name 'T16_DUT1'
            number (int): number of cores
        """
        self.virsh('setvcpus', guest, number)
        self.reset_guest(guest, timeout)
        self._verify_guest_state(guest, 'running', timeout)

    def change_interface_state_on_guest(self, guest, net, state='up'):
        """
        Given the domiflist as a 2D array Ex.
        Brings up or down an interface on the HyperV
        linked to the give guest
        To turn of (dpdk1, net 1) pass in int(2) for net etc.
        Net 0 is typically the mgmt interface

        Args:
            guest: guest name 'T16_DUT1'
            net (int): network list element to collect interface on 0-#interfaces
            state (str, optional): final state of network interface

        Raises:
            Exception: hit if interface state is not valid
        """
        if state not in ['up', 'down']:
            raise Exception('Invalid interface state {}'.format(state))

        domiflist = self.collect_domain_list_on_guest(guest)[net]
        self.CLIENT.execute_command('ifconfig {} {}'.format(domiflist[0], state), expected_rc=0)

    def define_xml_for_guest(self, guest, path_to_xml='/etc/libvirt/qemu/'):
        """
        Runs a virsh define on a guest's xml file

        Args:
            guest: guest name 'T16_DUT1'
            path_to_xml: Path to where the xml lives x/y/z/*.xml
        """
        self.virsh('define', '{0}{1}.xml'.format(path_to_xml, guest))

    def collect_domain_list_on_guest(self, guest):
        """
        Returns a 2D array of all domiflist info

        Ex:
            macvtap3   direct     eno1       virtio      52:54:00:d1:05:e4
            vnet9      network    T16_net1   e1000       52:54:00:f9:94:24
            vnet10     network    T16_net2   e1000       52:54:00:14:07:34
            vnet11     network    T16_net3   e1000       52:54:00:3a:92:4a

        Args:
            guest: guest name 'T16_DUT1'
        """
        domiflist = self.virsh('domiflist', guest)
        return [i.split() for i in domiflist[2:]]

    def get_vm_intf_as_list(self, guest, net):
        """return  single interface as a list object
        Args:
            guest (string): name of the vm
            net (int): index of the network interface

        Returns:
            domiflist(list): list including interface values
            Ex:
            vnet9      network    T16_net1   e1000       52:54:00:f9:94:24
        """
        kvm_logger.debug('guest is {}'.format(guest))
        domiflist = self.collect_domain_list_on_guest(guest)[net]
        return domiflist

    def get_vm_intf_name(self, guest, net):
        """return vm linux interface name
        Args:
            guest (string): vm name
            net (int): number of the network to get
        Returns:
            string: name of the interface
        """
        return self.get_vm_intf_as_list(guest, net)[0]


    def modify_guest_xml(self, find, replace, guest):
        """Run a 'sed' command on the host

        Args:
            find (TYPE): Description
            replace (TYPE): Description
            guest (TYPE): Description
        """
        cmd = '\'s/{}/{}/g\''.format(find, replace)
        file = '/etc/libvirt/qemu/{}.xml'.format(guest)
        command = self.CLIENT._build_cmd('sed', '-i', cmd, file)
        self.CLIENT.execute_command(command, expected_rc=0)

    def get_guest_state(self, guest):
        """Give the given guest state
        Args:
            guest (str): Guest name to check state of

        Returns:
            str: Current state
        """
        try:
            stdout = self.virsh('domstate {}'.format(guest))
            for state in ['shut off', 'running', 'paused', 'blocked', 'not found', 'blocking', 'crashed', 'inactive']:
                if state in stdout:
                    return state
        except KvmError:
            return 'missing'

    def check_guest_state(self, guest, state):
        """Returns bool true if guest is in 'state'
        else false

        Args:
            guest (str): Guest name to check
            state (str): State to verify

        Returns:
            bool: If current state matched `state`
        """
        cur_state = self.get_guest_state(guest)
        return True if cur_state == state else False

    def set_guest_stopped_cpu_number(self, guest, cores):
        """
        Set CPU type on guest. It is expected but not tested that the KVM
        Guest is stopped.  Does not test or mandate that the guest is running
        as Kvm::set_cpu_number_guest() does...
        Args:
            guest (str): vm to interact with
            number (int): number of cores to set
        """
        cmds=[]
        cmds.append("rm -f /tmp/" + guest + ".xml")
        cmds.append("virsh dumpxml " + guest + " > /tmp/" + guest + ".xml")
        cmds.append("cat /tmp/" + guest + ".xml")
        cmds.append("awk $'BEGIN {s=0} /^[\\t ]*<domain type=\\'kvm\\'/ {s=1}"\
                    "/^[\\t ]*<\\/domain>/ {s=0} /^[\\t ]*<vcpu.*>[0-9]+<\\/vcpu>/"\
                    "{ if (s==1) $0=\"<vcpu placement=\\'static\\'>" + cores + "<\\/vcpu>\" } {print}' "\
                    "/tmp/" + guest + ".xml > /tmp/" + guest + ".edit.xml")
        cmds.append("virsh define /tmp/" + guest + ".edit.xml")
        for i in range(len(cmds)):
            print "cmd[%d]: %s\n" % (i, cmds[i])
            build_cmd = self.CLIENT._build_cmd(cmds[i])
            self.CLIENT.execute_command(build_cmd, expected_rc=0)

    def set_guest_cpu_type(self, guest, cpu_type):
        """
        Set CPU type on guest.  It is expected but not tested that the KVM
        Guest is stopped.

        Arguments:
            guest(str):    Guest VM name
            nic_type(str): NIC type

        Exceptions?
            No validation performed of anything performed in this library.
        """
        cmds=[]
        cmds.append("rm -f /tmp/" + guest + ".xml")
        cmds.append("virsh dumpxml " + guest + " > /tmp/" + guest + ".xml")
        cmds.append("cat /tmp/" + guest + ".xml")
        cmds.append("rm -f /tmp/" + guest + ".edit.xml")
        cmds.append("sed 's/Haswell-noTSX/" + cpu_type + "/' /tmp/" + guest + ".xml > /tmp/" + guest + ".edit.xml")
        cmds.append("cat /tmp/" + guest + ".edit.xml")
        cmds.append("virsh define /tmp/" + guest + ".edit.xml")

        for i in range(len(cmds)):
            build_cmd = self.CLIENT._build_cmd(cmds[i])
            self.CLIENT.execute_command(build_cmd, expected_rc=0)

    def set_guest_nic_driver(self, guest, nic_type):
        """
        Set CPU type on guest.  It is expected but not tested that the KVM
        Guest is stopped.

        Arguments:
            guest(str):    Guest VM name
            nic_type(str): NIC type
        """
        cmds=[]
        cmds.append("rm -f /tmp/" + guest + ".xml")
        cmds.append("virsh dumpxml " + guest + " > /tmp/" + guest + ".xml")
        cmds.append("awk $'BEGIN {s=0} /^[\\t ]*<interface type=\\'network\\'/ {s=1}" \
                    "/^[\\t ]*<\\/interface>/ {s=0} /^[\\t ]*<model type=\\'\\w+\\'\\/>/" \
                    "{ if (s==1) $0=\"<model type=\\'${nic_type}\\'/>\" } {print}' " \
                    "/tmp/" + guest + ".xml > /tmp/" + guest + ".edit.xml")
        cmds.append("virsh define /tmp/" + guest + ".edit.xml")

        for i in range(len(cmds)):
            build_cmd = self.CLIENT._build_cmd(cmds[i])
            self.CLIENT.execute_command(build_cmd, expected_rc=0)

    def set_guest_memory_size(self, guest, mem_size):
         """
         Set Guest Memory Size in MB
         Arguments:
             guest(str):    Guest VM name
             mem_size(int): Memory Size (MB)
         """
         mem_in_mb = int(mem_size) * 1024
         cmds=[]
         cmds.append("rm -f /tmp/" + guest + ".xml")
         cmds.append("virsh dumpxml " + guest + " > /tmp/" + guest + ".xml")
         cmds.append("cat /tmp/" + guest + ".xml")
         cmds.append("awk $'BEGIN {s=0} /<domain/ {s=1}" \
                     "/^[\\t ]*<\\/domain>/ {s=0}" \
                     "/^[\\t ]*<memory unit=\\'\\w+\\'>[0-9]+<\\/memory>/" \
                     "{ if (s==1) $0=\"<memory unit=\\'KiB\\'>" + str(mem_in_mb) + "<\\/memory>\" }" \
                     "/^[\\t ]*<currentMemory unit=\\'\\w+\\'>[0-9]+<\\/currentMemory>/" \
                     "{ if (s==1) $0=\"<currentMemory unit=\\'KiB\\'>" + str(mem_in_mb) + "<\\/currentMemory>\" }" \
                     "{print}' /tmp/" + guest + ".xml > /tmp/" + guest + ".edit.xml")
         cmds.append("cat /tmp/" + guest + ".edit.xml")
         cmds.append("virsh define /tmp/" + guest + ".edit.xml")

         for i in range(len(cmds)):
             build_cmd = self.CLIENT._build_cmd(cmds[i])
             self.CLIENT.execute_command(build_cmd, expected_rc=0)


    def _verify_guest_state(self, guest, desired_state, timeout):
        attempts = timeout/1
        for attempt in range(attempts):
            current_state = self.get_guest_state(guest)
            if desired_state == current_state: return
            sleep(1)
        raise TimeoutException('State:\'{}\' not reached in {} sec'.format(desired_state,timeout))

    @staticmethod
    def _parse_qemu_info(info):
        """
        Parses the output from "qemu-img info"
        Args:
        tmp_string:     The output from "qemu-img info"
        return:         The Filesystem type found in the tmp_string
        """
        qemu_format = None
        for line in info.splitlines():
            matches = re.match(r'file format: (\S+)', line)
            if matches is not None:
                return matches.group(1)
        return qemu_format
