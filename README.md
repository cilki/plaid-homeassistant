# Plaid Integration for Home Assistant

Link your bank and card accounts through [Plaid](https://plaid.com) and expose their
balances as Home Assistant sensors. Optionally sync your full transaction history and keep
it forever.

> This integration talks to Plaid's **production** environment. You are responsible for
> your own Plaid `client_id` / `secret` and any associated costs.

## Installation

### HACS (custom repository)

1. In HACS → Integrations → the three-dot menu → *Custom repositories*, add
   `https://github.com/cilki/plaid-homeassistant` as an *Integration*.
2. Install **Plaid Integration** and restart Home Assistant.

### Manual

Copy `custom_components/plaid_integration/` into your Home Assistant `config/custom_components/`
directory and restart.

## Setup

1. *Settings → Devices & Services → Add Integration → Plaid Integration.*
2. Enter your Plaid **Client ID** and **Secret**.
3. Follow the hosted-link authorization link to connect an institution.
4. A balance sensor is created for each account. To link more institutions, add the
   integration again — the stored credentials are reused.

## Balance sensors

Each account becomes a `sensor.plaid_<institution>_<account>` whose state is the current
balance, with available balance, credit limit, currency, type, subtype, mask, and
account id as attributes.

## Transactions (optional)

Transaction syncing is **off by default**. Enable it per config entry via
*Settings → Devices & Services → Plaid Integration → Configure → Sync transactions*.

When enabled:

- All transactions are pulled from Plaid (full history on first sync, incrementally
  afterwards using Plaid's `/transactions/sync` cursor).
- **Permanent storage:** every transaction is stored in an integration-owned file,
  `.storage/plaid_integration_transactions_<entry_id>`. Home Assistant **never purges**
  this file — it is the durable, forever copy of your history.
- **Logbook events:** each newly-added transaction also fires a
  `plaid_integration_transaction` event, browsable in *Settings → Logbook*. Note these
  events live in the recorder database and are purged after `recorder.purge_keep_days`
  (default 10 days), so the Logbook shows only recent activity — the Store file above is
  the permanent record.

### Reading the full history

- A `sensor.plaid_..._transactions` entity reports the total transaction count and exposes
  the most recent 50 transactions as attributes for dashboard cards.
- The `plaid_integration.get_transactions` service returns the entire stored ledger and can
  be filtered by `account_id`, `start_date`, and `end_date`. Call it from
  *Developer Tools → Actions* (enable *Return response*) to view or export everything.

## Notes

- `requirements` pins `plaid-python`; bump the version in `manifest.json` if you need a
  newer Plaid SDK.
- The Plaid access token is stored in the Home Assistant config entry. Removing the
  integration deletes it locally but does **not** revoke it at Plaid.
