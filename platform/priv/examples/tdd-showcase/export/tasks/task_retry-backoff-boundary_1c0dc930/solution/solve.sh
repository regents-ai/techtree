#!/bin/bash
set -u
mkdir -p /app/tests
cat > /app/tests/test_notifier.py <<'PY'
import unittest
from unittest.mock import patch

from notifier import PermanentFailure, TemporaryFailure, send


class MailClient:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.messages = []

    def send(self, message):
        self.messages.append(message)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class SendTests(unittest.TestCase):
    @patch("notifier.service.time.sleep")
    def test_temporary_failures_use_policy_waits_until_success(self, sleep):
        client = MailClient([
            TemporaryFailure("busy"),
            TemporaryFailure("still busy"),
            "receipt-7",
        ])

        self.assertEqual(send("hello", client), "receipt-7")
        self.assertEqual(client.messages, ["hello", "hello", "hello"])
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [0.05, 2, 0.05, 4, 0.05],
        )

    @patch("notifier.service.time.sleep")
    def test_only_four_retries_are_allowed(self, sleep):
        final = TemporaryFailure("last failure")
        client = MailClient([
            TemporaryFailure("one"),
            TemporaryFailure("two"),
            TemporaryFailure("three"),
            TemporaryFailure("four"),
            final,
            "too late",
        ])

        with self.assertRaises(TemporaryFailure) as raised:
            send("hello", client)

        self.assertIs(raised.exception, final)
        self.assertEqual(len(client.messages), 5)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [0.05, 2, 0.05, 4, 0.05, 8, 0.05, 16, 0.05],
        )

    @patch("notifier.service.time.sleep")
    def test_permanent_failure_is_not_retried(self, sleep):
        failure = PermanentFailure("invalid address")
        client = MailClient([failure, "too late"])

        with self.assertRaises(PermanentFailure) as raised:
            send("hello", client)

        self.assertIs(raised.exception, failure)
        self.assertEqual(client.messages, ["hello"])
        sleep.assert_called_once_with(0.05)


if __name__ == "__main__":
    unittest.main()
PY
python3 -m unittest discover -s /app/tests -p 'test*.py' >/dev/null 2>&1 || true
cat > /app/notifier/service.py <<'PY'
import time

from . import backoff
from .errors import TemporaryFailure

RATE_LIMIT_SECONDS = 0.05
MAX_RETRIES = 4


def send(message, client):
    for retry_number in range(MAX_RETRIES + 1):
        time.sleep(RATE_LIMIT_SECONDS)
        try:
            return client.send(message)
        except TemporaryFailure:
            if retry_number == MAX_RETRIES:
                raise
            time.sleep(backoff.delay_for_retry(retry_number + 1))
PY
python3 -m unittest discover -s /app/tests -p 'test*.py' >/dev/null
