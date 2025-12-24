# #!/usr/bin/env python
# """
# Standalone Python script to list all video files (gc-*_with_overlay.mp4) 
# from Azure Blob Storage and save to CSV.

# Usage:
#     # Using .env file (recommended)
#     # Create a .env file with:
#     #   wajo-azure-storage-account-name=your_account_name
#     #   wajo-azure-storage-account-key=your_account_key
#     #   wajo-azure-storage-connection-string=your_connection_string  # Optional, alternative to account/key
#     python list_azure_videos.py
    
#     # Or use command-line arguments
#     python list_azure_videos.py --account-name "account" --account-key "key" --container "media" --output "output.csv"
# """

# import argparse
# import os
# import sys
# import csv
# from azure.storage.blob import BlobServiceClient
# from azure.core.exceptions import AzureError

# try:
#     from dotenv import load_dotenv
# except ImportError:
#     print("WARNING: python-dotenv not installed. Install it with: pip install python-dotenv")
#     print("The script will continue but won't load .env file.")
#     load_dotenv = None


# def extract_account_name_from_connection_string(connection_string):
#     """Extract account name from Azure connection string"""
#     import re
#     match = re.search(r'AccountName=([^;]+)', connection_string)
#     return match.group(1) if match else None


# def process_session_data(container_name, session_id, session_data, results, account_name=None, custom_domain=None):
#     """Process session data to generate CSV rows"""
#     base_path = f'sessions/{session_id}'
#     highlights_path = f'{base_path}/videos/highlights'

#     videos_exists = session_data['videos']
#     highlights_exists = session_data['highlights']
#     video_files = session_data['videos_list']

#     # Process results
#     if not videos_exists:
#         # Add entry for missing videos folder
#         results.append({
#             'sr_no': len(results) + 1,
#             'folder_path': base_path,
#             'content_name': None,
#             'content_path': None,
#             'content_url': None,
#             'remark': 'videos folder not found'
#         })
#     elif not highlights_exists:
#         # Add entry for missing highlights folder
#         results.append({
#             'sr_no': len(results) + 1,
#             'folder_path': highlights_path,
#             'content_name': None,
#             'content_path': None,
#             'content_url': None,
#             'remark': 'highlights folder not found'
#         })
#     elif not video_files:
#         # Add entry for no videos found
#         results.append({
#             'sr_no': len(results) + 1,
#             'folder_path': highlights_path,
#             'content_name': None,
#             'content_path': None,
#             'content_url': None,
#             'remark': 'no gc-*_with_overlay.mp4 files found'
#         })
#     else:
#         # Add entries for each video file
#         for video in video_files:
#             blob_name = video['blob_name']
#             filename = video['filename']
            
#             # Generate content URL
#             if custom_domain:
#                 content_url = f"https://{custom_domain}/{container_name}/{blob_name}"
#             elif account_name:
#                 content_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
#             else:
#                 content_url = f"https://<account>.blob.core.windows.net/{container_name}/{blob_name}"

#             # Build folder path with parent>>current format for nested folders
#             path_parts = blob_name.split('/')
#             folder_path_parts = path_parts[:-1]  # All except filename
#             folder_path = '>>'.join(folder_path_parts) if len(folder_path_parts) > 1 else folder_path_parts[0] if folder_path_parts else ''

#             results.append({
#                 'sr_no': len(results) + 1,
#                 'folder_path': folder_path,
#                 'content_name': filename,
#                 'content_path': blob_name,
#                 'content_url': content_url,
#                 'remark': 'found'
#             })


# def write_csv(results, output_file):
#     """Write results to CSV file"""
#     if not results:
#         print('WARNING: No results to write to CSV')
#         return

#     # Ensure output directory exists
#     output_dir = os.path.dirname(output_file) if os.path.dirname(output_file) else '.'
#     if output_dir and not os.path.exists(output_dir):
#         os.makedirs(output_dir)

#     # Write CSV
#     with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
#         fieldnames = ['Sr.No.', 'folder_path', 'content_name', 'content_path', 'content_url', 'remark']
#         writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
#         writer.writeheader()
#         for result in results:
#             writer.writerow({
#                 'Sr.No.': result['sr_no'],
#                 'folder_path': result['folder_path'],
#                 'content_name': result['content_name'] or '',
#                 'content_path': result['content_path'] or '',
#                 'content_url': result['content_url'] or '',
#                 'remark': result['remark']
#             })

#     print(f'SUCCESS: CSV file written: {output_file}')


# def main():
#     # Load environment variables from .env file if dotenv is available
#     if load_dotenv:
#         # Try to load .env file from script directory first
#         env_path = os.path.join(os.path.dirname(__file__), '.env')
#         if os.path.exists(env_path):
#             load_dotenv(env_path, override=True)
#             print(f'✓ Loaded environment variables from: {env_path}')
#         else:
#             # Try loading from current working directory
#             cwd_env = os.path.join(os.getcwd(), '.env')
#             if os.path.exists(cwd_env):
#                 load_dotenv(cwd_env, override=True)
#                 print(f'✓ Loaded environment variables from: {cwd_env}')
#             else:
#                 # Try default load_dotenv() which searches in current directory and parent directories
#                 loaded = load_dotenv(override=True)
#                 if loaded:
#                     print('✓ Loaded environment variables from .env file')
#                 else:
#                     print('⚠ No .env file found. Using system environment variables or command-line arguments.')
#     else:
#         print('⚠ python-dotenv not installed. Using system environment variables or command-line arguments.')
    
#     parser = argparse.ArgumentParser(
#         description='List all video files (gc-*_with_overlay.mp4) from Azure Blob Storage and save to CSV'
#     )
#     parser.add_argument(
#         '--connection-string',
#         type=str,
#         default=None,
#         help='Azure Storage connection string (or set wajo-azure-storage-connection-string in .env)'
#     )
#     parser.add_argument(
#         '--account-name',
#         type=str,
#         default=None,
#         help='Azure Storage account name (or set wajo-azure-storage-account-name in .env)'
#     )
#     parser.add_argument(
#         '--account-key',
#         type=str,
#         default=None,
#         help='Azure Storage account key (or set wajo-azure-storage-account-key in .env)'
#     )
#     parser.add_argument(
#         '--container',
#         type=str,
#         default=None,
#         help='Azure container name (default: media)'
#     )
#     parser.add_argument(
#         '--custom-domain',
#         type=str,
#         default=None,
#         help='Custom domain for blob URLs (optional)'
#     )
#     parser.add_argument(
#         '--output',
#         type=str,
#         default='azure_videos_list.csv',
#         help='Output CSV file path (default: azure_videos_list.csv)'
#     )

#     args = parser.parse_args()

#     # Get configuration from args or environment variables (loaded from .env)
#     # Priority: command-line args > environment variables > defaults
#     connection_string = args.connection_string or os.environ.get('wajo-azure-storage-connection-string')
#     account_name = args.account_name or os.environ.get('wajo-azure-storage-account-name')
#     account_key = args.account_key or os.environ.get('wajo-azure-storage-account-key')
#     container_name = args.container or os.environ.get('AZURE_CONTAINER_NAME', 'media')
#     custom_domain = args.custom_domain
#     output_file = args.output

#     # Debug: Show which credentials were loaded (without exposing sensitive data)
#     print('\n--- Configuration Loaded ---')
#     if connection_string:
#         print('✓ Connection string: Loaded from .env/args')
#     if account_name:
#         print(f'✓ Account name: {account_name}')
#     else:
#         print('✗ Account name: Not found')
#     if account_key:
#         print('✓ Account key: Loaded from .env/args')
#     else:
#         print('✗ Account key: Not found')
#     print(f'✓ Container: {container_name}')
#     print('---\n')

#     # Validate required settings - need either connection string OR account name + key
#     if not connection_string and (not account_name or not account_key):
#         print('ERROR: Azure credentials are required.')
#         print('Please provide either:')
#         print('  1. Connection string via --connection-string or wajo-azure-storage-connection-string in .env')
#         print('  2. Account name and key via --account-name/--account-key or wajo-azure-storage-account-name/key in .env')
#         print('\nMake sure your .env file contains:')
#         print('  wajo-azure-storage-account-name=your_account_name')
#         print('  wajo-azure-storage-account-key=your_account_key')
#         sys.exit(1)

#     # Extract account name from connection string if not provided
#     if not account_name and connection_string:
#         account_name = extract_account_name_from_connection_string(connection_string)

#     # Set custom domain if account name is available
#     if not custom_domain and account_name:
#         custom_domain = f"{account_name}.blob.core.windows.net"

#     print('Connecting to Azure Blob Storage...')
#     print(f'Container: {container_name}')
#     if account_name:
#         print(f'Account: {account_name}')

#     try:
#         # Connect to Azure Blob Storage using connection string or account name/key
#         if connection_string:
#             blob_service_client = BlobServiceClient.from_connection_string(connection_string)
#         else:
#             account_url = f"https://{account_name}.blob.core.windows.net"
#             blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)
        
#         container_client = blob_service_client.get_container_client(container_name)

#         # Check if container exists
#         if not container_client.exists():
#             print(f'ERROR: Container "{container_name}" does not exist')
#             sys.exit(1)

#         print('SUCCESS: Connected successfully!')
#         print('Scanning for videos...')

#         # Collect all results
#         results = []
#         session_folders = set()
        
#         # Dictionary to track session structure: {session_id: {'videos': bool, 'highlights': bool, 'videos_list': []}}
#         session_structure = {}

#         # List all blobs in the container - single pass to collect all data
#         blob_list = container_client.list_blobs(name_starts_with='sessions/')
        
#         for blob in blob_list:
#             blob_name = blob.name
            
#             # Extract session ID from path: sessions/<session_id>/...
#             parts = blob_name.split('/')
#             if len(parts) >= 2 and parts[0] == 'sessions':
#                 session_id = parts[1]
#                 session_folders.add(session_id)
                
#                 # Initialize session structure if not exists
#                 if session_id not in session_structure:
#                     session_structure[session_id] = {
#                         'videos': False,
#                         'highlights': False,
#                         'videos_list': []
#                     }
                
#                 # Check folder structure
#                 if len(parts) >= 3:
#                     if parts[2] == 'videos':
#                         session_structure[session_id]['videos'] = True
                        
#                         if len(parts) >= 4 and parts[3] == 'highlights':
#                             session_structure[session_id]['highlights'] = True
                            
#                             # Check if it's a video file matching the pattern
#                             filename = os.path.basename(blob_name)
#                             if filename.startswith('gc-') and filename.endswith('_with_overlay.mp4'):
#                                 session_structure[session_id]['videos_list'].append({
#                                     'blob_name': blob_name,
#                                     'filename': filename,
#                                     'blob': blob
#                                 })

#         print(f'Found {len(session_folders)} session folder(s)')

#         # Process each session
#         total_sessions = len(session_folders)
#         processed = 0
        
#         for session_id in sorted(session_folders):
#             processed += 1
#             if processed % 10 == 0 or processed == total_sessions:
#                 print(f'Processing session {processed}/{total_sessions}...')
            
#             # Get session data or use empty structure if not found
#             session_data = session_structure.get(session_id, {
#                 'videos': False,
#                 'highlights': False,
#                 'videos_list': []
#             })
            
#             process_session_data(
#                 container_name,
#                 session_id,
#                 session_data,
#                 results,
#                 account_name,
#                 custom_domain
#             )

#         # Write results to CSV
#         write_csv(results, output_file)

#         print(f'\nSUCCESS: Completed! Found {len(results)} video(s) across {len(session_folders)} session(s)')
#         print(f'Results saved to: {output_file}')

#     except AzureError as e:
#         print(f'ERROR: Azure Blob Storage error: {str(e)}')
#         sys.exit(1)
#     except Exception as e:
#         print(f'ERROR: Unexpected error: {str(e)}')
#         import traceback
#         traceback.print_exc()
#         sys.exit(1)

import json
import os


def update_trace_session_multilingual_data(match_data, session=None):
    """
    Update TraceSession multilingual data from match data
    """


    # Steps:
    """
    1. Get the en and he Team name from the match data.
    2. get the both the team's name in he and en from the match data.
    3. Update the Games and Teams name with the new names.
        i. First check that __model__.language_metadata is not empty. but if then try to find the team or games, using the both name like team.name=he_name or team.name=en_name.
        ii. if language_metadata field is not empty for that model then use this filed to find the existing team or game using both he and en name, to process the query use the following format:
            models.Q(language_metadata__en__<field_name>__exact=en_name) & models.Q(language_metadata__he__<field_name>__exact=he_name)
        iii. Now if Team or Game is found using the he value or en value and second value option is not presetent in the language_metadata field and present in match data then update the language_metadata field with the new names for that lanugage option.
        iv. if Team or Game is not found using the he_value or en_value in the model.field or language_metadata__[en/he]__<field_name>__exact=value then create a new team or game with the new names for that lanugage option. and if foudn for any case, then udpate the value for which the value is not present.\
    """


    try:
        # Get the en and he Team name from the match data.
        en_home_team_name = match_data.get("en", {}).get("Match_summary", {}).get("match_home_team", "")
        he_home_team_name = match_data.get("he", {}).get("Match_summary", {}).get("match_home_team", "")

        # Get the en and he Team name from the match data.
        en_away_team_name = match_data.get("en", {}).get("Match_summary", {}).get("match_away_team", "")
        he_away_team_name = match_data.get("he", {}).get("Match_summary", {}).get("match_away_team", "")

        # Get the en and he Game name from the match data.
        en_game_name = match_data.get("en", {}).get("Match_summary", {}).get("match_id", "")
        he_game_name = match_data.get("he", {}).get("Match_summary", {}).get("match_id", "")


        print(f"en_home_team_name: {en_home_team_name}")
        print(f"he_home_team_name: {he_home_team_name}")
        print(f"en_away_team_name: {en_away_team_name}")
        print(f"he_away_team_name: {he_away_team_name}")
        print(f"en_game_name: {en_game_name}")
        print(f"he_game_name: {he_game_name}")

    except Exception as e:
        print(f"Error updating TraceSession multilingual data: {e}")
    pass



if __name__ == '__main__':
    match_data = os.path.join(os.path.dirname(__file__), "tracevision", "data", "Gmae_Match_Detail Template_multilingual.json")
    with open(match_data, "r", encoding="utf-8") as f:
        match_data = json.load(f)
        
    update_trace_session_multilingual_data(match_data, session=None)

