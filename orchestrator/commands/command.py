from enum import IntEnum


class CommandType(IntEnum):
    CHECK_STATUS_ON_LSF = 0
    SUBMIT = 1
    ABORT = 2
    SUSPEND = 3
    RESUME = 4


class Command(object):

    def __init__(self, command_type, job_id):
        self.command_type = CommandType(command_type)
        self.job_id = job_id

    def to_dict(self):
        return dict(
            type=self.command_type,
            job_id=self.job_id
        )

    @classmethod
    def from_dict(cls, dct):
        return cls(
            dct['type'],
            dct['job_id']
        )
