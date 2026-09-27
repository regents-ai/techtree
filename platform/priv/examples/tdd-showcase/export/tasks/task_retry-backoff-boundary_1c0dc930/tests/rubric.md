send returns a successful client result, retries temporary failures no more than four times with the rate-limit and policy waits in the required order, re-raises the final temporary failure, and never retries a permanent failure.
The submitted unittest suite completes in under five seconds while network sockets are blocked.
The submitted tests fail for implementations that make one extra retry, use waits that differ from the backoff policy, or retry permanent failures.
The submitted tests pass unchanged with a behavior-equivalent reorganization of the backoff module and do not replace functions or classes owned by that module.
