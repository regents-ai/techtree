The accounts package implements all deactivation, reactivation, persistence, error, listing, fetch, and sign-in behavior specified by the ticket.
At least one submitted test detects an implementation that still lists a deactivated account.
At least one submitted test detects an implementation that permits sign-in to a deactivated account, and at least one detects ineffective reactivation.
All submitted tests pass unchanged when the package is replaced with a behavior-equivalent implementation having different private storage and schema.
