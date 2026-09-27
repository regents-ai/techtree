_BASE_SECONDS = 2


def delay_for_retry(retry_number):
    """Return the delay before a one-based retry number."""
    if retry_number < 1:
        raise ValueError("retry_number must be positive")
    return _BASE_SECONDS ** retry_number
