from ote_utils.ote_logger import OteLogger
import os

OteLogger.set_global_loglevel('DEBUG')
a_log_name = '/tmp/a.log'
alog = OteLogger('classA', filename=a_log_name, file_mode='overwrite')
blog = OteLogger('classB')
blog.set_loglevel('CRIT')
blog.set_loglevel('CRITICAL')
clog = OteLogger('classC')


class a(object):

    def a1(self):
        alog.debug('PASS: This should print')
        alog.info('PASS: This should print')
        alog.warning('PASS: This should print')
        alog.error('PASS: This should print')
        alog.critical('PASS: This should print')


class b(object):

    def b1(self):
        blog.debug('FAIL: This should not print')
        blog.info('FAIL: This should not print')
        blog.warning('FAIL: This should not print')
        blog.error('FAIL: This should not print')
        blog.critical('PASS: This should print')


class c(object):

    def c1(self):
        clog.debug('PASS: This should print')
        clog.info('PASS: This should print')
        clog.warning('PASS: This should print')
        clog.error('PASS: This should print')
        clog.critical('PASS: This should print')


obja = a()
obja.a1()
if (os.path.isfile(a_log_name)):
    alog.info('PASS: \'{}\' exists - Cleaning up.'.format(a_log_name))
    os.remove(a_log_name)
else:
    alog.info('FAIL: \'{}\' didn\'t exist!'.format(a_log_name))

objb = b()
objb.b1()
objc = c()
objc.c1()
