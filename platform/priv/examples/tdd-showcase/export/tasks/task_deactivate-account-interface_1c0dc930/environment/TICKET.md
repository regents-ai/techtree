Account deactivation

Add two public package functions:

- deactivate(account_id)
- reactivate(account_id)

A deactivated account remains available from fetch(account_id), but list_accounts() must omit it. Calling sign_in(email, password) with the correct credentials of a deactivated account must raise the public accounts.AccountDeactivated exception.

Reactivating the account restores it to list_accounts() and permits sign-in again. Deactivation and reactivation are each idempotent. Both functions return the account in the same public representation used by create and fetch. An unknown account ID raises KeyError.

The state must remain in effect after opening the same database path again.
