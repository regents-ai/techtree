class TemporaryFailure(Exception):
    """The mail service may accept the message if it is tried again."""


class PermanentFailure(Exception):
    """The mail service will not accept this message."""
