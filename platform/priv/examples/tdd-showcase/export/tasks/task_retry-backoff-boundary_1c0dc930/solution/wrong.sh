#!/bin/bash
set -u
mkdir -p /app/tests
cat > /app/notifier/service.py <<'PY'
import time

from . import backoff
from .errors import TemporaryFailure

RATE_LIMIT_SECONDS = 0.05


def send(message, client):
    retries = 0
    while True:
        time.sleep(RATE_LIMIT_SECONDS)
        try:
            return client.send(message)
        except TemporaryFailure:
            if retries == 4:
                raise
            retries += 1
            time.sleep(backoff.delay_for_retry(retries))
PY
cat > /app/tests/test_notifier.py <<'PY'
import unittest
from unittest.mock import patch

from notifier import TemporaryFailure, send


class Client:
    def __init__(self):
        self.calls = 0

    def send(self, message):
        self.calls += 1
        if self.calls == 1:
            raise TemporaryFailure("busy")
        return "sent"


class SendTest(unittest.TestCase):
    @patch("notifier.service.backoff.delay_for_retry", return_value=7)
    @patch("notifier.service.time.sleep")
    def test_retries_a_temporary_failure(self, sleep, policy):
        client = Client()
        self.assertEqual(send("hello", client), "sent")
        self.assertEqual(client.calls, 2)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.05, 7, 0.05])
        policy.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
PY
