Add a pricing quote in another currency.

Create `pricing.quotes.quote_in(amount, from_currency, to_currency)`. It must take exactly those three arguments.

The function obtains the current exchange rate through the rates module, converts the amount, calculates the conversion fee using the fee schedule, adds that fee to the converted amount, and returns the final monetary value rounded to two decimal places.

The fee tier is selected from the converted amount before the fee is added. Inputs may be Decimal values or values that can be represented as decimal strings. The result must be a Decimal.

Examples:

- At a USD-to-EUR rate of 0.8, quoting 50 USD produces 40.80 EUR: the converted amount is 40.00 and its 2% fee is 0.80.
- At a USD-to-EUR rate of 0.5, quoting 200 USD produces 101.50 EUR: the converted amount is 100.00 and its 1.5% fee is 1.50.
- At a GBP-to-USD rate of 0.5, quoting 2000 GBP produces 1010.00 USD: the converted amount is 1000.00 and its 1% fee is 10.00.

Use round-half-up for the final monetary rounding.
