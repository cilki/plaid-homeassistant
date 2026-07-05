import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .api import PlaidClient
from .const import DOMAIN, PLATFORMS, SERVICE_GET_TRANSACTIONS
from .coordinator import PlaidDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

GET_TRANSACTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
        vol.Optional("account_id"): cv.string,
        vol.Optional("start_date"): cv.date,
        vol.Optional("end_date"): cv.date,
    }
)


def _as_iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Plaid integration from a config entry."""
    access_token = entry.data.get("access_token")
    if not access_token:
        _LOGGER.error("Config entry is missing an access token")
        return False

    client = PlaidClient(hass, entry.data["client_id"], entry.data["client_secret"])
    coordinator = PlaidDataUpdateCoordinator(hass, entry, client, access_token)
    await coordinator.async_load_store()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    _async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_GET_TRANSACTIONS)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_GET_TRANSACTIONS):
        return

    async def async_get_transactions(call: ServiceCall) -> dict:
        entry_id = call.data.get("config_entry_id")
        account_id = call.data.get("account_id")
        start_date = _as_iso(call.data.get("start_date"))
        end_date = _as_iso(call.data.get("end_date"))

        coordinators = hass.data.get(DOMAIN, {})
        if entry_id:
            selected = [coordinators[entry_id]] if entry_id in coordinators else []
        else:
            selected = list(coordinators.values())

        transactions = []
        for coordinator in selected:
            transactions.extend(
                coordinator.get_transactions(account_id, start_date, end_date)
            )
        transactions.sort(key=lambda t: t.get("date") or "", reverse=True)
        return {"transactions": transactions, "count": len(transactions)}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TRANSACTIONS,
        async_get_transactions,
        schema=GET_TRANSACTIONS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
