#!/usr/bin/python
#!/usr/bin/env python
# NOTE: ^^^^ Make sure to use 'env python' when using virtual environments
# otherwise you will likely use the wrong version of python which won't
# have the right paths setup and nothing will work
# -----------------------------------------------------------------------------
from __future__ import print_function
import os
from ote_utils.linux import gdb
from time import sleep


total_passed = 0
total_failed = 0


def test(msg):
    print('\n-----\nTest: {}\n-----'.format(msg))


def test_pass(msg=''):
    global total_passed
    total_passed += 1
    if msg != '':
        msg = ' : ' + msg
    print('Test: PASS {}'.format(msg))


def test_fail(msg=''):
    global total_failed
    total_failed += 1
    if msg != '':
        msg = ' : ' + msg
    print('Test: FAIL {}'.format(msg))


def test_summary():
    global total_passed
    global total_failed
    print('\n-----------------[ Unittest summary: ]-----------------')
    print('Tests Passed: {}'.format(total_passed))
    print('Tests Failed: {}'.format(total_failed))
    print('-------------------')

image_dict = {'type' : 'deploy',
                'base_directory' : '/Users/dcosic/repos/second/i95/build',
                'install_directory' : '/usr/bin',
                'sh_key_file' : 'pdc_ssh_key',
                'rpm_name' : '',
                'rpm_path' : '',
                'fastlane_cores' : 4,
                'init_log_level' : 'Debug',
                'huge_2m' : '2G'}

host_dict = {'name' : 'localhost',
                'address' : 'localhost',
                'mgmt_address' : 'localhost',
                'username' : 'root',
                'password' : 'exit33'}

device_dict ={'name' : 'local', 'type' : 'vm', 'host' : host_dict, 'image' : image_dict }

print("Testing python ssh linux client")
print("-------------------------------")
alias = 'localhost'
host = '127.0.0.1'
user = os.environ['USER']
keyfile = '/Users/' + os.environ['USER'] + '/.ssh/id_rsa.pub'
logfile = '/tmp/test-ote_sshlib_clients.gdb.log'

test('Creating Linux Object')
# note: each SSHClient has an sftp and shell component
#       so there is no need to spawn a new shell or sftp client
#       unless you need a separate instance to the same host
gdb = gdb.Gdb(device_dict)
gdb.connect_to_host(host, 'root', 'exit33')

# print('\n{}'.format(gdb.config))
gdb.start_gdb_with_core_file()
test_pass()

# test('Enabling logging and logging in to host')
# local.enable_logging(logfile)
# local.login_with_public_key(user, keyfile, None)
gdb.send_command_to_gdb()
test_pass()
cores = gdb.has_gdb_core_files()
if cores is True:
    test_pass()
else:
    test_fail()

core_files = gdb.get_gdb_core_files()
print('corefiles: ' + str(core_files))
gdb.set_gdb_command_timeout(1)
gdb.clean_core_files()
test_pass()
# test('Check for running process')
# if local.is_process_running('systemd') is True:
#     test_pass('Systemd is running')
# else:
#     test_fail('Systemd is not running')


test_summary()
