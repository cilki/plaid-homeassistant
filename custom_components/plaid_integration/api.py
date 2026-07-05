import json
import logging

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_hosted_link import LinkTokenCreateHostedLink
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_get_request import LinkTokenGetRequest
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
CLIENT_USER_ID = "home-assistant-user"


def _error_detail(err):
    """Extract a safe, compact detail from a Plaid ApiException (no secrets)."""
    body = getattr(err, "body", None)
    if body:
        try:
            data = json.loads(body)
            return data.get("error_code") or data.get("error_message")
        except (ValueError, TypeError):
            pass
    return getattr(err, "status", None)


class PlaidClient:
    """Thin async wrapper around the synchronous plaid-python SDK."""

    def __init__(self, hass, client_id, client_secret):
        self._hass = hass
        configuration = plaid.Configuration(
            host=plaid.Environment.Production,
            api_key={"clientId": client_id, "secret": client_secret},
        )
        self._client = plaid_api.PlaidApi(plaid.ApiClient(configuration))

    async def _call(self, method, request):
        """Run a blocking SDK call in the executor and return it as a dict."""
        response = await self._hass.async_add_executor_job(
            lambda: method(request, _request_timeout=REQUEST_TIMEOUT)
        )
        return response.to_dict()

    async def async_create_link_token(self):
        """Create a hosted link token to add a new account."""
        request = LinkTokenCreateRequest(
            client_name="Home Assistant",
            language="en",
            country_codes=[CountryCode("US")],
            user=LinkTokenCreateRequestUser(client_user_id=CLIENT_USER_ID),
            products=[Products("transactions")],
            hosted_link=LinkTokenCreateHostedLink(),
        )
        try:
            data = await self._call(self._client.link_token_create, request)
        except plaid.ApiException as err:
            _LOGGER.error("Failed to create link token: %s", _error_detail(err))
            return None, None
        return data.get("hosted_link_url"), data.get("link_token")

    async def async_get_link_session(self, link_token):
        """Return the completed link session containing a public token, if any."""
        request = LinkTokenGetRequest(link_token=link_token)
        try:
            data = await self._call(self._client.link_token_get, request)
        except plaid.ApiException as err:
            _LOGGER.error("Failed to get link session: %s", _error_detail(err))
            return None

        for session in data.get("link_sessions", []):
            results = session.get("results") or {}
            item_add_results = results.get("item_add_results") or []
            item = next((i for i in item_add_results if i.get("public_token")), None)
            if item:
                session["public_token"] = item["public_token"]
                return session

        _LOGGER.error("Plaid link session did not contain a public token")
        return None

    async def async_exchange_public_token(self, public_token):
        """Exchange a public token for a long-lived access token."""
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        try:
            data = await self._call(self._client.item_public_token_exchange, request)
        except plaid.ApiException as err:
            _LOGGER.error("Failed to exchange public token: %s", _error_detail(err))
            return None
        return data.get("access_token")

    async def async_get_accounts(self, access_token):
        """Retrieve account balances and the institution name from Plaid."""
        request = AccountsGetRequest(access_token=access_token)
        try:
            data = await self._call(self._client.accounts_get, request)
        except plaid.ApiException as err:
            _LOGGER.error("Failed to fetch accounts: %s", _error_detail(err))
            return None, None
        accounts = data.get("accounts", [])
        institution = (data.get("item") or {}).get("institution_name")
        return accounts, institution

    async def async_sync_transactions(self, access_token, cursor=None):
        """Fetch one page of transaction updates via the sync cursor.

        Returns the raw response dict (``added``/``modified``/``removed``/
        ``next_cursor``/``has_more``). Raises ``plaid.ApiException`` on failure so
        the coordinator can surface it as an update failure.
        """
        kwargs = {"access_token": access_token}
        if cursor:
            kwargs["cursor"] = cursor
        request = TransactionsSyncRequest(**kwargs)
        return await self._call(self._client.transactions_sync, request)
