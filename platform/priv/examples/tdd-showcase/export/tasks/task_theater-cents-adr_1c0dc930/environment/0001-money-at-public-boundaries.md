# ADR 0001: Money at package boundaries

Status: Accepted

## Context

Catalog sources commonly express theater prices as decimal dollar strings. Binary floating-point values can alter a cent when several seat prices are totaled.

## Decision

Every monetary amount crossing the theater-sales package's public boundary is an integer number of cents. Conversion from catalog decimal strings must be exact. Persisted hold totals, if any, also use integer cents.

Catalog adapters may retain the source's decimal strings internally. Public callers must not receive floating-point dollar values or decimal objects.
