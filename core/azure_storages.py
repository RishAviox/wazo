from storages.backends.azure_storage import AzureStorage

class AzureStaticStorage(AzureStorage):
    azure_container = 'static'
    
class AzureMediaStorage(AzureStorage):
    azure_container = 'media'