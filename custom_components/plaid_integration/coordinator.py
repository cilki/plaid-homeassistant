import logging
from datetime import timedelta

import plaid
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import _error_detail
from .const import (
    DOMAIN,
    EVENT_TRANSACTION,
    OPT_ENABLE_TRANSACTIONS,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .transactions import apply_transaction_updates, filter_transactions

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)


class PlaidDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetches balances and, when enabled, keeps a permanent transaction ledger."""

    def __init__(self, hass, entry, client, access_token):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        self.client = client
        self.access_token = access_token
        self._store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}_{entry.entry_id}"
        )
        self._cursor = None
        self._transactions = {}

    @property
    def transactions_enabled(self):
        return self.entry.options.get(OPT_ENABLE_TRANSACTIONS, False)

    @property
    def transaction_count(self):
        return len(self._transactions)

    async def async_load_store(self):
        """Load the permanent ledger and sync cursor from disk."""
        stored = await self._store.async_load()
        if stored:
            self._cursor = stored.get("cursor")
            self._transactions = stored.get("transactions") or {}

    def recent_transactions(self, limit):
        """Return the most recent transactions, newest first."""
        return self.get_transactions()[:limit]

    def get_transactions(self, account_id=None, start_date=None, end_date=None):
        """Return the stored ledger, optionally filtered, newest first."""
        return filter_transactions(
            self._transactions, account_id, start_date, end_date
        )

    async def _async_update_data(self):
        accounts, institution = await self.client.async_get_accounts(self.access_token)
        if accounts is None:
            raise UpdateFailed("Failed to fetch accounts")

        for account in accounts:
            account["institution"] = institution

        if self.transactions_enabled:
            await self._async_sync_transactions()

        return {"accounts": accounts}

    async def _async_sync_transactions(self):
        """Pull transaction updates, update the ledger, and fire events for new ones."""
        cursor = self._cursor
        new_transactions = []
        try:
            has_more = True
            while has_more:
                response = await self.client.async_sync_transactions(
                    self.access_token, cursor
                )
                new_transactions.extend(
                    apply_transaction_updates(self._transactions, response)
                )
                cursor = response.get("next_cursor")
                has_more = response.get("has_more", False)
        except plaid.ApiException as err:
            raise UpdateFailed(
                f"Failed to sync transactions: {_error_detail(err)}"
            ) from err

        self._cursor = cursor
        await self._store.async_save(
            {"cursor": self._cursor, "transactions": self._transactions}
        )

        # Persist before firing so a restart mid-loop cannot duplicate events.
        for record in new_transactions:
            self.hass.bus.async_fire(EVENT_TRANSACTION, record)
