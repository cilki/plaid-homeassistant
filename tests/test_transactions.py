"""Unit tests for the pure transaction-ledger helpers.

Loaded directly from the source file so the tests run without Home Assistant or
the Plaid SDK installed.
"""
import datetime
import importlib.util
import os

_MODULE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "custom_components",
    "plaid_integration",
    "transactions.py",
)
_spec = importlib.util.spec_from_file_location("plaid_transactions", _MODULE_PATH)
transactions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transactions)


def _txn(txn_id, date="2026-07-01", account_id="acc1", **extra):
    data = {
        "transaction_id": txn_id,
        "account_id": account_id,
        "name": f"txn-{txn_id}",
        "amount": 1.0,
        "date": date,
    }
    data.update(extra)
    return data


def test_serialize_converts_date_and_selects_fields():
    record = transactions.serialize_transaction(
        {
            "transaction_id": "t1",
            "account_id": "a1",
            "name": "Coffee",
            "amount": 5.75,
            "date": datetime.date(2026, 7, 4),
            "authorized_date": datetime.date(2026, 7, 3),
            "unexpected": "dropped",
        }
    )
    assert record["date"] == "2026-07-04"
    assert record["authorized_date"] == "2026-07-03"
    assert record["amount"] == 5.75
    assert "unexpected" not in record


def test_added_returns_new_records_once():
    ledger = {}
    new = transactions.apply_transaction_updates(
        ledger, {"added": [_txn("t1"), _txn("t2")]}
    )
    assert [r["transaction_id"] for r in new] == ["t1", "t2"]
    assert set(ledger) == {"t1", "t2"}

    # Re-delivering an existing transaction updates it but is not "new".
    again = transactions.apply_transaction_updates(
        ledger, {"added": [_txn("t1", name_override="x")]}
    )
    assert again == []
    assert set(ledger) == {"t1", "t2"}


def test_modified_upserts_without_being_new():
    ledger = {}
    transactions.apply_transaction_updates(ledger, {"added": [_txn("t1", amount=1.0)]})
    new = transactions.apply_transaction_updates(
        ledger, {"modified": [_txn("t1", amount=9.0)]}
    )
    assert new == []
    assert ledger["t1"]["amount"] == 9.0


def test_removed_drops_from_ledger():
    ledger = {}
    transactions.apply_transaction_updates(ledger, {"added": [_txn("t1"), _txn("t2")]})
    transactions.apply_transaction_updates(
        ledger, {"removed": [{"transaction_id": "t1"}]}
    )
    assert set(ledger) == {"t2"}
    # Removing an unknown id is a no-op.
    transactions.apply_transaction_updates(
        ledger, {"removed": [{"transaction_id": "nope"}]}
    )
    assert set(ledger) == {"t2"}


def test_added_without_id_is_ignored():
    ledger = {}
    new = transactions.apply_transaction_updates(
        ledger, {"added": [{"transaction_id": None, "amount": 1.0}]}
    )
    assert new == []
    assert ledger == {}


def test_multi_page_sync_accumulates():
    ledger = {}
    pages = [
        {"added": [_txn("t1"), _txn("t2")], "has_more": True},
        {"added": [_txn("t3")], "modified": [_txn("t1", amount=2.0)], "has_more": False},
    ]
    new = []
    for page in pages:
        new.extend(transactions.apply_transaction_updates(ledger, page))
    assert [r["transaction_id"] for r in new] == ["t1", "t2", "t3"]
    assert set(ledger) == {"t1", "t2", "t3"}
    assert ledger["t1"]["amount"] == 2.0


def test_filter_by_account_and_date_sorted_newest_first():
    ledger = {}
    transactions.apply_transaction_updates(
        ledger,
        {
            "added": [
                _txn("t1", date="2026-07-01", account_id="a1"),
                _txn("t2", date="2026-07-05", account_id="a1"),
                _txn("t3", date="2026-07-03", account_id="a2"),
            ]
        },
    )

    a1 = transactions.filter_transactions(ledger, account_id="a1")
    assert [r["transaction_id"] for r in a1] == ["t2", "t1"]

    ranged = transactions.filter_transactions(
        ledger, start_date="2026-07-02", end_date="2026-07-04"
    )
    assert [r["transaction_id"] for r in ranged] == ["t3"]


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in funcs:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(funcs)} passed")


if __name__ == "__main__":
    _run()
