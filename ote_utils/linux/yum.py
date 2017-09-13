from ote_utils.remote_api import LinuxAPI
from ote_utils.ote_logger import OteLogger

logger = OteLogger(__name__)

class YumException(Exception):
    """Exception for Yumclass"""
    pass


class Yum(LinuxAPI):
    def execute_yum_command(self, cmd, skip_error=False):
        """
        Issues any yum command and raises an exception on error
        Args:
            cmd - yum command string to execute
        """
        stdout, stderr, rc = self.CLIENT.execute_command(cmd)
        if skip_error is False and rc > 0:
            raise YumException(stderr)

        return stdout

    def execute_yum_install(self, rpm, skip_error=False):
        """
        Issues yum install command on rpm
        Args:
            rpm - target rpm to install
        """
        return self.execute_yum_command('yum install -y {}'.format(rpm), skip_error)

    def execute_yum_reinstall(self, rpm):
        """
        Issues yum remove command on rpm and then installs it
        Args:
            rpm - target rpm to remove/install
        """
        self.execute_yum_remove(rpm)
        self.execute_yum_install(rpm)

    def execute_yum_remove(self, rpm):
        """
        Issues yum remove command on rpm
        Args:
            rpm - target rpm to remove
        """
        return self.execute_yum_command('yum remove -y {}'.format(rpm))

    def create_yum_repo_file(self, filename, yum_repo_dir, file_contents, ssl_cert=None):
        """
        Creates yum repository file.
        """
        if ssl_cert is not None:
            file_contents += '\nsslclientcert={}\n'.format(ssl_cert)

        cmd = 'echo \"{}\" > {}/{}'.format(file_contents, yum_repo_dir, filename)
        self.CLIENT.execute_command(cmd, expected_rc=0)

    def clean_yum(self, target='all'):
        """
        Executes yum clean command on target
        Args:
            Target - target to clean, defaults to all
        """
        cmd = 'yum clean {}'.format(target)
        self.CLIENT.execute_command(cmd, expected_rc=0)

    def verify_yum_permissions(self, install_target, should_have_permissions):
        """
        Attempts to install target package and upon success/failure raises exception
        based on if you should have permissions to install it
        Args:
            install_target - Package to install
            should_have_permissions - boolean
        """
        install_succeeded = True
        try:
            self.execute_yum_install(install_target)
        except YumException:
            install_succeeded = False

        if install_succeeded != should_have_permissions:
            return False

        return True

    def verify_rpm_version_exists_on_yum(self, package, rpm_name):
        """
        Does a "yum list" of an rpm_name and verifies package exists in list
        Args:
            rpm_name - Name of the rpm you want to check
            package - specific package to check
        """
        stdout = self.execute_yum_command(
            'yum list {} --showduplicates | grep -c {}'.format(package, rpm_name))
        logger.debug('get_yum_list_info: \'yum list {}\' has output:\n{}' .format(rpm_name, stdout))
        if stdout == '0':
            raise YumException('Package: {} does not exist on yum repo.'.format(package))
