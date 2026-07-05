DOMAIN = "plaid_integration"
PLATFORMS = ["sensor"]

# Options
OPT_ENABLE_TRANSACTIONS = "enable_transactions"

# Event fired for each newly added transaction (browsable in the Logbook).
EVENT_TRANSACTION = "plaid_integration_transaction"

# Service that returns the full, permanently-stored transaction ledger.
SERVICE_GET_TRANSACTIONS = "get_transactions"

# Number of most-recent transactions exposed as sensor attributes.
RECENT_TRANSACTIONS_LIMIT = 50

# Persistent ledger stored via homeassistant.helpers.storage.Store.
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_transactions"
