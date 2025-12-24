#!/usr/bin/env python
"""
Automation script to process videos from Azure Blob Storage:
1. Read CSV rows where remark='found'
2. Download videos from Azure
3. Re-encode with H.264/AVC using ffmpeg via Docker
4. Rename old video with 'old_' prefix and upload new one
5. Update CSV with processing status
6. Clean up local files

Usage:
    # Using .env file (recommended)
    # Create a .env file with:
    #   wajo-azure-storage-account-name=your_account_name
    #   wajo-azure-storage-account-key=your_account_key
    python process_azure_videos.py --csv azure_videos_list.csv
    
    # Or use command-line arguments
    python process_azure_videos.py --csv azure_videos_list.csv --output processed_videos.csv --limit 10
"""

import argparse
import os
import sys
import csv
import tempfile
import subprocess
import shutil
import time
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError

try:
    from dotenv import load_dotenv
except ImportError:
    print("WARNING: python-dotenv not installed. Install it with: pip install python-dotenv")
    print("The script will continue but won't load .env file.")
    load_dotenv = None


def extract_account_name_from_connection_string(connection_string):
    """Extract account name from Azure connection string"""
    import re
    match = re.search(r'AccountName=([^;]+)', connection_string)
    return match.group(1) if match else None


def download_video_from_azure(blob_service_client, container_name, blob_path, local_path):
    """Download video from Azure Blob Storage"""
    try:
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Download blob with progress tracking
        file_size = 0
        chunk_size = 2 * 1024 * 1024  # 2MB chunks
        with open(local_path, 'wb') as download_file:
            download_stream = blob_client.download_blob()
            for chunk in download_stream.chunks():
                download_file.write(chunk)
                file_size += len(chunk)
        
        print(f'  ✓ Downloaded: {file_size / (1024*1024):.2f} MB')
        return True
    except Exception as e:
        print(f'  ✗ Download failed: {str(e)}')
        return False


def convert_video_with_docker(input_path, output_path, fps=30, container_name='wajo-app'):
    """Convert video to H.264/AVC using ffmpeg in existing running Docker container"""
    try:
        # Get absolute paths
        input_abs = os.path.abspath(input_path)
        output_abs = os.path.abspath(output_path)
        
        # Check if container is running
        check_cmd = ['sudo', 'docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}']
        check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
        
        found_container = None
        if container_name in check_result.stdout or check_result.stdout.strip():
            # Container found
            found_container = container_name
        else:
            # Try alternative container names
            alt_names = ['wajo-app', 'django', 'wajo-django']
            for alt_name in alt_names:
                check_cmd = ['sudo', 'docker', 'ps', '--filter', f'name={alt_name}', '--format', '{{.Names}}']
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                if check_result.stdout.strip():
                    # Get the actual container name from output
                    container_names = [name.strip() for name in check_result.stdout.strip().split('\n') if name.strip()]
                    if container_names:
                        found_container = container_names[0]
                        break
        
        if not found_container: 
            print(f'  ✗ Docker container not found. Please ensure a container (wajo-app, django, etc.) is running.')
            print(f'     Run: docker ps to see running containers')
            return False
        
        container_name = found_container
        
        # Since volumes are mounted (.:/app), we can access files directly
        # Convert absolute path to container path
        # Assuming the project root is mounted at /app
        project_root = os.path.abspath(os.path.dirname(__file__))
        
        # If input/output are in the project directory, use relative paths
        if input_abs.startswith(project_root):
            container_input = input_abs.replace(project_root, '/app').replace('\\', '/')
        else:
            # File is outside project, need to copy it
            # Use /app/temp in container
            temp_dir_in_container = '/app/temp'
            subprocess.run(
                ['sudo', 'docker', 'exec', container_name, 'mkdir', '-p', temp_dir_in_container],
                capture_output=True,
                timeout=10
            )
            input_filename = os.path.basename(input_abs)
            container_input = f'{temp_dir_in_container}/{input_filename}'
            # Copy file into container
            copy_in_cmd = ['sudo', 'docker', 'cp', input_abs, f'{container_name}:{container_input}']
            copy_result = subprocess.run(copy_in_cmd, capture_output=True, text=True, timeout=300)
            if copy_result.returncode != 0:
                print(f'  ✗ Failed to copy file to container: {copy_result.stderr}')
                return False
        
        if output_abs.startswith(project_root):
            container_output = output_abs.replace(project_root, '/app').replace('\\', '/')
        else:
            # Output outside project, use temp directory
            output_filename = os.path.basename(output_abs)
            container_output = f'/app/temp/{output_filename}'

        # FFmpeg command based on video_generator.py convert_to_browser_friendly
        ffmpeg_cmd = [
            'ffmpeg', '-loglevel', 'error', '-i', container_input,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-pix_fmt', 'yuv420p', '-profile:v', 'baseline', '-level', '3.1',
            '-movflags', '+faststart', '-vsync', 'cfr', '-r', str(int(fps)),
            '-an', '-f', 'mp4', '-y', container_output
        ]

        # Run ffmpeg in existing Docker container
        docker_cmd = ['sudo', 'docker', 'exec', container_name] + ffmpeg_cmd

        print(f'  → Running ffmpeg conversion in Docker container ({container_name})...')
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes timeout
        )

        if result.returncode == 0:
            # If output was in temp, copy it back
            if container_output.startswith('/app/temp'):
                copy_out_cmd = ['sudo', 'docker', 'cp', f'{container_name}:{container_output}', output_abs]
                copy_result = subprocess.run(copy_out_cmd, capture_output=True, text=True, timeout=300)
                if copy_result.returncode != 0:
                    print(f'  ✗ Failed to copy output from container: {copy_result.stderr}')
                    return False
                # Clean up temp files in container
                try:
                    subprocess.run(
                        ['sudo', 'docker', 'exec', container_name, 'rm', '-f', container_input, container_output],
                        capture_output=True,
                        timeout=10
                    )
                except:
                    pass
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                output_size = os.path.getsize(output_path)
                print(f'  ✓ Converted: {output_size / (1024*1024):.2f} MB')
                return True
            else:
                print(f'  ✗ Output file not found or empty')
                return False
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            print(f'  ✗ Conversion failed: {error_msg}')
            # Clean up input file in container if it was copied
            if container_input.startswith('/app/temp'):
                try:
                    subprocess.run(
                        ['sudo', 'docker', 'exec', container_name, 'rm', '-f', container_input],
                        capture_output=True,
                        timeout=10
                    )
                except:
                    pass
            return False

    except subprocess.TimeoutExpired:
        print(f'  ✗ Conversion timeout (exceeded 30 minutes)')
        return False
    except Exception as e:
        print(f'  ✗ Conversion error: {str(e)}')
        import traceback
        traceback.print_exc()
        return False


def rename_blob_in_azure(blob_service_client, container_name, old_blob_path, new_blob_path):
    """Rename blob in Azure by copying to new name and deleting old"""
    try:
        from azure.storage.blob import ContentSettings
        
        source_blob = blob_service_client.get_blob_client(container=container_name, blob=old_blob_path)
        dest_blob = blob_service_client.get_blob_client(container=container_name, blob=new_blob_path)

        # Get source blob properties to preserve content type
        source_props = source_blob.get_blob_properties()
        content_type = source_props.content_settings.content_type or 'video/mp4'
        
        # Copy blob to new location
        dest_blob.start_copy_from_url(source_blob.url)
        
        # Wait for copy to complete
        import time
        props = dest_blob.get_blob_properties()
        while props.copy.status == 'pending':
            time.sleep(1)
            props = dest_blob.get_blob_properties()
        
        if props.copy.status != 'success':
            print(f'  ✗ Rename failed: Copy status {props.copy.status}')
            return False

        # Set content type after copy to ensure it's video/mp4
        content_settings = ContentSettings(content_type=content_type)
        dest_blob.set_http_headers(content_settings=content_settings)

        # Delete old blob
        source_blob.delete_blob()
        print(f'  ✓ Renamed blob: {os.path.basename(old_blob_path)} → {os.path.basename(new_blob_path)} (content-type: {content_type})')
        return True

    except Exception as e:
        print(f'  ✗ Rename failed: {str(e)}')
        return False


def upload_video_to_azure(blob_service_client, container_name, blob_path, local_path):
    """Upload video to Azure Blob Storage with proper content type"""
    try:
        from azure.storage.blob import ContentSettings
        
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)
        
        file_size = os.path.getsize(local_path)
        
        # Set content type to video/mp4 for proper browser playback
        content_settings = ContentSettings(content_type='video/mp4')
        
        # Upload blob with content type
        with open(local_path, 'rb') as upload_file:
            blob_client.upload_blob(
                upload_file,
                overwrite=True,
                content_settings=content_settings
            )
        
        print(f'  ✓ Uploaded: {file_size / (1024*1024):.2f} MB (content-type: video/mp4)')
        return True

    except Exception as e:
        print(f'  ✗ Upload failed: {str(e)}')
        return False


def delete_old_video_from_azure(blob_service_client, container_name, old_blob_path):
    """Delete old_ prefixed video from Azure Blob Storage"""
    try:
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=old_blob_path)
        
        # Check if blob exists before deleting
        if blob_client.exists():
            blob_client.delete_blob()
            print(f'  ✓ Deleted old video: {os.path.basename(old_blob_path)}')
            return True
        else:
            print(f'  ⚠ Old video not found (may already be deleted): {os.path.basename(old_blob_path)}')
            return True  # Consider it success if already deleted

    except Exception as e:
        print(f'  ✗ Delete old video failed: {str(e)}')
        return False


def process_video_row(row, blob_service_client, container_name, temp_dir, row_index, total_rows):
    """Process a single video row"""
    sr_no = row.get('Sr.No.', '')
    content_path = row.get('content_path', '')
    content_name = row.get('content_name', '')
    content_url = row.get('content_url', '')

    print(f'\n[{row_index}/{total_rows}] Processing: {content_name}')

    # Initialize status fields
    status = {
        'video_download_status': '',
        'video_download_error': '',
        'video_process_status': '',
        'video_process_error': '',
        'video_rename_status': '',
        'video_rename_error': '',
        'video_upload_status': '',
        'video_upload_error': '',
        'old_video_delete_status': '',
        'old_video_delete_error': '',
        'overall_status': 'pending'
    }

    # Step 1: Download video
    print('  Step 1: Downloading from Azure...')
    local_input_path = os.path.join(temp_dir, f'input_{sr_no}_{content_name}')
    
    if not download_video_from_azure(blob_service_client, container_name, content_path, local_input_path):
        status['video_download_status'] = 'failed'
        status['video_download_error'] = 'Download failed'
        status['overall_status'] = 'failed'
        return status

    status['video_download_status'] = 'completed'

    # Step 2: Convert video
    print('  Step 2: Converting to H.264/AVC...')
    local_output_path = os.path.join(temp_dir, f'output_{sr_no}_{content_name}')

    # Try to get FPS from video (default to 30)
    fps = 30
    try:
        # Use ffprobe to get FPS if available
        probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                     '-show_entries', 'stream=r_frame_rate', '-of', 'default=noprint_wrappers=1:nokey=1', local_input_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            num, den = map(int, result.stdout.strip().split('/'))
            fps = num / den if den > 0 else 30
    except:
        pass  # Use default FPS

    if not convert_video_with_docker(local_input_path, local_output_path, fps):
        status['video_process_status'] = 'failed'
        status['video_process_error'] = 'Conversion failed'
        status['overall_status'] = 'failed'
        # Clean up immediately on failure
        cleanup_local_files([local_input_path, local_output_path])
        return status

    status['video_process_status'] = 'completed'

    # Step 3: Rename old blob with 'old_' prefix
    print('  Step 3: Renaming old video in Azure...')
    old_blob_path = content_path
    old_blob_name = os.path.basename(old_blob_path)
    old_blob_dir = os.path.dirname(old_blob_path)
    new_old_blob_name = f'old_{old_blob_name}'
    new_old_blob_path = os.path.join(old_blob_dir, new_old_blob_name).replace('\\', '/')

    if not rename_blob_in_azure(blob_service_client, container_name, old_blob_path, new_old_blob_path):
        status['video_rename_status'] = 'failed'
        status['video_rename_error'] = 'Rename failed'
        status['overall_status'] = 'failed'
        # Clean up immediately on failure
        cleanup_local_files([local_input_path, local_output_path])
        return status

    status['video_rename_status'] = 'completed'

    # Step 4: Upload new video
    print('  Step 4: Uploading new video to Azure...')
    if not upload_video_to_azure(blob_service_client, container_name, content_path, local_output_path):
        status['video_upload_status'] = 'failed'
        status['video_upload_error'] = 'Upload failed'
        status['overall_status'] = 'failed'
        # Clean up immediately on failure
        cleanup_local_files([local_input_path, local_output_path])
        return status

    status['video_upload_status'] = 'completed'

    # Step 5: Delete old video from Azure
    print('  Step 5: Deleting old video from Azure...')
    if not delete_old_video_from_azure(blob_service_client, container_name, new_old_blob_path):
        status['old_video_delete_status'] = 'failed'
        status['old_video_delete_error'] = 'Delete failed'
        # Don't fail overall status if old video deletion fails
        print(f'  ⚠ Warning: Old video deletion failed, but new video is uploaded successfully')
    else:
        status['old_video_delete_status'] = 'completed'

    status['overall_status'] = 'completed'

    # Step 6: Clean up local files immediately after successful upload
    print('  Step 6: Cleaning up local files...')
    cleanup_local_files([local_input_path, local_output_path])

    print(f'  ✓ Successfully processed: {content_name}')
    return status


def cleanup_local_files(file_paths):
    """Clean up local files immediately"""
    for f in file_paths:
        if os.path.exists(f):
            try:
                file_size = os.path.getsize(f) / (1024*1024)  # Size in MB
                os.remove(f)
                print(f'  ✓ Removed: {os.path.basename(f)} ({file_size:.2f} MB freed)')
            except Exception as e:
                print(f'  ⚠ Could not remove {os.path.basename(f)}: {e}')


def save_csv_incremental(csv_path, all_rows, fieldnames):
    """Save CSV file incrementally after each video"""
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        return True
    except Exception as e:
        print(f'  ⚠ Could not save CSV: {e}')
        return False


def is_video_already_processed(row):
    """Check if video is already processed successfully"""
    overall_status = row.get('overall_status', '').lower()
    return overall_status == 'completed'


def main():
    # Load environment variables from .env file if dotenv is available
    if load_dotenv:
        # Try to load .env file from script directory first
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
            print(f'✓ Loaded environment variables from: {env_path}')
        else:
            # Try loading from current working directory
            cwd_env = os.path.join(os.getcwd(), '.env')
            if os.path.exists(cwd_env):
                load_dotenv(cwd_env, override=True)
                print(f'✓ Loaded environment variables from: {cwd_env}')
            else:
                # Try default load_dotenv() which searches in current directory and parent directories
                loaded = load_dotenv(override=True)
                if loaded:
                    print('✓ Loaded environment variables from .env file')
                else:
                    print('⚠ No .env file found. Using system environment variables or command-line arguments.')
    else:
        print('⚠ python-dotenv not installed. Using system environment variables or command-line arguments.')
    
    parser = argparse.ArgumentParser(
        description='Process videos from Azure Blob Storage: download, re-encode, and re-upload'
    )
    parser.add_argument(
        '--csv',
        type=str,
        required=True,
        help='Input CSV file path'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output CSV file path (default: updates input file)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of videos to process (for testing)'
    )
    parser.add_argument(
        '--start-from',
        type=int,
        default=None,
        help='Start processing from video number (e.g., --start-from 50 will skip first 49 videos)'
    )
    parser.add_argument(
        '--connection-string',
        type=str,
        default=None,
        help='Azure Storage connection string (or set wajo-azure-storage-connection-string in .env)'
    )
    parser.add_argument(
        '--account-name',
        type=str,
        default=None,
        help='Azure Storage account name (or set wajo-azure-storage-account-name in .env)'
    )
    parser.add_argument(
        '--account-key',
        type=str,
        default=None,
        help='Azure Storage account key (or set wajo-azure-storage-account-key in .env)'
    )
    parser.add_argument(
        '--container',
        type=str,
        default=None,
        help='Azure container name (default: media, or set AZURE_CONTAINER_NAME in .env)'
    )

    args = parser.parse_args()

    # Get configuration from args or environment variables (loaded from .env)
    # Priority: command-line args > environment variables > defaults
    connection_string = args.connection_string or os.environ.get('wajo-azure-storage-connection-string')
    account_name = args.account_name or os.environ.get('wajo-azure-storage-account-name')
    account_key = args.account_key or os.environ.get('wajo-azure-storage-account-key')
    container_name = args.container or os.environ.get('AZURE_CONTAINER_NAME', 'media')

    # Debug: Show which credentials were loaded (without exposing sensitive data)
    print('\n--- Configuration Loaded ---')
    if connection_string:
        print('✓ Connection string: Loaded from .env/args')
    if account_name:
        print(f'✓ Account name: {account_name}')
    else:
        print('✗ Account name: Not found')
    if account_key:
        print('✓ Account key: Loaded from .env/args')
    else:
        print('✗ Account key: Not found')
    print(f'✓ Container: {container_name}')
    print('---\n')

    # Validate required settings - need either connection string OR account name + key
    if not connection_string and (not account_name or not account_key):
        print('ERROR: Azure credentials are required.')
        print('Please provide either:')
        print('  1. Connection string via --connection-string or wajo-azure-storage-connection-string in .env')
        print('  2. Account name and key via --account-name/--account-key or wajo-azure-storage-account-name/key in .env')
        print('\nMake sure your .env file contains:')
        print('  wajo-azure-storage-account-name=your_account_name')
        print('  wajo-azure-storage-account-key=your_account_key')
        sys.exit(1)

    # Extract account name from connection string if not provided
    if not account_name and connection_string:
        account_name = extract_account_name_from_connection_string(connection_string)

    print('Connecting to Azure Blob Storage...')
    print(f'Container: {container_name}')
    if account_name:
        print(f'Account: {account_name}')

    try:
        # Connect to Azure Blob Storage using connection string or account name/key
        if connection_string:
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        else:
            account_url = f"https://{account_name}.blob.core.windows.net"
            blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)
        
        container_client = blob_service_client.get_container_client(container_name)

        # Check if container exists
        if not container_client.exists():
            print(f'ERROR: Container "{container_name}" does not exist')
            sys.exit(1)

        print('SUCCESS: Connected successfully!')
    except AzureError as e:
        print(f'ERROR: Azure Blob Storage error: {str(e)}')
        sys.exit(1)
    except Exception as e:
        print(f'ERROR: Failed to connect to Azure: {str(e)}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Read CSV
    csv_path = args.csv
    if not os.path.exists(csv_path):
        print(f'ERROR: CSV file not found: {csv_path}')
        sys.exit(1)

    print(f'\nReading CSV: {csv_path}')
    
    # Read all rows from CSV first
    all_rows = []
    fieldnames = None
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        all_rows = list(reader)

    # Add status columns if not present
    status_columns = [
        'video_download_status', 'video_download_error',
        'video_process_status', 'video_process_error',
        'video_rename_status', 'video_rename_error',
        'video_upload_status', 'video_upload_error',
        'old_video_delete_status', 'old_video_delete_error',
        'overall_status'
    ]
    for col in status_columns:
        if col not in fieldnames:
            fieldnames.append(col)
            # Initialize missing columns for existing rows
            for row in all_rows:
                if col not in row:
                    row[col] = ''

    # Filter rows to process (remark='found' and not already completed)
    rows_to_process = []
    for row in all_rows:
        if row.get('remark', '').lower() == 'found':
            if not is_video_already_processed(row):
                rows_to_process.append(row)
            else:
                print(f'  ⊘ Skipping already processed: {row.get("content_name", "N/A")}')

    total_rows = len(rows_to_process)
    already_processed_count = len([r for r in all_rows if r.get("remark", "").lower() == "found" and is_video_already_processed(r)])
    print(f'Found {total_rows} videos to process (remark="found" and not completed)')
    print(f'Skipped {already_processed_count} already processed videos')

    # Apply start-from filter (skip first N videos)
    if args.start_from is not None and args.start_from > 1:
        if args.start_from > len(rows_to_process):
            print(f'WARNING: --start-from {args.start_from} is greater than available videos ({len(rows_to_process)})')
            print('No videos to process.')
            return
        rows_to_process = rows_to_process[args.start_from - 1:]
        print(f'Starting from video #{args.start_from} (skipped first {args.start_from - 1} videos)')

    # Apply limit filter
    if args.limit:
        rows_to_process = rows_to_process[:args.limit]
        print(f'Limited to {len(rows_to_process)} videos (--limit={args.limit})')

    if not rows_to_process:
        print('No videos to process.')
        return

    # Set output path
    output_path = args.output or csv_path

    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix='video_process_')
    print(f'Using temp directory: {temp_dir}')

    try:
        # Process each video
        processed_count = 0
        failed_count = 0
        skipped_count = 0

        for idx, row in enumerate(rows_to_process, start=1):
            try:
                # Check if already processed (double-check)
                if is_video_already_processed(row):
                    skipped_count += 1
                    print(f'\n[{idx}/{len(rows_to_process)}] ⊘ Skipping already processed: {row.get("content_name", "N/A")}')
                    continue

                status = process_video_row(
                    row, blob_service_client, container_name, temp_dir, idx, len(rows_to_process)
                )

                # Update row with status
                row.update(status)
                processed_count += 1

                if status['overall_status'] == 'failed':
                    failed_count += 1

                # Save CSV incrementally after each video
                print(f'  → Saving progress to CSV...')
                if save_csv_incremental(output_path, all_rows, fieldnames):
                    print(f'  ✓ Progress saved')
                else:
                    print(f'  ⚠ Failed to save progress')

            except KeyboardInterrupt:
                print('\n\n⚠ Process interrupted by user')
                print(f'  Saving current progress...')
                save_csv_incremental(output_path, all_rows, fieldnames)
                print(f'  Progress saved. You can resume later.')
                break
            except Exception as e:
                print(f'\n  ✗ Unexpected error: {str(e)}')
                row.update({
                    'overall_status': 'error',
                    'video_download_error': str(e) if not row.get('video_download_error') else row.get('video_download_error')
                })
                failed_count += 1
                # Save progress even on error
                save_csv_incremental(output_path, all_rows, fieldnames)

        # Final save
        print(f'\nSaving final results to: {output_path}')
        save_csv_incremental(output_path, all_rows, fieldnames)

        print(f'\nSUCCESS: Processing complete!')
        print(f'  Total processed: {processed_count}')
        print(f'  Successful: {processed_count - failed_count}')
        print(f'  Failed: {failed_count}')
        print(f'  Skipped: {skipped_count}')
        print(f'  Results saved to: {output_path}')

    except KeyboardInterrupt:
        print('\n\n⚠ Process interrupted by user')
    except AzureError as e:
        print(f'\nERROR: Azure Blob Storage error: {str(e)}')
    except Exception as e:
        print(f'\nERROR: Unexpected error: {str(e)}')
        import traceback
        traceback.print_exc()
    finally:
        # Clean up temp directory
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f'\n✓ Cleaned up temp directory: {temp_dir}')
            except Exception as e:
                print(f'\n⚠ Could not clean up temp directory: {e}')


if __name__ == '__main__':
    main()

