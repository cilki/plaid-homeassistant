import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .api import PlaidClient
from .const import DOMAIN, OPT_ENABLE_TRANSACTIONS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("client_id"): str,
        vol.Required("client_secret"): str,
    }
)


class PlaidConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the Plaid integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Step 1: collect the Plaid client id and secret."""
        # Reuse credentials from an existing entry to link another institution.
        existing_entries = self._async_current_entries()
        if existing_entries:
            master_entry = existing_entries[0]
            self.client_id = master_entry.data.get("client_id", "")
            self.client_secret = master_entry.data.get("client_secret", "")
            if self.client_id and self.client_secret:
                self.plaid_client = PlaidClient(
                    self.hass, self.client_id, self.client_secret
                )
                return await self.async_step_authorization()

        if user_input is not None:
            self.client_id = user_input.get("client_id", "").strip()
            self.client_secret = user_input.get("client_secret", "").strip()

            if not self.client_id or not self.client_secret:
                _LOGGER.error("Client ID or secret is empty")
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "missing_credentials"},
                )

            self.plaid_client = PlaidClient(
                self.hass, self.client_id, self.client_secret
            )
            return await self.async_step_authorization()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA
        )

    async def async_step_authorization(self, user_input=None):
        """Step 2: show the hosted authorization link and wait for the user."""
        if user_input is not None:
            return await self.async_step_accounts()

        hosted_link, link_token = await self.plaid_client.async_create_link_token()
        if not hosted_link or not link_token:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_credentials"},
            )

        self.context["link_token"] = link_token
        return self.async_show_form(
            step_id="authorization",
            data_schema=vol.Schema({}),
            description_placeholders={"hosted_link": hosted_link},
        )

    async def async_step_accounts(self, user_input=None):
        """Step 3: exchange tokens, fetch accounts, and create the entry."""
        link_session = await self.plaid_client.async_get_link_session(
            self.context["link_token"]
        )
        if not link_session:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_link_token"},
            )

        access_token = await self.plaid_client.async_exchange_public_token(
            link_session.get("public_token")
        )
        if not access_token:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_public_token"},
            )

        accounts, institution = await self.plaid_client.async_get_accounts(
            access_token
        )
        if not accounts:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_access_token"},
            )

        return self.async_create_entry(
            title=f"Plaid Integration - {institution}",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "access_token": access_token,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PlaidOptionsFlow(config_entry)


class PlaidOptionsFlow(config_entries.OptionsFlow):
    """Options flow to toggle transaction syncing."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        OPT_ENABLE_TRANSACTIONS,
                        default=self._entry.options.get(
                            OPT_ENABLE_TRANSACTIONS, False
                        ),
                    ): bool,
                }
            ),
        )
