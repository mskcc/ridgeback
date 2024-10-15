class RetryException(Exception):
    pass


class StopException(Exception):
    pass


class FailToSubmitToSchedulerException(Exception):
    pass


class FetchStatusException(Exception):
    pass
