#!/usr/bin/python
#!/usr/bin/env python
# NOTE: ^^^^ Make sure to use 'env python' when using virtual environments
# otherwise you will likely use the wrong version of python which won't
# have the right paths setup and nothing will work
# -----------------------------------------------------------------------------
from __future__ import print_function
import os
from ote_utils.linux import lshw
from ote_utils.ote_logger import OteLogger
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

print("Testing python ssh linux client")
print("-------------------------------")
alias = 'localhost'
host = '127.0.0.1'
user = os.environ['USER']
keyfile = '/Users/' + os.environ['USER'] + '/.ssh/id_rsa.pub'
logfile = '/tmp/test-ote_sshlib_clients.lshw.log'

test('Creating Linux Object')
# note: each SSHClient has an sftp and shell component
#       so there is no need to spawn a new shell or sftp client
#       unless you need a separate instance to the same host
local = lshw.Lshw()
local.connect_to_host(host, 'root', 'exit33')

local.get_host_hw_info_file()
test_pass()

local.get_host_hw_dictionary()
test_pass()

test_summary()
