# Theater Sales Context

A show is one scheduled performance. A seat is an individually priced place at a show.

A hold temporarily removes one or more seats from availability while a customer decides whether to complete a purchase. The operation that creates one is called `hold_seats`, and its identifier is a hold ID. A caller asks for the amount owed for a hold before completing the sale.

Use show, seat, hold, hold ID, amount owed, and unavailable in public interfaces and test descriptions. A hold is not called a cart, booking, order, or generic reservation in this package.
