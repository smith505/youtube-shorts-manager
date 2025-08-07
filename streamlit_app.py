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
        """Generate a YouTube short script using Claude API."""
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
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "content": data["content"][0]["text"],
                    "session_id": session_id
                }
            else:
                return {
                    "success": False,
                    "error": f"API Error {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Network error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
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
    
    def get_used_titles(self, channel_name: str) -> Set[str]:
        """Load used titles for a channel from Google Drive channel folder."""
        filename = f"titles_{channel_name.lower()}.txt"
        titles = set()
        try:
            # Get or create the channel folder
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            content = self.drive_manager.read_file(filename, channel_folder_id)
            if content:
                titles = {line.strip() for line in content.split('\n') if line.strip()}
        except Exception as e:
            pass
        return titles
    
    def add_title(self, channel_name: str, title: str):
        """Add a new title to a channel's Google Drive folder."""
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            # Get or create the channel folder
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            self.drive_manager.append_to_file(filename, f"{title}\n", channel_folder_id)
        except Exception as e:
            st.error(f"Failed to save title for {channel_name} to Google Drive: {str(e)}")
    
    def bulk_add_titles(self, channel_name: str, titles_list: list):
        """Bulk add multiple titles to a channel's Google Drive folder."""
        if not titles_list:
            return 0, 0
            
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            # Get existing titles to avoid duplicates
            existing_titles = self.get_used_titles(channel_name)
            
            # Filter out duplicates and empty titles
            new_titles = []
            duplicate_count = 0
            
            for title in titles_list:
                title = title.strip()
                if title:  # Not empty
                    if title in existing_titles:
                        duplicate_count += 1
                    else:
                        new_titles.append(title)
                        existing_titles.add(title)  # Add to set to catch duplicates within the list
            
            if new_titles:
                # Get or create the channel folder
                channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
                
                # Add all new titles at once
                titles_content = "\n".join(new_titles) + "\n"
                self.drive_manager.append_to_file(filename, titles_content, channel_folder_id)
                
            return len(new_titles), duplicate_count
            
        except Exception as e:
            st.error(f"Failed to bulk add titles for {channel_name} to Google Drive: {str(e)}")
            return 0, 0
    
    def save_script(self, channel_name: str, content: str, session_id: str):
        """Save the full generated script to a channel's Google Drive folder."""
        filename = f"saved_scripts_{channel_name.lower()}.txt"
        try:
            # Get or create the channel folder
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            script_content = content + "\n\n\n"  # Add three blank lines between scripts
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


from auth_system import show_login_page, check_authentication, get_current_user


def main():
    """Main Streamlit application."""
    
    try:
        # Check authentication first
        if not check_authentication():
            show_login_page()
            return
        
        # Get current user
        current_user = get_current_user()
        
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
    st.markdown(f"Welcome back, **{current_user['first_name']}**! Role: **{user_role.upper()}**")
    # App version: 2.1 - delete channel fix
    
    # Logout button in top right
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🚪 Logout"):
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
                # Get last backup time, default to 4 hours ago to trigger immediate first backup
                last_backup_time = st.session_state.last_backup.get(channel_name, datetime.now() - timedelta(hours=4))
                
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
        if st.button("🔄 Refresh Channels"):
            st.session_state.channel_manager.channels = st.session_state.channel_manager.load_channels()
            st.rerun()
        
        # Upload local channels button (admin only)
        if user_role == 'admin':
            if st.button("📤 Upload Local Channels"):
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
            
            if st.button("Add Channel", type="primary"):
                if new_channel_name.strip():
                    if new_channel_name not in st.session_state.channel_manager.channels:
                        # Show text area for base prompt
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
                if st.button("✅ Create"):
                    if base_prompt.strip():
                        st.session_state.channel_manager.add_channel(st.session_state.adding_channel, base_prompt.strip())
                        del st.session_state.adding_channel
                        st.success("Channel created successfully!")
                        st.rerun()
                    else:
                        st.error("Please enter a base prompt")
            
            with col2:
                if st.button("❌ Cancel"):
                    del st.session_state.adding_channel
                    st.rerun()
    
    # Main content area
    if selected_channel:
        st.header(f"📝 Generate Scripts for: {selected_channel}")
        
        # Admin controls
        if user_role == 'admin':
            col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 1])
            with col1:
                if st.button("✏️ Edit Prompt"):
                    st.session_state.editing_prompt = selected_channel
            with col2:
                if st.button("🗑️ Clear Titles"):
                    st.session_state.clear_titles_confirm = selected_channel
            with col3:
                if st.button("🗑️ Clear Scripts"):
                    st.session_state.clear_scripts_confirm = selected_channel
            with col4:
                if st.button("💾 Backup Now"):
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
                    st.session_state.delete_channel_confirm = selected_channel
            with col6:
                if st.button("📝 Add Titles"):
                    st.session_state.add_titles_modal = selected_channel
        
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
                        current_titles = st.session_state.channel_manager.get_used_titles(selected_channel)
                        st.write(f"**Current titles in {selected_channel}: {len(current_titles)}**")
                    except:
                        st.write("**Current titles: Unable to load**")
        
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
                edited_prompt = st.text_area("Edit channel prompt:", value=current_prompt, height=200, key="prompt_editor")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Save Changes"):
                        st.session_state.channel_manager.update_channel_prompt(selected_channel, edited_prompt)
                        del st.session_state.editing_prompt
                        st.success("Prompt updated successfully!")
                        st.rerun()
                
                with col2:
                    if st.button("❌ Cancel Edit"):
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
        
        # Script generation
        st.subheader("🎯 Generate New Script")
        extra_prompt = st.text_input("Extra prompt (optional):", help="Add any specific instructions for this generation")
        
        if st.button("🚀 Generate Script", type="primary"):
            if 'generating' not in st.session_state:
                st.session_state.generating = True
                
                with st.spinner("Generating script..."):
                    # Get used titles for exclusion
                    used_titles = st.session_state.channel_manager.get_used_titles(selected_channel)
                    
                    # Build exclusion list
                    base_prompt = st.session_state.channel_manager.get_channel_prompt(selected_channel)
                    full_prompt = base_prompt
                    
                    if used_titles:
                        # Create comprehensive exclusion list - AGGRESSIVE MOVIE VARIETY CHECKING
                        used_movies = set()
                        used_franchises = set()
                        used_keywords = set()
                        used_titles_list = list(used_titles)
                        
                        # Extract movie names, franchises, and key terms from ALL title formats
                        for title in used_titles_list:
                            title_lower = title.lower()
                            
                            # Pattern 1: "In Movie Name (Year)" - extract exact movie
                            match = re.search(r'^In (.+?) \(\d{4}\)', title)
                            if match:
                                movie_name = match.group(1)
                                used_movies.add(movie_name)
                                
                                # Extract franchise/series keywords
                                movie_lower = movie_name.lower()
                                if any(franchise in movie_lower for franchise in ['star wars', 'star trek', 'marvel', 'dc', 'batman', 'superman', 'spider-man', 'x-men', 'avengers', 'iron man', 'captain america', 'thor', 'guardians', 'fast', 'furious', 'mission impossible', 'john wick', 'terminator', 'alien', 'predator', 'matrix', 'lord of the rings', 'hobbit', 'harry potter', 'jurassic']):
                                    # Extract the franchise name
                                    for franchise in ['star wars', 'star trek', 'marvel', 'dc', 'batman', 'superman', 'spider-man', 'x-men', 'avengers', 'iron man', 'captain america', 'thor', 'guardians', 'fast', 'furious', 'mission impossible', 'john wick', 'terminator', 'alien', 'predator', 'matrix', 'lord of the rings', 'hobbit', 'harry potter', 'jurassic']:
                                        if franchise in movie_lower:
                                            used_franchises.add(franchise.title())
                                            break
                            
                            # Pattern 2: "Movie Name (Year)" (without "In")
                            elif re.search(r'^([^(]+) \(\d{4}\)', title):
                                match = re.search(r'^([^(]+) \(\d{4}\)', title)
                                movie_name = match.group(1).strip()
                                used_movies.add(movie_name)
                            
                            # Pattern 3: Extract any recognizable content
                            else:
                                clean_title = title.replace('In ', '').strip()
                                if '(' in clean_title and ')' in clean_title:
                                    movie_part = clean_title.split('(')[0].strip()
                                    if len(movie_part) > 3:
                                        used_movies.add(movie_part)
                            
                            # Extract key descriptive words to avoid similar topics
                            words = re.findall(r'\\b[a-zA-Z]{4,}\\b', title_lower)
                            for word in words:
                                if word not in ['movie', 'film', 'scene', 'short', 'year', 'when', 'that', 'this', 'they', 'were', 'with', 'from', 'have', 'been', 'their', 'would', 'could', 'should']:
                                    used_keywords.add(word)
                        
                        # Build comprehensive exclusion prompt
                        exclusion_parts = []
                        
                        # Exclude ALL used movies (not just 25)
                        if used_movies:
                            all_movies = list(used_movies)
                            exclusion_parts.append(f"BANNED MOVIES (DO NOT USE): {', '.join(all_movies)}")
                        
                        # Exclude franchises entirely
                        if used_franchises:
                            exclusion_parts.append(f"BANNED FRANCHISES (avoid entirely): {', '.join(used_franchises)}")
                        
                        # Build strong exclusion prompt
                        if exclusion_parts:
                            exclusion_text = " | ".join(exclusion_parts)
                            full_prompt = f"🚫 STRICT CONTENT VARIETY ENFORCEMENT: {exclusion_text}. You have already created {len(used_titles_list)} shorts. You MUST choose completely different movies, genres, decades, and topics. Prioritize variety - pick movies from different years, different genres, different studios. NO SEQUELS or related content to anything already used. {base_prompt}"
                        
                        # Add even more aggressive variety instructions
                        full_prompt += f" \\n\\n🎯 VARIETY REQUIREMENTS: Mix different decades (1970s, 1980s, 1990s, 2000s, 2010s, 2020s, and current 2025/recent releases), different genres (horror, comedy, drama, sci-fi, action, thriller, romance), different studios, and different countries of origin. Avoid any thematic similarities to existing content."
                    else:
                        # Even for first generation, encourage variety
                        full_prompt += " \\n\\n🎯 VARIETY PRIORITY: Ensure maximum variety in your selection. Choose movies from different decades (1970s through present day 2025), different genres (horror, comedy, drama, sci-fi, action, thriller, romance), different studios, and different countries. Avoid sequels or movies from the same franchise in a single batch."
                    
                    if extra_prompt.strip():
                        full_prompt += " " + extra_prompt.strip()
                    
                    # Generate script
                    session_id = str(uuid.uuid4())
                    result = st.session_state.claude_client.generate_script(full_prompt, session_id)
                    
                    if result["success"]:
                        # Extract and save titles
                        content = result["content"]
                        titles = extract_titles_from_response(content)
                        
                        for title in titles:
                            st.session_state.channel_manager.add_title(selected_channel, title)
                        
                        # Save script
                        st.session_state.channel_manager.save_script(selected_channel, content, session_id)
                        
                        # Display results
                        st.success(f"✅ Generated script successfully! Found {len(titles)} titles.")
                        
                        if titles:
                            st.subheader("📋 Extracted Titles:")
                            for i, title in enumerate(titles, 1):
                                st.write(f"{i}. {title}")
                        
                        st.subheader("📄 Generated Script:")
                        st.code(content, language="text")
                        
                        st.info(f"Session ID: {session_id}")
                        
                    else:
                        st.error(f"❌ Generation failed: {result['error']}")
                
                del st.session_state.generating
        
        # Show generation status
        if 'generating' in st.session_state:
            st.info("🔄 Generating script... Please wait.")
    
    else:
        st.info("👈 Select a channel from the sidebar or create a new one to get started!")
        st.markdown("""
        ### 🚀 Getting Started:
        1. **Create a Channel** - Add a new channel with your base prompt
        2. **Select Channel** - Choose which channel to generate scripts for  
        3. **Generate Scripts** - Create new YouTube Shorts scripts with AI
        4. **Real-time Sync** - All changes sync to Google Drive instantly
        """)


if __name__ == "__main__":
    main()