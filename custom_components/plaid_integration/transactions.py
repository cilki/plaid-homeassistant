"""Pure transaction-ledger helpers.

Kept free of Home Assistant and Plaid imports so the logic can be unit-tested
in isolation.
"""


def iso(value):
    """Convert a date/datetime to an ISO string, leaving other values as-is."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def serialize_transaction(txn):
    """Reduce a Plaid transaction to a compact, JSON-serializable record."""
    return {
        "transaction_id": txn.get("transaction_id"),
        "account_id": txn.get("account_id"),
        "name": txn.get("name"),
        "merchant_name": txn.get("merchant_name"),
        "amount": txn.get("amount"),
        "iso_currency_code": txn.get("iso_currency_code"),
        "date": iso(txn.get("date")),
        "authorized_date": iso(txn.get("authorized_date")),
        "pending": txn.get("pending"),
        "payment_channel": txn.get("payment_channel"),
        "category": txn.get("category"),
    }


def apply_transaction_updates(ledger, response):
    """Apply one ``/transactions/sync`` page to ``ledger`` in place.

    Upserts ``added`` and ``modified`` transactions and drops ``removed`` ones,
    keyed by ``transaction_id``. Returns the list of records that were genuinely
    new (not previously in the ledger) so the caller can emit events for them.
    """
    new_records = []

    for txn in response.get("added", []):
        record = serialize_transaction(txn)
        txn_id = record["transaction_id"]
        if not txn_id:
            continue
        if txn_id not in ledger:
            new_records.append(record)
        ledger[txn_id] = record

    for txn in response.get("modified", []):
        record = serialize_transaction(txn)
        txn_id = record["transaction_id"]
        if txn_id:
            ledger[txn_id] = record

    for txn in response.get("removed", []):
        ledger.pop(txn.get("transaction_id"), None)

    return new_records


def filter_transactions(ledger, account_id=None, start_date=None, end_date=None):
    """Return ledger values filtered by account/date, sorted newest first.

    ``start_date``/``end_date`` are ISO date strings, which sort the same way as
    the stored ``date`` values.
    """
    result = []
    for txn in ledger.values():
        if account_id and txn.get("account_id") != account_id:
            continue
        date = txn.get("date")
        if start_date and (date is None or date < start_date):
            continue
        if end_date and (date is None or date > end_date):
            continue
        result.append(txn)
    result.sort(key=lambda t: t.get("date") or "", reverse=True)
    return result
