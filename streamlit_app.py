#!/usr/bin/env python3
"""
YouTube Shorts Channel Manager & Script Generator - Streamlit Web Version

Dependencies: 
  pip install streamlit streamlit-authenticator google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2

Setup:
  1. Set environment variable: set ANTHROPIC_API_KEY=your_key_here (Windows) or export ANTHROPIC_API_KEY="your_key_here" (Mac/Linux)
  2. Google Drive API Setup:
     a) Go to https://console.cloud.google.com/
     b) Create a new project or select existing one
     c) Enable the Google Drive API
     d) Create credentials (OAuth 2.0 Client ID) for "Desktop application"
     e) Download the credentials JSON file and save it as "credentials.json" in the same folder as this script
  3. Run: streamlit run streamlit_app.py
  
Features:
  • Web-based interface accessible from any browser
  • Password protection for security
  • All files stored on Google Drive for real-time collaboration
  • Automatic sync - changes are immediately visible to all users
  • Creates a "YouTube Shorts Manager" folder in your Google Drive

Usage:
  Visit the website, enter the password, and start generating shorts!
"""

# Version information
APP_VERSION = "2.7.2"
VERSION_DATE = "2024-12-11"
VERSION_NOTES = "Fixed within-session duplicates by updating banned list after each generation"

import streamlit as st
import os
import json
import uuid
import requests
import threading
from typing import Dict, List, Set, Optional, Any
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import time
import re
from datetime import datetime, timedelta
from src.utils.similarity_checker import SimilarityChecker

# Page configuration
st.set_page_config(
    page_title="YouTube Shorts Manager",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import your existing classes (they work the same in Streamlit)
class GoogleDriveManager:
    """Handles all Google Drive operations for file storage."""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    def __init__(self):
        self.service = None
        self.folder_id = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Drive API."""
        creds = None
        
        try:
            # Try to get credentials from Streamlit secrets first
            if 'GOOGLE_CREDENTIALS' in st.secrets:
                import json
                # Handle multiline JSON from secrets
                creds_str = st.secrets['GOOGLE_CREDENTIALS']
                # Remove any control characters that might be in the multiline string
                creds_str = creds_str.replace('\n', '').replace('\r', '').replace('\t', '')
                creds_info = json.loads(creds_str)
                creds = Credentials.from_authorized_user_info(creds_info, self.SCOPES)
            
            # Fallback to local files for development
            elif os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            
            # If no credentials available, try to create them
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Try credentials from secrets first
                    if 'GOOGLE_CLIENT_CONFIG' in st.secrets:
                        import json
                        client_config = json.loads(st.secrets['GOOGLE_CLIENT_CONFIG'])
                        flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                        
                        # For Streamlit Cloud, we'll need a different auth flow
                        st.error("Google Drive authentication required. Please contact admin to setup credentials.")
                        return False
                    
                    elif os.path.exists('credentials.json'):
                        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                        creds = flow.run_local_server(port=8080, open_browser=True)
                        
                        # Save the credentials for the next run
                        with open('token.json', 'w') as token:
                            token.write(creds.to_json())
                    else:
                        st.error("Google Drive credentials not configured. Please contact admin.")
                        return False
            
            self.service = build('drive', 'v3', credentials=creds)
            self.setup_app_folder()
            return True
            
        except Exception as e:
            st.error(f"Failed to authenticate with Google Drive: {str(e)}")
            return False
    
    def setup_app_folder(self):
        """Create or find the app folder on Google Drive."""
        try:
            # Search for existing folder
            results = self.service.files().list(
                q="name='YouTube Shorts Manager' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                self.folder_id = folders[0]['id']
            else:
                # Create new folder
                folder_metadata = {
                    'name': 'YouTube Shorts Manager',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(body=folder_metadata, fields='id').execute()
                self.folder_id = folder.get('id')
                
        except Exception as e:
            st.error(f"Failed to setup Google Drive folder: {str(e)}")
    
    def read_file(self, filename: str, parent_folder_id: str = None) -> str:
        """Read a file from Google Drive."""
        try:
            if parent_folder_id is None:
                parent_folder_id = self.folder_id
                
            # Search for the file (exclude trashed files)
            results = self.service.files().list(
                q=f"name='{filename}' and parents='{parent_folder_id}' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                return ""  # File doesn't exist yet
            
            file_id = files[0]['id']
            
            # Download file content
            request = self.service.files().get_media(fileId=file_id)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_io.seek(0)
            return file_io.read().decode('utf-8')
            
        except Exception as e:
            return ""
    
    def write_file(self, filename: str, content: str, parent_folder_id: str = None):
        """Write a file to Google Drive."""
        try:
            if parent_folder_id is None:
                parent_folder_id = self.folder_id
                
            # Check if file already exists (exclude trashed files)
            results = self.service.files().list(
                q=f"name='{filename}' and parents='{parent_folder_id}' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            
            # Prepare content
            media = MediaIoBaseUpload(
                io.BytesIO(content.encode('utf-8')),
                mimetype='text/plain',
                resumable=True
            )
            
            if files:
                # Update existing file
                file_id = files[0]['id']
                self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
            else:
                # Create new file
                file_metadata = {
                    'name': filename,
                    'parents': [parent_folder_id]
                }
                self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                
        except Exception as e:
            st.error(f"Failed to save {filename}: {str(e)}")
    
    def append_to_file(self, filename: str, content: str, parent_folder_id: str = None):
        """Append content to a file on Google Drive."""
        existing_content = self.read_file(filename, parent_folder_id)
        new_content = existing_content + content
        self.write_file(filename, new_content, parent_folder_id)
    
    def get_or_create_channel_folder(self, channel_name: str) -> str:
        """Get or create a folder for a specific channel."""
        try:
            # Search for existing channel folder (exclude trashed folders)
            results = self.service.files().list(
                q=f"name='{channel_name}' and parents='{self.folder_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                return folders[0]['id']
            else:
                # Create new channel folder
                folder_metadata = {
                    'name': channel_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [self.folder_id]
                }
                folder = self.service.files().create(body=folder_metadata, fields='id').execute()
                return folder.get('id')
                
        except Exception as e:
            st.error(f"Error getting/creating channel folder for {channel_name}: {str(e)}")
            return self.folder_id  # Fallback to main folder
    
    def get_or_create_backup_folder(self, channel_folder_id: str, channel_name: str) -> str:
        """Get or create a backup folder within a channel folder."""
        try:
            backup_folder_name = "Backups"
            
            # Validate that we have a service connection
            if not self.service:
                st.error(f"Google Drive service not available for backup folder creation")
                return None
            
            # Search for existing backup folder
            results = self.service.files().list(
                q=f"name='{backup_folder_name}' and parents='{channel_folder_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                backup_folder_id = folders[0]['id']
                st.success(f"✅ Found existing backup folder for {channel_name}")
                return backup_folder_id
            else:
                # Create new backup folder
                st.info(f"📁 Creating backup folder for {channel_name}...")
                folder_metadata = {
                    'name': backup_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [channel_folder_id]
                }
                folder = self.service.files().create(body=folder_metadata, fields='id').execute()
                backup_folder_id = folder.get('id')
                
                if backup_folder_id:
                    st.success(f"✅ Created backup folder for {channel_name}")
                    return backup_folder_id
                else:
                    st.error(f"Failed to get backup folder ID for {channel_name}")
                    return None
                
        except Exception as e:
            st.error(f"Error getting/creating backup folder for {channel_name}: {str(e)}")
            return None  # Return None instead of fallback to indicate failure


class ClaudeClient:
    """Handles all Claude API interactions."""
    
    def __init__(self):
        # Try Streamlit secrets first, then environment variable
        self.api_key = st.secrets.get('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in Streamlit secrets or environment variables")
        
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
    
    def generate_script(self, prompt: str, session_id: str) -> Dict[str, Any]:
        """Generate a YouTube short script using Claude API with retry logic."""
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # Retry logic for network errors
        max_retries = 3
        timeout = 60  # Increased from 30 to 60 seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract token usage if available
                    usage = data.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    total_tokens = input_tokens + output_tokens
                    
                    return {
                        "success": True,
                        "content": data["content"][0]["text"],
                        "session_id": session_id,
                        "token_usage": {
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": total_tokens
                        }
                    }
                else:
                    # If not a timeout error, don't retry
                    if response.status_code != 504:
                        return {
                            "success": False,
                            "error": f"API Error {response.status_code}: {response.text}"
                        }
                    # Otherwise, continue to retry
                    
            except requests.exceptions.Timeout as e:
                # Timeout error - retry
                if attempt < max_retries - 1:
                    st.warning(f"⏱️ Request timed out. Retrying... (Attempt {attempt + 2}/{max_retries})")
                    time.sleep(2)  # Wait 2 seconds before retrying
                    continue
                else:
                    return {
                        "success": False,
                        "error": f"Network timeout after {max_retries} attempts. The API is taking too long to respond. Please try again later."
                    }
                    
            except requests.exceptions.RequestException as e:
                # Other network errors - retry
                if attempt < max_retries - 1:
                    st.warning(f"🔄 Network error. Retrying... (Attempt {attempt + 2}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    return {
                        "success": False,
                        "error": f"Network error after {max_retries} attempts: {str(e)}"
                    }
                    
            except Exception as e:
                # Unexpected errors - don't retry
                return {
                    "success": False,
                    "error": f"Unexpected error: {str(e)}"
                }
        
        # Should not reach here, but just in case
        return {
            "success": False,
            "error": "Failed to generate script after all retries"
        }


class ChannelManager:
    """Manages channel definitions and per-channel title tracking using Google Drive."""
    
    def __init__(self, drive_manager: GoogleDriveManager):
        self.drive_manager = drive_manager
        self.channels_file = "channels.json"
        self.channels = self.load_channels()
    
    def load_channels(self) -> Dict[str, str]:
        """Load channel definitions from Google Drive channels.json."""
        try:
            # Skip loading if Drive manager isn't ready
            if not self.drive_manager or not self.drive_manager.service:
                return {}
                
            content = self.drive_manager.read_file(self.channels_file)
            if content:
                # Clean up content in case of formatting issues
                content = content.strip()
                if not content:
                    return {}
                    
                channels = json.loads(content)
                return channels
            else:
                # Try to create initial channels file
                initial_channels = {}
                self.channels = initial_channels
                self.save_channels()
                return initial_channels
        except json.JSONDecodeError as e:
            # Only show error to admins
            return {}
        except Exception as e:
            # Silent fail for default users
            return {}
        return {}
    
    def save_channels(self):
        """Save channel definitions to Google Drive channels.json."""
        try:
            content = json.dumps(self.channels, indent=2, ensure_ascii=False)
            self.drive_manager.write_file(self.channels_file, content)
        except Exception as e:
            st.error(f"Failed to save channels to Google Drive: {str(e)}")
    
    def add_channel(self, name: str, base_prompt: str):
        """Add a new channel with its base prompt."""
        self.channels[name] = base_prompt
        self.save_channels()
    
    def get_channel_names(self) -> List[str]:
        """Get list of all channel names."""
        return list(self.channels.keys())
    
    def get_channel_prompt(self, name: str) -> str:
        """Get base prompt for a specific channel."""
        return self.channels.get(name, "")
    
    def update_channel_prompt(self, name: str, new_prompt: str):
        """Update the base prompt for an existing channel."""
        if name in self.channels:
            self.channels[name] = new_prompt
            self.save_channels()
            return True
        return False
    
    def delete_channel(self, name: str):
        """Delete a channel from the dropdown (removes from channels.json only)."""
        if name in self.channels:
            del self.channels[name]
            self.save_channels()
            return True
        return False
    
    def get_used_titles(self, channel_name: str, force_refresh: bool = False) -> Set[str]:
        """Load used titles for a channel from Google Drive channel folder."""
        filename = f"titles_{channel_name.lower()}.txt"
        titles = set()
        
        # Cache key for this channel's titles
        cache_key = f"cached_titles_{channel_name}"
        
        # Use cache unless force_refresh is True
        if not force_refresh and cache_key in st.session_state:
            return st.session_state[cache_key]
        
        try:
            # Get or create the channel folder
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            content = self.drive_manager.read_file(filename, channel_folder_id)
            if content:
                titles = {line.strip() for line in content.split('\n') if line.strip()}
                # Update cache
                st.session_state[cache_key] = titles
        except Exception as e:
            pass
        return titles
    
    def get_used_titles_ordered(self, channel_name: str, force_refresh: bool = False) -> List[str]:
        """Load used titles for a channel in the same order as they appear in the file."""
        filename = f"titles_{channel_name.lower()}.txt"
        
        try:
            # Get or create the channel folder
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            content = self.drive_manager.read_file(filename, channel_folder_id)
            if content:
                # Return as list to preserve order from the file
                titles_list = [line.strip() for line in content.split('\n') if line.strip()]
                return titles_list
        except Exception as e:
            pass
        return []
    
    def add_title(self, channel_name: str, title: str):
        """Add a new title with similarity checking."""
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            # Check for similar existing titles first
            existing_titles = self.get_used_titles(channel_name, force_refresh=False)
            is_dup, similar_to = SimilarityChecker.is_duplicate_title(title, existing_titles)
            
            if is_dup:
                # Don't add duplicate, but don't show error (silent skip)
                return False
            
            # Get or create the channel folder
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            self.drive_manager.append_to_file(filename, f"{title}\n", channel_folder_id)
            
            # Update cache immediately after adding
            cache_key = f"cached_titles_{channel_name}"
            if cache_key in st.session_state:
                st.session_state[cache_key].add(title)
            else:
                st.session_state[cache_key] = {title}
            
            return True
                
        except Exception as e:
            st.error(f"Failed to save title for {channel_name} to Google Drive: {str(e)}")
            return False
    
    def bulk_add_titles(self, channel_name: str, titles_list: list):
        """Bulk add multiple titles with similarity-based duplicate detection."""
        if not titles_list:
            return 0, 0
            
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            # Get existing titles to avoid duplicates
            existing_titles = self.get_used_titles(channel_name, force_refresh=False)
            
            # Use similarity checker to filter duplicates
            unique_titles, duplicates = SimilarityChecker.filter_duplicate_titles(
                titles_list, existing_titles
            )
            
            # Process titles in batches to prevent memory issues
            batch_size = 100
            total_added = 0
            
            for i in range(0, len(unique_titles), batch_size):
                batch = unique_titles[i:i + batch_size]
                
                # Write this batch to Google Drive if there are new titles
                if batch:
                    channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
                    titles_content = "\n".join(batch) + "\n"
                    self.drive_manager.append_to_file(filename, titles_content, channel_folder_id)
                    total_added += len(batch)
                    
                    # Update cache with new titles from this batch
                    cache_key = f"cached_titles_{channel_name}"
                    if cache_key in st.session_state:
                        st.session_state[cache_key].update(batch)
                    else:
                        st.session_state[cache_key] = set(batch)
            
            return total_added, len(duplicates)
            
        except Exception as e:
            st.error(f"Failed to bulk add titles for {channel_name} to Google Drive: {str(e)}")
            return 0, 0
    
    def delete_title(self, channel_name: str, title_to_delete: str):
        """Delete a specific title from a channel's Google Drive folder while preserving file order."""
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            # Get the file content to preserve order
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            content = self.drive_manager.read_file(filename, channel_folder_id)
            
            if not content:
                return False, f"No titles file found for {channel_name}"
            
            # Split into lines and preserve order
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            if title_to_delete not in lines:
                return False, f"Title '{title_to_delete}' not found"
            
            # Remove the title while preserving order
            lines.remove(title_to_delete)
            
            # Rewrite the file with preserved order
            new_content = "\n".join(lines) + ("\n" if lines else "")
            self.drive_manager.write_file(filename, new_content, channel_folder_id)
            
            # Clear cache to force refresh
            cache_key = f"cached_titles_{channel_name}"
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            
            return True, f"Title '{title_to_delete}' deleted successfully"
            
        except Exception as e:
            import traceback
            return False, f"Failed to delete title: {str(e)}\n{traceback.format_exc()}"
    
    def bulk_delete_titles(self, channel_name: str, titles_to_delete: list):
        """Delete multiple titles from a channel's Google Drive folder."""
        if not titles_to_delete:
            return 0, 0
            
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            # Get all current titles
            current_titles = self.get_used_titles(channel_name, force_refresh=True)
            
            # Count found and not found titles
            deleted_count = 0
            not_found_count = 0
            
            for title in titles_to_delete:
                title = title.strip()
                if title in current_titles:
                    current_titles.remove(title)
                    deleted_count += 1
                else:
                    not_found_count += 1
            
            if deleted_count > 0:
                # Rewrite the entire file without the deleted titles
                channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
                new_content = "\n".join(sorted(current_titles)) + ("\n" if current_titles else "")
                self.drive_manager.write_file(filename, new_content, channel_folder_id)
                
                # Update cache
                cache_key = f"cached_titles_{channel_name}"
                if cache_key in st.session_state:
                    for title in titles_to_delete:
                        st.session_state[cache_key].discard(title.strip())
            
            return deleted_count, not_found_count
            
        except Exception as e:
            st.error(f"Failed to bulk delete titles for {channel_name}: {str(e)}")
            return 0, 0
    
    def save_script(self, channel_name: str, content: str, session_id: str, user_name: str = None):
        """Save the full generated script to a channel's Google Drive folder."""
        filename = f"saved_scripts_{channel_name.lower()}.txt"
        try:
            # Get or create the channel folder
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            
            # Add user attribution and timestamp to the script
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            attribution = f"Created by: {user_name if user_name else 'Unknown User'} on {timestamp}\n"
            separator = "="*50 + "\n\n"
            
            script_content = attribution + content + "\n\n" + separator + "\n"  # Add attribution, content, and separator
            self.drive_manager.append_to_file(filename, script_content, channel_folder_id)
        except Exception as e:
            st.error(f"Failed to save script for {channel_name} to Google Drive: {str(e)}")
    
    def clear_titles(self, channel_name: str):
        """Clear all titles for a channel."""
        try:
            if not self.drive_manager or not hasattr(self.drive_manager, 'get_or_create_channel_folder'):
                st.warning("Google Drive not available")
                return False
                
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            filename = f"titles_{channel_name.lower()}.txt"
            self.drive_manager.write_file(filename, "", channel_folder_id)
            
            # Clear cache
            cache_key = f"cached_titles_{channel_name}"
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            
            return True
        except Exception as e:
            st.error(f"Failed to clear titles: {str(e)}")
            return False
    
    def clear_scripts(self, channel_name: str):
        """Clear all scripts for a channel."""
        try:
            if not self.drive_manager or not hasattr(self.drive_manager, 'get_or_create_channel_folder'):
                st.warning("Google Drive not available")
                return False
                
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            filename = f"saved_scripts_{channel_name.lower()}.txt"
            self.drive_manager.write_file(filename, "", channel_folder_id)
            return True
        except Exception as e:
            st.error(f"Failed to clear scripts: {str(e)}")
            return False
    
    def backup_channel_files(self, channel_name: str):
        """Create backup of channel files (titles and scripts)."""
        try:
            # Check if drive_manager exists and is properly initialized
            if not hasattr(self, 'drive_manager') or self.drive_manager is None:
                st.warning("Google Drive not available for backup")
                return False
                
            if not hasattr(self.drive_manager, 'service') or self.drive_manager.service is None:
                st.warning("Google Drive service not available for backup")
                return False
                
            if not hasattr(self.drive_manager, 'get_or_create_channel_folder'):
                st.warning("Google Drive folder management not available for backup")
                return False
                
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            if not channel_folder_id:
                st.warning("Could not access channel folder for backup")
                return False
            
            # Get or create backup folder within the channel folder
            backup_folder_id = self.drive_manager.get_or_create_backup_folder(channel_folder_id, channel_name)
            if not backup_folder_id:
                st.error("❌ Failed to create or access backup folder - backups will be stored in main channel folder")
                backup_folder_id = channel_folder_id  # Fallback to main channel folder
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup titles file
            titles_filename = f"titles_{channel_name.lower()}.txt"
            titles_content = self.drive_manager.read_file(titles_filename, channel_folder_id)
            if titles_content:
                backup_titles = f"backup_titles_{channel_name.lower()}_{timestamp}.txt"
                self.drive_manager.write_file(backup_titles, titles_content, backup_folder_id)
            
            # Backup scripts file
            scripts_filename = f"saved_scripts_{channel_name.lower()}.txt"
            scripts_content = self.drive_manager.read_file(scripts_filename, channel_folder_id)
            if scripts_content:
                backup_scripts = f"backup_scripts_{channel_name.lower()}_{timestamp}.txt"
                self.drive_manager.write_file(backup_scripts, scripts_content, backup_folder_id)
            
            return True
        except AttributeError as e:
            st.warning(f"Backup service not available (missing attribute): {str(e)}")
            return False
        except Exception as e:
            st.error(f"Failed to backup {channel_name}: {str(e)}")
            return False


def extract_titles_from_response(content: str) -> List[str]:
    """Extract ALL titles from the AI response."""
    titles_found = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        # Look for "TITLE:" or "TITLE" format (case insensitive)
        line_upper = line.upper()
        if line_upper.startswith('TITLE:'):
            # Extract everything after "TITLE:"
            title = line[6:].strip()  # Remove "TITLE:" and whitespace
        elif line_upper.startswith('TITLE '):
            # Extract everything after "TITLE "
            title = line[6:].strip()  # Remove "TITLE " and whitespace
        elif line_upper.startswith('TITLE') and len(line) > 5 and not line[5].isalpha():
            # Handle "TITLE" followed by non-letter (like numbers, symbols)
            title = line[5:].strip()
        else:
            continue
            
        # Clean up the title
        if title.endswith(' SHORT'):
            title = title[:-6].strip()
        
        # Remove any leading numbers/dots/dashes (like "1. ", "- ", etc.)
        title = re.sub(r'^[\d\-\.\s]+', '', title).strip()
        
        if title and len(title) > 5:  # Minimum length check
            titles_found.append(title)
    
    return titles_found


from src.core.auth_system import show_login_page, check_authentication, get_current_user


def clear_all_modals():
    """Clear all open modals/panels to ensure only one is open at a time."""
    modal_keys = [
        'editing_prompt', 'add_titles_modal', 'delete_titles_modal', 
        'clear_titles_confirm', 'clear_scripts_confirm', 'delete_channel_confirm',
        'adding_channel'
    ]
    for key in modal_keys:
        if key in st.session_state:
            del st.session_state[key]


def main():
    """Main Streamlit application."""
    
    try:
        # Check authentication first
        if not check_authentication():
            show_login_page()
            return
        
        # Get current user
        current_user = get_current_user()
        
        # Clear all modals on initial login to ensure clean state
        if 'modals_cleared_on_login' not in st.session_state:
            clear_all_modals()
            st.session_state.modals_cleared_on_login = True
        
        # Initialize session state
        if 'drive_manager' not in st.session_state:
            try:
                st.session_state.claude_client = ClaudeClient()
                
                # Try to initialize Google Drive
                try:
                    st.session_state.drive_manager = GoogleDriveManager()
                except Exception as drive_error:
                    st.warning(f"Google Drive initialization warning: {str(drive_error)}")
                    st.info("Some features may be limited. Channels will use local storage.")
                    # Create a dummy drive manager for fallback
                    st.session_state.drive_manager = None
                
                # Initialize channel manager (will work even if Drive fails)
                if st.session_state.drive_manager:
                    st.session_state.channel_manager = ChannelManager(st.session_state.drive_manager)
                else:
                    st.error("Google Drive not available. Please check credentials.")
                    return
                    
            except Exception as e:
                st.error(f"Failed to initialize services: {str(e)}")
                st.info("Please check if all secrets are configured correctly.")
                return
    
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        return
    
    st.title("🎬 YouTube Shorts Manager")
    user_role = current_user.get('role', 'default')
    
    # Display version for admin users
    if user_role == 'admin':
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"Welcome back, **{current_user['first_name']}**! Role: **{user_role.upper()}**")
        with col2:
            st.caption(f"v{APP_VERSION} ({VERSION_DATE})")
            st.caption(f"📝 {VERSION_NOTES}")
    else:
        st.markdown(f"Welcome back, **{current_user['first_name']}**! Role: **{user_role.upper()}**")
    
    # Logout button in top right
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🚪 Logout", key="logout_button"):
            del st.session_state.authenticated
            del st.session_state.user
            st.rerun()
    
    st.markdown("---")
    
    # Auto-backup functionality (runs every 3 hours)
    if 'last_backup' not in st.session_state:
        st.session_state.last_backup = {}
    
    # Check if backup is needed for each channel (only if channel_manager exists)
    if 'channel_manager' in st.session_state and st.session_state.channel_manager:
        try:
            for channel_name in st.session_state.channel_manager.get_channel_names():
                # For new channels, set backup time to now (so next backup is in 3 hours)
                last_backup_time = st.session_state.last_backup.get(channel_name, datetime.now())
                
                # Check if 3 hours have passed since last backup
                time_since_backup = datetime.now() - last_backup_time
                if time_since_backup > timedelta(hours=3):
                    # Show admin that auto-backup is happening
                    if user_role == 'admin':
                        st.info(f"🔄 Auto-backup running for {channel_name}...")
                    
                    # Perform backup
                    try:
                        if st.session_state.channel_manager.backup_channel_files(channel_name):
                            st.session_state.last_backup[channel_name] = datetime.now()
                            if user_role == 'admin':
                                st.success(f"✅ Auto-backup completed for {channel_name}")
                        else:
                            if user_role == 'admin':
                                st.warning(f"⚠️ Auto-backup failed for {channel_name}")
                    except Exception as backup_error:
                        if user_role == 'admin':
                            st.error(f"❌ Auto-backup error for {channel_name}: {str(backup_error)}")
        except Exception as e:
            # Silent fail for auto-backup, but log for admin
            if user_role == 'admin':
                st.error(f"❌ Auto-backup system error: {str(e)}")
    
    # Sidebar for channel management
    with st.sidebar:
        st.header("📁 Channel Management")
        
        # Refresh channels
        if st.button("🔄 Refresh Channels", key="refresh_channels_button"):
            st.session_state.channel_manager.channels = st.session_state.channel_manager.load_channels()
            st.rerun()
        
        # Upload local channels button (admin only)
        if user_role == 'admin':
            if st.button("📤 Upload Local Channels", key="upload_local_channels_button"):
                local_channels = {"Swipecore": "You are a ScrollCore-style YouTube Shorts scriptwriter...", "Starwars": "You are a ScrollCore-style YouTube Shorts scriptwriter for Star Wars..."}
                for name, prompt in local_channels.items():
                    st.session_state.channel_manager.add_channel(name, prompt)
                st.success("Uploaded sample channels to Google Drive!")
                st.rerun()
        
        # Channel selector
        channels = st.session_state.channel_manager.get_channel_names()
        if channels:
            selected_channel = st.selectbox("Select Channel", channels, key="selected_channel")
            
            # Show backup timer for all channels (admin only)
            if user_role == 'admin':
                if selected_channel:
                    # Show timer for selected channel
                    last_backup = st.session_state.last_backup.get(selected_channel)
                    if last_backup:
                        time_since = datetime.now() - last_backup
                        hours = int(time_since.total_seconds() / 3600)
                        minutes = int((time_since.total_seconds() % 3600) / 60)
                        st.caption(f"🕐 Last backup: {hours}h {minutes}m ago")
                        
                        # Calculate time until next backup (3 hours from last backup)
                        next_backup = last_backup + timedelta(hours=3)
                        time_until = next_backup - datetime.now()
                        
                        if time_until.total_seconds() > 0:
                            hours_until = int(time_until.total_seconds() / 3600)
                            minutes_until = int((time_until.total_seconds() % 3600) / 60)
                            seconds_until = int(time_until.total_seconds() % 60)
                            
                            # Show countdown with different colors based on time remaining
                            if hours_until > 0:
                                st.caption(f"⏰ Next backup in: {hours_until}h {minutes_until}m")
                            elif minutes_until > 0:
                                st.caption(f"⏰ Next backup in: {minutes_until}m {seconds_until}s")
                            else:
                                st.caption(f"⏰ Next backup in: {seconds_until}s")
                            
                            # Progress bar showing time until next backup
                            progress = (3 * 3600 - time_until.total_seconds()) / (3 * 3600)
                            st.progress(progress, text="Backup progress")
                        else:
                            st.caption("🔄 Backup pending (will run on next refresh)")
                            st.progress(1.0, text="Backup ready")
                    else:
                        st.caption("🕐 No backup yet - will run automatically")
                
                # Force page refresh every 30 seconds to update timer and trigger auto-backups
                if 'last_refresh' not in st.session_state:
                    st.session_state.last_refresh = datetime.now()
                
                time_since_refresh = datetime.now() - st.session_state.last_refresh
                if time_since_refresh > timedelta(seconds=30):
                    st.session_state.last_refresh = datetime.now()
                    st.rerun()
        else:
            selected_channel = None
            st.info("No channels yet. Create one below!")
        
        st.markdown("---")
        
        # Backup settings for admins
        if user_role == 'admin':
            with st.expander("⚙️ Backup Settings"):
                st.write("**Auto-Backup Schedule:**")
                st.info("• Automatic backups run every 3 hours\n• Files are backed up with timestamps\n• Backups stored in channel folder")
                
                # Show all channels backup status
                st.write("**All Channels Status:**")
                for ch_name in st.session_state.channel_manager.get_channel_names():
                    last_bk = st.session_state.last_backup.get(ch_name)
                    if last_bk:
                        time_ago = datetime.now() - last_bk
                        hours_ago = int(time_ago.total_seconds() / 3600)
                        minutes_ago = int((time_ago.total_seconds() % 3600) / 60)
                        st.write(f"• {ch_name}: {hours_ago}h {minutes_ago}m ago")
                    else:
                        st.write(f"• {ch_name}: Never backed up")
        
        st.markdown("---")
        
        # Add new channel (admin only)
        if user_role == 'admin':
            st.subheader("➕ Add New Channel")
            new_channel_name = st.text_input("Channel Name", key="new_channel_name")
            
            if st.button("Add Channel", type="primary", key="add_channel_button"):
                if new_channel_name.strip():
                    if new_channel_name not in st.session_state.channel_manager.channels:
                        # Show text area for base prompt
                        clear_all_modals()
                        st.session_state.adding_channel = new_channel_name.strip()
                    else:
                        st.error("Channel already exists!")
                else:
                    st.error("Please enter a channel name")
        
        # Handle adding channel (show prompt input)
        if 'adding_channel' in st.session_state:
            st.write(f"Creating channel: **{st.session_state.adding_channel}**")
            base_prompt = st.text_area("Enter base prompt for this channel:", height=150, key="base_prompt_input")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Create", key="create_channel_button"):
                    if base_prompt.strip():
                        st.session_state.channel_manager.add_channel(st.session_state.adding_channel, base_prompt.strip())
                        del st.session_state.adding_channel
                        st.success("Channel created successfully!")
                        st.rerun()
                    else:
                        st.error("Please enter a base prompt")
            
            with col2:
                if st.button("❌ Cancel", key="cancel_create_channel_button"):
                    del st.session_state.adding_channel
                    st.rerun()
    

    # Main content area
    if selected_channel:
        st.header(f"📝 Generate Scripts for: {selected_channel}")
        
        # Admin controls
        if user_role == 'admin':
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 1, 1, 1])
            with col1:
                if st.button("✏️ Edit Prompt", key=f"edit_prompt_{selected_channel}"):
                    clear_all_modals()
                    st.session_state.editing_prompt = selected_channel
            with col2:
                if st.button("🗑️ Clear Titles", key=f"clear_titles_{selected_channel}"):
                    clear_all_modals()
                    st.session_state.clear_titles_confirm = selected_channel
            with col3:
                if st.button("🗑️ Clear Scripts", key=f"clear_scripts_{selected_channel}"):
                    clear_all_modals()
                    st.session_state.clear_scripts_confirm = selected_channel
            with col4:
                if st.button("💾 Backup Now", key=f"backup_now_{selected_channel}"):
                    try:
                        if hasattr(st.session_state, 'channel_manager') and st.session_state.channel_manager:
                            if st.session_state.channel_manager.backup_channel_files(selected_channel):
                                st.success(f"✅ Backup created for {selected_channel}")
                                st.session_state.last_backup[selected_channel] = datetime.now()
                            else:
                                st.warning("Backup failed - check Google Drive connection")
                        else:
                            st.error("Channel manager not available")
                    except Exception as e:
                        st.error(f"Backup error: {str(e)}")
            with col5:
                if st.button("❌ Delete Channel"):
                    clear_all_modals()
                    st.session_state.delete_channel_confirm = selected_channel
            with col6:
                if st.button("📝 Add Titles"):
                    clear_all_modals()
                    st.session_state.add_titles_modal = selected_channel
            with col7:
                if st.button("🗑️ Delete Titles"):
                    clear_all_modals()
                    st.session_state.delete_titles_modal = selected_channel
        
        # Handle bulk add titles modal
        if 'add_titles_modal' in st.session_state and st.session_state.add_titles_modal == selected_channel:
            st.markdown("---")
            with st.expander("📝 **Add Existing Titles**", expanded=True):
                st.info(f"Add existing titles to **{selected_channel}** to prevent duplicates in future generations.")
                
                st.markdown("**Instructions:**")
                st.write("• Enter one title per line")
                st.write("• Titles will be checked for duplicates automatically") 
                st.write("• Empty lines will be ignored")
                
                # Text area for bulk title input
                bulk_titles_input = st.text_area(
                    "Enter titles (one per line):",
                    height=200,
                    placeholder="In The Dark Knight (2008)\nIn Avengers: Endgame (2019)\nIn The Matrix (1999)\n...",
                    key="bulk_titles_textarea"
                )
                
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    if st.button("➕ Add Titles", type="primary"):
                        if bulk_titles_input.strip():
                            # Split by lines and clean up
                            titles_list = [line.strip() for line in bulk_titles_input.split('\n') if line.strip()]
                            
                            if titles_list:
                                try:
                                    if hasattr(st.session_state.channel_manager, 'bulk_add_titles'):
                                        added_count, duplicate_count = st.session_state.channel_manager.bulk_add_titles(
                                            selected_channel, titles_list
                                        )
                                        
                                        if added_count > 0:
                                            st.success(f"✅ Added {added_count} new titles to {selected_channel}")
                                        
                                        if duplicate_count > 0:
                                            st.info(f"ℹ️ Skipped {duplicate_count} duplicate titles")
                                        
                                        if added_count == 0 and duplicate_count == 0:
                                            st.warning("No valid titles found to add")
                                        
                                        # Clear the modal after successful addition
                                        if added_count > 0:
                                            del st.session_state.add_titles_modal
                                            st.rerun()
                                    else:
                                        st.error("❌ Bulk add titles functionality not available - please refresh the page")
                                except Exception as e:
                                    st.error(f"❌ Error adding titles: {str(e)}")
                            else:
                                st.warning("Please enter at least one title")
                        else:
                            st.warning("Please enter some titles to add")
                
                with col2:
                    if st.button("❌ Cancel"):
                        del st.session_state.add_titles_modal
                        st.rerun()
                
                with col3:
                    # Show current title count
                    try:
                        current_titles = st.session_state.channel_manager.get_used_titles(selected_channel, force_refresh=False)
                        st.write(f"**Current titles in {selected_channel}: {len(current_titles)}**")
                    except Exception as e:
                        st.write(f"**Current titles: Unable to load** ({str(e)})")
        
        # Handle delete titles modal
        if 'delete_titles_modal' in st.session_state and st.session_state.delete_titles_modal == selected_channel:
            st.markdown("---")
            with st.expander("🗑️ **Delete Existing Titles**", expanded=True):
                st.info(f"Select titles to delete from **{selected_channel}**. Use checkboxes for batch deletion.")
                
                # Add control buttons
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    # Initialize selected titles if not exists
                    if 'selected_for_deletion' not in st.session_state:
                        st.session_state.selected_for_deletion = set()
                    
                    selected_count = len(st.session_state.selected_for_deletion)
                    if selected_count > 0:
                        st.write(f"**{selected_count} titles selected**")
                    else:
                        st.write("Select titles to delete")
                        
                with col2:
                    if st.button("🗑️ Delete Selected", type="primary", disabled=selected_count == 0):
                        if st.session_state.selected_for_deletion:
                            with st.spinner(f"Deleting {selected_count} titles..."):
                                titles_to_delete = list(st.session_state.selected_for_deletion)
                                deleted_count, not_found = st.session_state.channel_manager.bulk_delete_titles(
                                    selected_channel, titles_to_delete
                                )
                                if deleted_count > 0:
                                    st.success(f"✅ Deleted {deleted_count} titles")
                                    # Clear cache and selection
                                    cache_key = f"cached_titles_{selected_channel}"
                                    if cache_key in st.session_state:
                                        del st.session_state[cache_key]
                                    st.session_state.selected_for_deletion.clear()
                                    st.rerun()
                                else:
                                    st.error("Failed to delete titles")
                                    
                with col3:
                    if st.button("🔄 Force Refresh", help="Force reload from Google Drive"):
                        # Clear all caches and force Google Drive refresh
                        cache_key = f"cached_titles_{selected_channel}"
                        if cache_key in st.session_state:
                            del st.session_state[cache_key]
                        ordered_cache_key = f"ordered_titles_{selected_channel}"
                        if ordered_cache_key in st.session_state:
                            del st.session_state[ordered_cache_key]
                        st.session_state.selected_for_deletion.clear()
                        
                        # Also try to refresh the drive manager connection
                        try:
                            # Force refresh the Google Drive file list
                            filename = f"titles_{selected_channel.lower()}.txt"
                            channel_folder_id = st.session_state.channel_manager.drive_manager.get_or_create_channel_folder(selected_channel)
                            
                            # Try to get file fresh from Google Drive
                            st.success("🔄 Forcing fresh read from Google Drive...")
                        except Exception as e:
                            st.error(f"Refresh error: {str(e)}")
                        
                        st.rerun()
                
                # Get current titles in the order they appear in the file
                try:
                    # Always get fresh data from file to reflect manual changes
                    filename = f"titles_{selected_channel.lower()}.txt"
                    channel_folder_id = st.session_state.channel_manager.drive_manager.get_or_create_channel_folder(selected_channel)
                    
                    # Add debug checkbox for troubleshooting
                    show_debug = st.checkbox("🔍 Show debug info", help="Troubleshoot file reading issues")
                    
                    content = st.session_state.channel_manager.drive_manager.read_file(filename, channel_folder_id)
                    
                    if show_debug:
                        st.write(f"**Debug Info:**")
                        st.write(f"- File: {filename}")
                        st.write(f"- Channel folder: {channel_folder_id}")
                        st.write(f"- Content length: {len(content) if content else 0}")
                        
                        # List all files in the channel folder
                        try:
                            drive_service = st.session_state.channel_manager.drive_manager.service
                            folder_files = drive_service.files().list(
                                q=f"parents='{channel_folder_id}' and trashed=false",
                                fields="files(id, name, size, modifiedTime)"
                            ).execute()
                            
                            st.write(f"**All files in {selected_channel} folder:**")
                            for file in folder_files.get('files', []):
                                st.write(f"  • {file['name']} (Size: {file.get('size', 'N/A')} bytes, Modified: {file.get('modifiedTime', 'N/A')})")
                                
                        except Exception as e:
                            st.write(f"- Error listing folder files: {str(e)}")
                        
                        if content:
                            st.text_area("Raw file content:", content, height=200, disabled=True)
                        else:
                            st.write("- Raw content: (empty)")
                            st.error("🚨 **The app is reading an empty file, but you say there's content in Google Drive**")
                            st.write("**This suggests:**")
                            st.write("• Wrong file is being read")
                            st.write("• File permissions issue")
                            st.write("• Google Drive API cache issue")
                            st.write("• File is in wrong folder location")
                            
                            st.markdown("---")
                            st.write("**🔧 Try this fix:**")
                            if st.button("🔥 Force Recreate File", help="Delete and recreate the titles file", type="primary"):
                                try:
                                    # Try to delete the existing file and recreate it
                                    drive_service = st.session_state.channel_manager.drive_manager.service
                                    
                                    # Find and delete the existing file
                                    existing_files = drive_service.files().list(
                                        q=f"name='{filename}' and parents='{channel_folder_id}' and trashed=false",
                                        fields="files(id, name)"
                                    ).execute()
                                    
                                    for file in existing_files.get('files', []):
                                        drive_service.files().delete(fileId=file['id']).execute()
                                        st.success(f"🗑️ Deleted corrupted file: {file['name']}")
                                    
                                    st.info("📝 Now use the '📝 Add Titles' button to add your titles back")
                                    st.info("💡 Or generate some scripts to automatically create titles")
                                    
                                except Exception as e:
                                    st.error(f"Failed to recreate file: {str(e)}")
                            
                            st.write("**Or manually fix in Google Drive:**")
                            st.write("1. Go to your Google Drive Swipecore folder")
                            st.write("2. Delete the existing titles_swipecore.txt file")
                            st.write("3. Create a new file with the same name")
                            st.write("4. Add your titles and save")
                            st.write("5. Come back and try the Force Refresh button")
                    
                    if content and content.strip():
                        titles_list = [line.strip() for line in content.split('\n') if line.strip()]
                    else:
                        titles_list = []
                        if not show_debug:
                            st.warning(f"⚠️ The file {filename} appears empty")
                            st.info("📝 Try checking the '🔍 Show debug info' to see the raw file content")
                            st.write("**Then compare with what you see in Google Drive**")
                    
                    if titles_list:
                        # Show processing indicator if deleting
                        processing_key = f"processing_delete_{selected_channel}"
                        processing_start_key = f"processing_start_{selected_channel}"
                        is_processing = st.session_state.get(processing_key, False)
                        
                        if is_processing:
                            # Check if processing has been stuck for too long (more than 10 seconds)
                            processing_start = st.session_state.get(processing_start_key, datetime.now())
                            time_stuck = datetime.now() - processing_start
                            
                            if time_stuck.total_seconds() > 10:
                                # Reset stuck processing
                                st.session_state[processing_key] = False
                                if processing_start_key in st.session_state:
                                    del st.session_state[processing_start_key]
                                st.error("⚠️ Processing timeout - reset automatically")
                                st.rerun()
                            else:
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.warning("🔄 Processing deletion... Please wait")
                                with col2:
                                    if st.button("🔧 Reset", help="Click if stuck"):
                                        st.session_state[processing_key] = False
                                        if processing_start_key in st.session_state:
                                            del st.session_state[processing_start_key]
                                        st.rerun()
                        
                        st.write(f"**{len(titles_list)} titles found (in file order):**")
                        
                        # Pagination settings
                        items_per_page = 50  # Limit to prevent memory issues
                        if 'delete_page' not in st.session_state:
                            st.session_state.delete_page = 0
                        
                        total_pages = max(1, (len(titles_list) - 1) // items_per_page + 1)
                        # Ensure current page is valid
                        current_page = min(st.session_state.delete_page, total_pages - 1)
                        if current_page != st.session_state.delete_page:
                            st.session_state.delete_page = current_page
                        
                        # Pagination controls
                        col1, col2, col3, col4 = st.columns([1, 2, 1, 2])
                        with col1:
                            if st.button("◀ Prev", disabled=current_page == 0, key="prev_page_btn"):
                                st.session_state.delete_page = max(0, current_page - 1)
                                st.rerun()
                        with col2:
                            st.write(f"Page {current_page + 1} of {total_pages}")
                        with col3:
                            if st.button("Next ▶", disabled=current_page >= total_pages - 1, key="next_page_btn"):
                                st.session_state.delete_page = min(total_pages - 1, current_page + 1)
                                st.rerun()
                        with col4:
                            st.write(f"**{len(st.session_state.selected_for_deletion)} selected**")
                        
                        # Select/deselect buttons for current page
                        col1, col2, col3 = st.columns([1, 1, 3])
                        
                        # Calculate current page items
                        start_idx = current_page * items_per_page
                        end_idx = min(start_idx + items_per_page, len(titles_list))
                        page_titles = titles_list[start_idx:end_idx]
                        
                        with col1:
                            if st.button("✅ Select Page"):
                                for title in page_titles:
                                    st.session_state.selected_for_deletion.add(title)
                                st.rerun()
                        with col2:
                            if st.button("❌ Clear Page"):
                                for title in page_titles:
                                    st.session_state.selected_for_deletion.discard(title)
                                st.rerun()
                        with col3:
                            st.info(f"Showing {start_idx + 1}-{end_idx} of {len(titles_list)}")
                        
                        # Show titles for current page only
                        for idx, title in enumerate(page_titles):
                            actual_idx = start_idx + idx
                            col1, col2 = st.columns([1, 10])
                            with col1:
                                # Use checkbox for selection with proper label
                                is_selected = title in st.session_state.selected_for_deletion
                                checkbox_key = f"del_cb_{actual_idx}"  # Unique key using actual index
                                if st.checkbox("Select", value=is_selected, key=checkbox_key, label_visibility="hidden"):
                                    st.session_state.selected_for_deletion.add(title)
                                else:
                                    st.session_state.selected_for_deletion.discard(title)
                            with col2:
                                # Show title with visual indicator if selected
                                if title in st.session_state.selected_for_deletion:
                                    st.markdown(f"🗑️ ~~{title}~~")
                                else:
                                    st.write(f"• {title}")
                    
                    else:
                        st.info("No titles found in this channel.")
                
                except Exception as e:
                    st.error(f"❌ Error loading titles: {str(e)}")
                
                # Cancel button at the bottom
                st.markdown("---")
                if st.button("❌ Close", type="secondary"):
                    # Clear processing flags and selection when closing modal
                    processing_key = f"processing_delete_{selected_channel}"
                    processing_start_key = f"processing_start_{selected_channel}"
                    if processing_key in st.session_state:
                        del st.session_state[processing_key]
                    if processing_start_key in st.session_state:
                        del st.session_state[processing_start_key]
                    if 'selected_for_deletion' in st.session_state:
                        st.session_state.selected_for_deletion.clear()
                    if 'delete_page' in st.session_state:
                        del st.session_state.delete_page
                    del st.session_state.delete_titles_modal
                    st.rerun()
        
        # Handle channel deletion confirmation
        if 'delete_channel_confirm' in st.session_state and st.session_state.delete_channel_confirm == selected_channel:
            st.markdown("---")
            with st.expander("⚠️ **CONFIRM: Delete Channel**", expanded=True):
                st.error(f"**WARNING:** This will remove **{selected_channel}** from the dropdown!")
                st.info("📋 **What this does:**\n• Removes channel from the selection dropdown\n• Does NOT delete Google Drive files or data\n• Channel data remains safe in Google Drive")
                st.warning("You can re-add the channel later by creating it again with the same name")
                
                # Confirmation checkbox
                confirm_delete = st.checkbox(f"I want to remove {selected_channel} from the dropdown", key="confirm_channel_delete")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("❌ Yes, Remove Channel", type="primary", disabled=not confirm_delete):
                        try:
                            if hasattr(st.session_state.channel_manager, 'delete_channel'):
                                if st.session_state.channel_manager.delete_channel(selected_channel):
                                    st.success(f"✅ Channel '{selected_channel}' removed from dropdown")
                                    # Clear the confirmation state and force refresh
                                    del st.session_state.delete_channel_confirm
                                    time.sleep(1)  # Brief pause for user to see success message
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to delete channel '{selected_channel}'")
                            else:
                                st.error("❌ Delete channel functionality not available - please refresh the page")
                        except Exception as e:
                            st.error(f"❌ Delete channel error: {str(e)}")
                
                with col2:
                    if st.button("🔄 Cancel", key="cancel_delete_channel"):
                        del st.session_state.delete_channel_confirm
                        st.rerun()
        
        # Handle prompt editing (no password needed for admins)
        if 'editing_prompt' in st.session_state and st.session_state.editing_prompt == selected_channel:
            if user_role == 'admin':
                current_prompt = st.session_state.channel_manager.get_channel_prompt(selected_channel)
                edited_prompt = st.text_area("Edit channel prompt:", value=current_prompt, height=400, key="prompt_editor")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Save Changes", key=f"save_prompt_changes_{selected_channel}"):
                        st.session_state.channel_manager.update_channel_prompt(selected_channel, edited_prompt)
                        del st.session_state.editing_prompt
                        st.success("Prompt updated successfully!")
                        st.rerun()
                
                with col2:
                    if st.button("❌ Cancel Edit", key=f"cancel_edit_prompt_{selected_channel}"):
                        del st.session_state.editing_prompt
                        st.rerun()
            else:
                st.error("You don't have permission to edit prompts")
                del st.session_state.editing_prompt
        
        # Clear Titles Confirmation Dialog
        if 'clear_titles_confirm' in st.session_state and st.session_state.clear_titles_confirm == selected_channel:
            st.markdown("---")
            with st.expander("⚠️ **CONFIRM: Clear All Titles**", expanded=True):
                st.error(f"**WARNING:** This will delete ALL titles for {selected_channel}!")
                st.write("This action cannot be undone (but a backup will be created first).")
                
                # First confirmation
                confirm1 = st.checkbox("I understand this will delete all titles", key="clear_titles_confirm1")
                
                # Second confirmation  
                confirm2 = st.checkbox("I really want to delete all titles", key="clear_titles_confirm2")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Yes, Clear All Titles", type="primary", disabled=not (confirm1 and confirm2)):
                        # Create backup first
                        st.session_state.channel_manager.backup_channel_files(selected_channel)
                        # Clear titles
                        if st.session_state.channel_manager.clear_titles(selected_channel):
                            st.success(f"✅ All titles cleared for {selected_channel}")
                            del st.session_state.clear_titles_confirm
                            st.rerun()
                
                with col2:
                    if st.button("❌ Cancel", key="cancel_clear_titles"):
                        del st.session_state.clear_titles_confirm
                        st.rerun()
        
        # Clear Scripts Confirmation Dialog
        if 'clear_scripts_confirm' in st.session_state and st.session_state.clear_scripts_confirm == selected_channel:
            st.markdown("---")
            with st.expander("⚠️ **CONFIRM: Clear All Scripts**", expanded=True):
                st.error(f"**WARNING:** This will delete ALL scripts for {selected_channel}!")
                st.write("This action cannot be undone (but a backup will be created first).")
                
                # First confirmation
                confirm1 = st.checkbox("I understand this will delete all scripts", key="clear_scripts_confirm1")
                
                # Second confirmation
                confirm2 = st.checkbox("I really want to delete all scripts", key="clear_scripts_confirm2")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Yes, Clear All Scripts", type="primary", disabled=not (confirm1 and confirm2)):
                        # Create backup first
                        st.session_state.channel_manager.backup_channel_files(selected_channel)
                        # Clear scripts
                        if st.session_state.channel_manager.clear_scripts(selected_channel):
                            st.success(f"✅ All scripts cleared for {selected_channel}")
                            del st.session_state.clear_scripts_confirm
                            st.rerun()
                
                with col2:
                    if st.button("❌ Cancel", key="cancel_clear_scripts"):
                        del st.session_state.clear_scripts_confirm
                        st.rerun()
        
        st.markdown("---")
        
        # Show last successful generation results if they exist
        if 'last_successful_generation' in st.session_state and st.session_state.last_successful_generation.get('channel') == selected_channel:
            gen_data = st.session_state.last_successful_generation
            
            st.success(f"✅ Last generation completed successfully! Found {len(gen_data['titles'])} titles.")
            
            # Show titles
            if gen_data['titles']:
                st.subheader("📋 Extracted Titles:")
                for i, title in enumerate(gen_data['titles'], 1):
                    st.write(f"{i}. {title}")
            
            # Show script
            st.subheader("📄 Generated Script:")
            
            # Debug info for admin
            if user_role == 'admin':
                st.caption(f"Generated: {gen_data['timestamp']}")
                st.caption(f"Content length: {len(gen_data['content']) if gen_data['content'] else 'None'} characters")
            
            # Script display
            with st.expander("🔽 **View Full Generated Script**", expanded=True):
                st.text_area(
                    "Generated Content (Click to copy):",
                    value=gen_data['content'] if gen_data['content'] else "No content available",
                    height=500,
                    disabled=True,
                    help="Full generated script with proper text wrapping - click and Ctrl+A to select all, then Ctrl+C to copy",
                    key=f"persisted_script_display_{gen_data['session_id']}"
                )
                
                # Add character and word count
                if gen_data['content']:
                    word_count = len(gen_data['content'].split())
                    char_count = len(gen_data['content'])
                    st.caption(f"📊 **Stats:** {word_count} words, {char_count} characters")
                
                st.info("💡 **Tip:** Click inside the text area above, then use Ctrl+A to select all and Ctrl+C to copy the entire script.")
            
            # Show token usage for admins
            if user_role == 'admin' and gen_data.get('token_usage'):
                token_info = gen_data['token_usage']
                with st.expander("📊 **Token Usage Stats** (Admin Only)", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Input Tokens", f"{token_info.get('input_tokens', 0):,}")
                    with col2:
                        st.metric("Output Tokens", f"{token_info.get('output_tokens', 0):,}")
                    with col3:
                        st.metric("Total Tokens", f"{token_info.get('total_tokens', 0):,}")
                    
                    # Cost estimation
                    input_cost = (token_info.get('input_tokens', 0) / 1_000_000) * 3.00
                    output_cost = (token_info.get('output_tokens', 0) / 1_000_000) * 15.00
                    total_cost = input_cost + output_cost
                    
                    st.write("**💰 Cost Estimation:**")
                    st.write(f"Total cost: ${total_cost:.4f}")
            
            st.info(f"Session ID: {gen_data['session_id']}")
            
            # Clear button for admin
            if user_role == 'admin':
                if st.button("🗑️ Clear Results"):
                    del st.session_state.last_successful_generation
                    st.rerun()
            
            st.markdown("---")
        
        # Show persistent error if exists
        if 'last_generation_error' in st.session_state and user_role == 'admin':
            with st.expander("⚠️ **Last Generation Error** (Admin Only)", expanded=False):
                error_info = st.session_state.last_generation_error
                st.error(f"**Error:** {error_info['error']}")
                st.write(f"**Time:** {error_info['timestamp']}")
                st.text_area("Full traceback:", value=error_info['traceback'], height=150, disabled=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Clear Error Log"):
                        del st.session_state.last_generation_error
                        st.rerun()
                with col2:
                    if st.button("🔄 Refresh Channel Manager"):
                        st.session_state.channel_manager = ChannelManager(st.session_state.drive_manager)
                        st.success("Channel manager refreshed!")
                        st.rerun()
        
        # Script generation
        st.subheader("🎯 Generate New Scripts")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            extra_prompt = st.text_input("Extra prompt (optional):", help="Add any specific instructions for this generation")
        with col2:
            num_scripts = st.number_input("🔢 Number of scripts:", min_value=1, max_value=10, value=1, step=1, help="Generate 1-10 scripts at once")
        
        # Create button (no disabled state needed for direct generation)
        generate_button = st.button(
            "🚀 Generate Scripts", 
            type="primary",
            key="generate_button"
        )
        
        # Process generation only when button is clicked
        if generate_button:
            try:
                with st.spinner(f"🎬 Generating {num_scripts} script{'s' if num_scripts > 1 else ''}... This may take {10 * int(num_scripts)}-{30 * int(num_scripts)} seconds..."):
                    try:
                        # Try with force_refresh first, fallback without it if there's an error
                        try:
                            used_titles = st.session_state.channel_manager.get_used_titles(selected_channel, force_refresh=True)
                        except TypeError:
                            # Fallback for old method signature - refresh channel manager
                            st.warning("Refreshing channel manager...")
                            st.session_state.channel_manager = ChannelManager(st.session_state.drive_manager)
                            used_titles = st.session_state.channel_manager.get_used_titles(selected_channel, force_refresh=True)
                        
                        # Debug: Show how many titles we're excluding
                        if user_role == 'admin':
                            st.info(f"📊 Loading exclusion list: Found {len(used_titles)} existing titles for {selected_channel}")
                    except Exception as titles_error:
                        st.error(f"❌ Error loading titles: {str(titles_error)}")
                        used_titles = set()  # Continue with empty set
                    
                    # Build exclusion list
                    base_prompt = st.session_state.channel_manager.get_channel_prompt(selected_channel)
                    full_prompt = base_prompt
                    
                    if used_titles:
                        # Get all used movies with years for complete blocking
                        used_titles_list = list(used_titles)
                        used_movies_with_years = set()
                        
                        # Extract complete movie names with years
                        for title in used_titles_list:
                            movie, _ = SimilarityChecker.extract_movie_and_fact(title)
                            if movie:
                                used_movies_with_years.add(movie)
                        
                        # Build comprehensive exclusion prompt for FACTS only, not movies
                        if used_titles_list:
                            # Show AI the titles intelligently
                            st.session_state.last_loaded_titles = used_titles_list
                            
                            # Smart title selection based on list size
                            if len(used_titles_list) <= 100:
                                # For smaller lists, send all titles
                                titles_to_send = used_titles_list
                                titles_display = '\n'.join(titles_to_send)
                                sampling_note = ""
                            elif len(used_titles_list) <= 300:
                                # For medium lists, send most recent 80 + random sample of 20 older ones
                                recent_titles = used_titles_list[-80:]  # Most recent 80
                                older_titles = used_titles_list[:-80]
                                import random
                                sample_older = random.sample(older_titles, min(20, len(older_titles)))
                                titles_to_send = sample_older + recent_titles
                                titles_display = '\n'.join(titles_to_send)
                                sampling_note = f"\n(Showing {len(titles_to_send)} of {len(used_titles_list)} total titles - focusing on recent ones)"
                            else:
                                # For large lists, send most recent 100 + sample of 50 older
                                recent_titles = used_titles_list[-100:]  # Most recent 100
                                older_titles = used_titles_list[:-100]
                                import random
                                sample_older = random.sample(older_titles, min(50, len(older_titles)))
                                titles_to_send = sample_older + recent_titles
                                titles_display = '\n'.join(titles_to_send)
                                sampling_note = f"\n(Showing {len(titles_to_send)} representative titles from {len(used_titles_list)} total)"
                            
                            # Create BANNED MOVIES list first
                            banned_movies_list = "\n".join(sorted(used_movies_with_years)[:200])  # Limit to 200 for token efficiency
                            
                            # Create strong exclusion prompt with banned movies FIRST
                            exclusion_text = f"""
🚫🚫🚫 BANNED MOVIES - DO NOT USE ANY OF THESE 🚫🚫🚫

These {len(used_movies_with_years)} movies have already been used. Each movie can only be used ONCE.
DO NOT USE ANY OF THESE MOVIES:

{banned_movies_list}

🚫🚫🚫 END OF BANNED MOVIES LIST 🚫🚫🚫

Now here are the existing facts for reference:

===== EXISTING FACTS =====
{titles_display[:50]}  
===== END OF FACTS =====

CRITICAL RULES:
1. NEVER use any movie from the BANNED MOVIES list above
2. Each movie can only be used ONCE - if it's in the banned list, pick a different movie
3. Generate facts from COMPLETELY NEW movies not in the banned list
4. Focus on diverse movies from different decades and genres
"""
                            full_prompt = f"{exclusion_text}\\n\\n{base_prompt}"
                        
                        # Add strong movie diversity instructions
                        full_prompt += f" \\n\\n⚠️ MOVIE RULES: NEVER reuse a movie. Each movie gets ONE fact only. Check the BANNED MOVIES list and pick something completely different. Mix facts from different decades (1970s-2020s). \\n\\n🔥 TRENDING: For new picks, consider trending actors (Sydney Sweeney, Zendaya, Timothée Chalamet, Anya Taylor-Joy, etc.) but ONLY if their movies aren't already used."
                    else:
                        # Even for first generation, emphasize movie diversity
                        full_prompt += " \\n\\n🎯 MOVIE DIVERSITY: Each movie can only be used ONCE. Pick from a wide variety of movies across different decades (1970s-2020s) and genres. \\n\\n🔥 TRENDING: Consider films with trending actors (Sydney Sweeney, Zendaya, Timothée Chalamet, etc.) for engagement."
                    
                    if extra_prompt.strip():
                        full_prompt += " " + extra_prompt.strip()
                    
                    # Debug: Show admin what the AI is receiving (for troubleshooting)
                    if user_role == 'admin':
                        with st.expander("🔍 **DEBUG: View AI Prompt** (Admin Only)", expanded=False):
                            st.text_area("Full prompt sent to AI:", value=full_prompt, height=200, disabled=True)
                            if used_titles:
                                st.write(f"**Total existing titles:** {len(used_titles)}")
                                st.write(f"**Unique movies extracted:** {len(used_movies) if 'used_movies' in locals() else 'N/A'}")
                                # Show sample of actual titles being excluded
                                with st.expander("View titles being excluded", expanded=False):
                                    for i, title in enumerate(list(used_titles)[:10], 1):
                                        st.caption(f"{i}. {title}")
                                    if len(used_titles) > 10:
                                        st.caption(f"... and {len(used_titles) - 10} more")
                            # Calculate and show prompt size
                            prompt_length = len(full_prompt)
                            estimated_tokens = prompt_length / 4  # Rough estimate: 1 token ≈ 4 characters
                            st.write(f"**Prompt length:** {prompt_length} characters (≈{int(estimated_tokens)} tokens)")
                    
                    # Generate multiple scripts
                    all_generated_scripts = []
                    total_added = 0
                    total_blocked = 0
                    session_used_movies = set()  # Track movies used in THIS session
                    
                    for script_num in range(int(num_scripts)):
                        st.write(f"🔄 Generating script {script_num + 1} of {int(num_scripts)}...")
                        
                        # REBUILD prompt for each generation with updated banned list
                        if script_num > 0:
                            # Get fresh titles including ones just added
                            used_titles = st.session_state.channel_manager.get_used_titles(selected_channel, force_refresh=True)
                            used_titles_list = list(used_titles)
                            used_movies_with_years = set()
                            
                            # Extract ALL movies (including from this session)
                            for title in used_titles_list:
                                movie, _ = SimilarityChecker.extract_movie_and_fact(title)
                                if movie:
                                    used_movies_with_years.add(movie)
                            
                            # Add session movies
                            used_movies_with_years.update(session_used_movies)
                            
                            # Rebuild the ENTIRE prompt with updated banned list
                            banned_movies_list = "\n".join(sorted(used_movies_with_years)[:200])
                            
                            exclusion_text = f"""
🚫🚫🚫 BANNED MOVIES - DO NOT USE ANY OF THESE 🚫🚫🚫

These {len(used_movies_with_years)} movies have already been used. Each movie can only be used ONCE.
DO NOT USE ANY OF THESE MOVIES:

{banned_movies_list}

🚫🚫🚫 END OF BANNED MOVIES LIST 🚫🚫🚫

CRITICAL RULES:
1. NEVER use any movie from the BANNED MOVIES list above
2. Each movie can only be used ONCE - if it's in the banned list, pick a different movie
3. Generate facts from COMPLETELY NEW movies not in the banned list
4. Focus on diverse movies from different decades and genres
"""
                            script_prompt = f"{exclusion_text}\n\n{base_prompt}"
                            
                            if extra_prompt.strip():
                                script_prompt += " " + extra_prompt.strip()
                            
                            script_prompt += " \n\n⚠️ MOVIE RULES: NEVER reuse a movie. Each movie gets ONE fact only. Check the BANNED MOVIES list and pick something completely different."
                        else:
                            # First script uses original prompt
                            script_prompt = full_prompt
                        
                        # Add final reminder
                        script_prompt += "\n\n⚠️ FINAL REMINDER: Generate EXACTLY ONE movie fact. The movie MUST NOT be in the BANNED MOVIES list shown above."
                        
                        try:
                            session_id = str(uuid.uuid4())
                            result = st.session_state.claude_client.generate_script(script_prompt, session_id)
                        except Exception as api_error:
                            st.error(f"❌ API Error for script {script_num + 1}: {str(api_error)}")
                            continue
                        
                        if result["success"]:
                            # Initialize variables to ensure they're always defined
                            content = result.get("content", "No content available")
                            titles = []
                            
                            try:
                                # Extract and save titles
                                titles = extract_titles_from_response(content)
                                
                                # Debug: Show what titles were found
                                if user_role == 'admin':
                                    st.info(f"🔍 Debug: Extracted {len(titles)} titles from script {script_num + 1}")
                                
                                added_count = 0
                                blocked_titles = []
                                
                                for title in titles:
                                    try:
                                        # Get fresh titles to check against
                                        current_titles = st.session_state.channel_manager.get_used_titles(selected_channel, force_refresh=True)
                                        is_dup, reason = SimilarityChecker.is_duplicate_title(title, current_titles)
                                        
                                        if not is_dup:
                                            if st.session_state.channel_manager.add_title(selected_channel, title):
                                                added_count += 1
                                                # Track movie for this session
                                                movie, _ = SimilarityChecker.extract_movie_and_fact(title)
                                                if movie:
                                                    session_used_movies.add(movie)
                                                if user_role == 'admin':
                                                    st.caption(f"✅ Saved title: {title}")
                                        else:
                                            blocked_titles.append((title, reason))
                                            total_blocked += 1
                                            if user_role == 'admin':
                                                st.caption(f"🚫 Blocked title: {title} (Reason: {reason})")
                                    except Exception as title_error:
                                        st.error(f"❌ Failed to process title '{title}': {str(title_error)}")
                                
                                # Save script
                                try:
                                    user_name = current_user.get('first_name', 'Unknown User')
                                    st.session_state.channel_manager.save_script(selected_channel, content, session_id, user_name)
                                except Exception as script_error:
                                    st.error(f"❌ Failed to save script {script_num + 1}: {str(script_error)}")
                                
                                # Store script info
                                script_info = {
                                    "script_number": script_num + 1,
                                    "content": content,
                                    "titles": titles,
                                    "added_titles": added_count,
                                    "blocked_titles": blocked_titles,
                                    "session_id": session_id,
                                    "token_usage": result.get('token_usage', {})
                                }
                                all_generated_scripts.append(script_info)
                                total_added += added_count
                                
                            except Exception as processing_error:
                                st.error(f"❌ Error processing script {script_num + 1}: {str(processing_error)}")
                        else:
                            st.error(f"❌ Script {script_num + 1} generation failed: {result.get('error', 'Unknown error')}")
                    
                    # Display overall results
                    if all_generated_scripts:
                        st.success(f"✅ Generated {len(all_generated_scripts)} script{'s' if len(all_generated_scripts) > 1 else ''}!")
                        if total_added > 0:
                            st.success(f"🎯 Added {total_added} new unique titles total!")
                        if total_blocked > 0:
                            st.warning(f"🚫 Blocked {total_blocked} duplicate/similar titles total!")
                    
                    # Display each script
                    for script_info in all_generated_scripts:
                        script_num = script_info["script_number"]
                        content = script_info["content"]
                        titles = script_info["titles"]
                        added_count = script_info["added_titles"]
                        blocked_titles = script_info["blocked_titles"]
                        session_id = script_info["session_id"]
                        
                        st.markdown("---")
                        st.subheader(f"📄 Script #{script_num}")
                        
                        # Show title statistics for this script
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Titles", len(titles))
                        with col2:
                            st.metric("Added", added_count, delta=added_count if added_count > 0 else None)
                        with col3:
                            st.metric("Blocked", len(blocked_titles), delta=f"-{len(blocked_titles)}" if blocked_titles else None)
                        
                        # Show blocked titles with reasons
                        if blocked_titles:
                            with st.expander(f"🚫 Blocked Titles for Script #{script_num} ({len(blocked_titles)})", expanded=False):
                                for blocked_title, reason in blocked_titles:
                                    st.write(f"❌ **{blocked_title}**")
                                    st.caption(f"   Reason: {reason}")
                        
                        # Show accepted titles
                        accepted_titles = [title for title in titles if not any(title == bt[0] for bt in blocked_titles)]
                        if accepted_titles:
                            with st.expander(f"✅ Added Titles for Script #{script_num} ({len(accepted_titles)})", expanded=False):
                                for i, title in enumerate(accepted_titles, 1):
                                    st.write(f"{i}. {title}")
                        
                        # Show script content
                        with st.expander(f"📜 View Script #{script_num} Content", expanded=len(all_generated_scripts) == 1):
                            st.text_area(
                                f"Script #{script_num} Content:",
                                value=content,
                                height=400,
                                disabled=True,
                                key=f"script_{session_id}"
                            )
                            
                            if content:
                                st.caption(f"📊 {len(content.split())} words, {len(content)} characters")
                    
            except Exception as e:
                st.error(f"❌ Outer error: {str(e)}")
    
    else:
        st.info("👈 Select a channel from the sidebar or create a new one to get started!")


if __name__ == "__main__":
    main()
