Holding available seats succeeds, while a request containing an already held seat raises SeatsUnavailable without partially holding the request.
amount_owed returns an exact int cent total for all verifier prices, including three seats priced at 19.99.
The submitted public-interface unittest suite passes with correct cent amounts and fails when amount_owed instead returns float dollars.
