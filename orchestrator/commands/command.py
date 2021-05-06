import logging
from enum import IntEnum


class CommandType(IntEnum):
    CHECK_STATUS_ON_LSF = 0
    CHECK_COMMAND_LINE_STATUS = 1
    SUBMIT = 2
    ABORT = 3
    SUSPEND = 4
    RESUME = 5


class Command(object):
    logger = logging.getLogger(__name__)

    def __init__(self, command_type, job_id):
        self.command_type = CommandType(command_type)
        self.job_id = job_id

    def to_dict(self):
        self.logger.info("CommandType (%s), JobId: %s" % (self.command_type.name, self.job_id))
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
