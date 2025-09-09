from storages.backends.azure_storage import AzureStorage
from django.conf import settings

class AzureStaticStorage(AzureStorage):
    azure_container = 'static'
    # Use connection string if available, otherwise fall back to account name/key
    azure_connection_string = getattr(settings, 'AZURE_CONNECTION_STRING', None)
    azure_account_name = getattr(settings, 'AZURE_ACCOUNT_NAME', None)
    azure_account_key = getattr(settings, 'AZURE_ACCOUNT_KEY', None)
    
class AzureMediaStorage(AzureStorage):
    azure_container = 'media'
    # Use connection string if available, otherwise fall back to account name/key
    azure_connection_string = getattr(settings, 'AZURE_CONNECTION_STRING', None)
    azure_account_name = getattr(settings, 'AZURE_ACCOUNT_NAME', None)
    azure_account_key = getattr(settings, 'AZURE_ACCOUNT_KEY', None)
    
    # Configure for better handling of large file uploads
    azure_ssl = True
    azure_upload_max_conn = 16  # Increased parallel connections for large files
    azure_upload_chunk_size = 32 * 1024 * 1024  # 32MB chunks for better reliability with large files
    azure_download_max_conn = 16  # Number of parallel connections for downloads
    azure_download_chunk_size = 32 * 1024 * 1024  # 32MB chunks for downloads
    # Increase timeout for large file operations (20 minutes for 5-6GB files)
    azure_connection_timeout = 1200  # 20 minutes
    azure_read_timeout = 1200  # 20 minutes
    # Additional settings for large file handling
    azure_max_block_size = 100 * 1024 * 1024  # 100MB max block size
    azure_max_single_put_size = 256 * 1024 * 1024  # 256MB max single put size