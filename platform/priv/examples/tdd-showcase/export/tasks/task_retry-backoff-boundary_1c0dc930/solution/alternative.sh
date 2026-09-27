#!/bin/bash
set -u
mkdir -p /app/tests
cat > /app/tests/test_notifier.py <<'PY'
import unittest
from unittest.mock import patch

import notifier.service as service
from notifier.errors import PermanentFailure, TemporaryFailure


class ScriptedMailService:
    def __init__(self, *events):
        self.events = list(events)
        self.received = []

    def send(self, message):
        self.received.append(message)
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event


class NotificationDeliveryTest(unittest.TestCase):
    def deliver(self, *events):
        client = ScriptedMailService(*events)
        waits = []
        with patch.object(service.time, "sleep", side_effect=waits.append):
            try:
                value = service.send("status", client)
                error = None
            except Exception as caught:
                value = None
                error = caught
        return client, waits, value, error

    def test_each_allowed_temporary_failure_adds_the_next_wait(self):
        expected_backoffs = [2, 4, 8, 16]
        for failures in range(5):
            with self.subTest(failures=failures):
                events = [TemporaryFailure("busy") for _ in range(failures)] + ["sent"]
                client, waits, value, error = self.deliver(*events)
                expected = []
                for number in range(failures + 1):
                    expected.append(0.05)
                    if number < failures:
                        expected.append(expected_backoffs[number])
                self.assertIsNone(error)
                self.assertEqual(value, "sent")
                self.assertEqual(waits, expected)
                self.assertEqual(len(client.received), failures + 1)

    def test_a_fifth_temporary_failure_ends_delivery(self):
        failures = [TemporaryFailure(str(number)) for number in range(5)]
        client, waits, value, error = self.deliver(*failures)
        self.assertIs(error, failures[-1])
        self.assertIsNone(value)
        self.assertEqual(len(client.received), 5)
        self.assertEqual(waits, [0.05, 2, 0.05, 4, 0.05, 8, 0.05, 16, 0.05])

    def test_a_permanent_rejection_stops_delivery(self):
        rejection = PermanentFailure("blocked")
        client, waits, value, error = self.deliver(rejection, "unexpected")
        self.assertIs(error, rejection)
        self.assertIsNone(value)
        self.assertEqual(client.received, ["status"])
        self.assertEqual(waits, [0.05])
PY
python3 -m unittest discover -s /app/tests -p 'test*.py' >/dev/null 2>&1 || true
cat > /app/notifier/service.py <<'PY'
import time

from .backoff import delay_for_retry
from .errors import TemporaryFailure

RATE_LIMIT_SECONDS = 0.05


def send(message, client):
    retries_used = 0
    while True:
        time.sleep(RATE_LIMIT_SECONDS)
        try:
            return client.send(message)
        except TemporaryFailure:
            if retries_used >= 4:
                raise
            retries_used += 1
            time.sleep(delay_for_retry(retries_used))
PY
python3 -m unittest discover -s /app/tests -p 'test*.py' >/dev/null
