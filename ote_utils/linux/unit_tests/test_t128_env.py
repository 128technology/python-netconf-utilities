#!/usr/bin/python
#!/usr/bin/env python
# NOTE: ^^^^ Make sure to use 'env python' when using virtual environments
# otherwise you will likely use the wrong version of python which won't
# have the right paths setup and nothing will work
# -----------------------------------------------------------------------------
from __future__ import print_function
import os
from ote_utils.ote_logger import OteLogger
from ote_utils.linux import t128_env
from time import sleep


total_passed = 0
total_failed = 0
OteLogger.set_global_loglevel('DEBUG')

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


print("Testing python t128_env client")
print("-------------------------------")
alias = 'localhost'
host = '127.0.0.1'
user = os.environ['USER']
keyfile = '/Users/' + os.environ['USER'] + '/.ssh/id_rsa.pub'
logfile = '/tmp/test-ote_sshlib_clients.t128_env_ssh.log'


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

test('Creating T128 Object')

local = t128_env.T128Env(device_dict)

test_pass()

test('Enabling logging and logging in to host')
local.connect_to_host(host, 'root', 'exit33')

test_pass()


test('deploy 128T rpm')
local.deploy_t128()
test_pass()

test('manipulate global.init')
node_address_info = {'controls' : [{'election_port': '2223', 'quorum_port': '2222', 'name': 'test1', 'address': '127.0.0.1'}], 'conductors' : [], 'router_name' : 'Fabric128'}

local.generate_global_init_file(node_address_info)
test_pass()

test('change local init node name')
local.set_t128_local_node_name('linecard-test', 'test1')
test_pass()

test('modify local init cores and hugepages')
local.modify_t128_local_init('test1', 2)
test_pass()

test('kill processes from the list')
local.cleanup_t128_processes()
test_pass()

test('start t128 service')
local.start_t128()
test_pass()

test('wait for log pattern')
local.wait_for_t128_log_pattern('highwayManager.log', 'Processed configuration update')
test_pass()

test('restart 128T service')
local.restart_t128()
test_pass()

test('stop 128T service')
local.stop_t128()
test_pass()
test('check that local rpm is the same as os of dest host')
local.check_t128_rpm_matches_os()
test_pass()

test('collect remote log files to local folder')
local.get_t128_log_files()
test_pass()

test('delete all 128T logs')
local.clean_t128_logs()
test_pass()

test('check the 128t rpm is laready installed')
local.check_t128_rpm_is_installed()
test_pass()

test_summary()
