# Reliable notification delivery

`notifier.send(message, client)` currently applies the required rate-limit pause and submits the message once with `client.send(message)`.

Change it so that a `TemporaryFailure` is retried at most four times after the initial attempt. Before each retry, wait for the duration returned by `backoff.delay_for_retry(retry_number)`, where the first retry has retry number 1. Every delivery attempt, including retries, must retain the existing rate-limit pause before calling the client.

Return the value from the first successful client call. If all five delivery attempts fail temporarily, re-raise the final `TemporaryFailure`. A `PermanentFailure` must be re-raised immediately without a retry or backoff wait.

Keep the public call `send(message, client)` and add automated tests for the requested behavior.
