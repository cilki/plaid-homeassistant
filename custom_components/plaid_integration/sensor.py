import logging
import re

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, RECENT_TRANSACTIONS_LIMIT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Plaid sensors for a config entry using the shared coordinator."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        PlaidAccountSensor(coordinator, account)
        for account in coordinator.data["accounts"]
    ]

    if coordinator.transactions_enabled:
        entities.append(PlaidTransactionsSensor(coordinator, entry))

    async_add_entities(entities)


class PlaidAccountSensor(CoordinatorEntity, Entity):
    """Representation of a Plaid account balance."""

    def __init__(self, coordinator, account):
        super().__init__(coordinator)
        self._account_id = account["account_id"]
        self._name = account["name"]
        self._institution = account["institution"]
        self._mask = account.get("mask")
        self._attr_unique_id = self._generate_unique_id()

    def _generate_unique_id(self):
        sanitized_institution = self._sanitize(self._institution)
        sanitized_account_id = self._sanitize(self._account_id)
        return f"plaid_{sanitized_institution}_{sanitized_account_id}"

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        name = f"Plaid {self._institution} {self._name}"
        if self._mask:
            name += f" {self._mask}"
        return name

    @property
    def state(self):
        return self._account_data().get("balances", {}).get("current", 0)

    @property
    def extra_state_attributes(self):
        account = self._account_data()
        balances = account.get("balances", {})
        return {
            "institution": self._institution,
            "name": self._name,
            "available_balance": balances.get("available", 0),
            "credit_limit": balances.get("limit", 0),
            "currency": balances.get("iso_currency_code", "USD"),
            "account_type": account.get("type"),
            "account_subtype": account.get("subtype"),
            "account_mask": self._mask,
            "account_id": self._account_id,
        }

    def _account_data(self):
        """Return the latest data for this account from the coordinator."""
        for account in self.coordinator.data["accounts"]:
            if account["account_id"] == self._account_id:
                return account
        return {}

    def _sanitize(self, value):
        """Sanitize a string to be a valid Home Assistant ID component."""
        return re.sub(r"[^a-zA-Z0-9_]", "_", value.lower())


class PlaidTransactionsSensor(CoordinatorEntity, Entity):
    """Exposes the transaction count and the most recent transactions."""

    _attr_name = "Plaid Transactions"
    _attr_icon = "mdi:bank-transfer"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"plaid_transactions_{entry.entry_id}"

    @property
    def should_poll(self):
        return False

    @property
    def state(self):
        return self.coordinator.transaction_count

    @property
    def extra_state_attributes(self):
        return {
            "transactions": self.coordinator.recent_transactions(
                RECENT_TRANSACTIONS_LIMIT
            )
        }
