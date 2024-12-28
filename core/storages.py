from storages.backends.azure_storage import AzureStorage
import os

class AzureStaticStorage(AzureStorage):
    account_name = os.environ.get("WAJO_AZURE_STORAGE_ACCOUNT_NAME")      # Must be replaced by your settings
    account_key = os.environ.get("WAJO_AZURE_STORAGE_ACCOUNT_KEY")        # Must be replaced by your settings
    azure_container = "static"
    expiration_secs = None  # or specify a time in seconds if you want SAS token expiration

class AzureMediaStorage(AzureStorage):
    account_name = os.environ.get("WAJO_AZURE_STORAGE_ACCOUNT_NAME")
    account_key = os.environ.get("WAJO_AZURE_STORAGE_ACCOUNT_KEY")
    azure_container = "media"
    expiration_secs = None
