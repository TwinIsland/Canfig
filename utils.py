import os
import subprocess


def check_file_exists(filename):
    return os.path.isfile(filename)


def check_command_installed(command):
    return (
            subprocess.call(
                ["which", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            == 0
    )


class CanfigException(Exception):
    pass


class TriggerException(Exception):
    pass
