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
    
    def backup_channel_files(self, channel_name: str):
        """Create backup of channel files (titles and scripts)."""
        try:
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup titles file
            titles_filename = f"titles_{channel_name.lower()}.txt"
            titles_content = self.drive_manager.read_file(titles_filename, channel_folder_id)
            if titles_content:
                backup_titles = f"backup_titles_{channel_name.lower()}_{timestamp}.txt"
                self.drive_manager.write_file(backup_titles, titles_content, channel_folder_id)
            
            # Backup scripts file
            scripts_filename = f"saved_scripts_{channel_name.lower()}.txt"
            scripts_content = self.drive_manager.read_file(scripts_filename, channel_folder_id)
            if scripts_content:
                backup_scripts = f"backup_scripts_{channel_name.lower()}_{timestamp}.txt"
                self.drive_manager.write_file(backup_scripts, scripts_content, channel_folder_id)
            
            return True
        except Exception as e:
            st.error(f"Failed to backup {channel_name}: {str(e)}")
            return False
    
    def clear_titles(self, channel_name: str):
        """Clear all titles for a channel."""
        try:
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
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            filename = f"saved_scripts_{channel_name.lower()}.txt"
            self.drive_manager.write_file(filename, "", channel_folder_id)
            return True
        except Exception as e:
            st.error(f"Failed to clear scripts: {str(e)}")
            return False


def extract_titles_from_response(content: str) -> List[str]:
    """Extract ALL titles from the AI response."""
    titles_found = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        # Look for "TITLE:" format (case insensitive)
        if line.upper().startswith('TITLE:'):
            # Extract everything after "TITLE:"
            title = line[6:].strip()  # Remove "TITLE:" and whitespace
            
            # Clean up the title
            if title.endswith(' SHORT'):
                title = title[:-6].strip()
            
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
                last_backup_time = st.session_state.last_backup.get(channel_name, datetime.now() - timedelta(hours=4))
                if datetime.now() - last_backup_time > timedelta(hours=3):
                    # Perform backup
                    if st.session_state.channel_manager.backup_channel_files(channel_name):
                        st.session_state.last_backup[channel_name] = datetime.now()
        except Exception as e:
            # Silent fail for auto-backup
            pass
    
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
            
            # Show last backup time for admins
            if user_role == 'admin' and selected_channel:
                last_backup = st.session_state.last_backup.get(selected_channel)
                if last_backup:
                    time_since = datetime.now() - last_backup
                    hours = int(time_since.total_seconds() / 3600)
                    minutes = int((time_since.total_seconds() % 3600) / 60)
                    st.caption(f"🕐 Last backup: {hours}h {minutes}m ago")
                else:
                    st.caption("🕐 No backup yet")
        else:
            selected_channel = None
            st.info("No channels yet. Create one below!")
        
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
            col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
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
                    if st.session_state.channel_manager.backup_channel_files(selected_channel):
                        st.success(f"✅ Backup created for {selected_channel}")
                        st.session_state.last_backup[selected_channel] = datetime.now()
        
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
                        used_movies = set()
                        for title in used_titles:
                            match = re.search(r'^In (.+?) \(\d{4}\)', title)
                            if match:
                                used_movies.add(match.group(1))
                        
                        if used_movies:
                            exclusion_list = ", ".join(list(used_movies)[:10])
                            full_prompt = f"DO NOT use any of these movies: {exclusion_list}. Pick something completely different. {base_prompt}"
                    
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