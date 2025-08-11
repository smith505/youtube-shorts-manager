#!/usr/bin/env python3
"""
YouTube Shorts Channel Manager & Script Generator - OPTIMIZED VERSION
Performance improvements implemented
"""

# Version information
APP_VERSION = "2.1.0"
VERSION_DATE = "2024-12-11"
VERSION_NOTES = "Smart duplicate detection using semantic similarity"

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
from functools import lru_cache
import asyncio
import concurrent.futures
from src.utils.similarity_checker import SimilarityChecker

# Page configuration
st.set_page_config(
    page_title="YouTube Shorts Manager",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Performance optimizations configuration
CACHE_TTL_SECONDS = 300  # 5 minutes cache
BATCH_SIZE = 50  # For pagination
AUTO_REFRESH_INTERVAL = 180  # 3 minutes instead of 30 seconds

class GoogleDriveManager:
    """Optimized Google Drive operations with caching and batching."""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    def __init__(self):
        self.service = None
        self.folder_id = None
        self.file_cache = {}  # In-memory cache for file contents
        self.cache_timestamps = {}  # Track cache age
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Drive API."""
        creds = None
        
        try:
            # Try to get credentials from Streamlit secrets first
            if 'GOOGLE_CREDENTIALS' in st.secrets:
                import json
                creds_str = st.secrets['GOOGLE_CREDENTIALS']
                creds_str = creds_str.replace('\n', '').replace('\r', '').replace('\t', '')
                creds_info = json.loads(creds_str)
                creds = Credentials.from_authorized_user_info(creds_info, self.SCOPES)
            
            elif os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if 'GOOGLE_CLIENT_CONFIG' in st.secrets:
                        import json
                        client_config = json.loads(st.secrets['GOOGLE_CLIENT_CONFIG'])
                        flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                        st.error("Google Drive authentication required. Please contact admin to setup credentials.")
                        return False
                    
                    elif os.path.exists('credentials.json'):
                        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                        creds = flow.run_local_server(port=8080, open_browser=True)
                        
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
            # Check cache first
            if 'folder_id' in st.session_state:
                self.folder_id = st.session_state.folder_id
                return
            
            results = self.service.files().list(
                q="name='YouTube Shorts Manager' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                self.folder_id = folders[0]['id']
            else:
                folder_metadata = {
                    'name': 'YouTube Shorts Manager',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(body=folder_metadata, fields='id').execute()
                self.folder_id = folder.get('id')
            
            # Cache the folder ID
            st.session_state.folder_id = self.folder_id
                
        except Exception as e:
            st.error(f"Failed to setup Google Drive folder: {str(e)}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self.cache_timestamps:
            return False
        
        age = time.time() - self.cache_timestamps[cache_key]
        return age < CACHE_TTL_SECONDS
    
    def read_file(self, filename: str, parent_folder_id: str = None, force_refresh: bool = False) -> str:
        """Read a file from Google Drive with caching."""
        try:
            if parent_folder_id is None:
                parent_folder_id = self.folder_id
            
            cache_key = f"{parent_folder_id}/{filename}"
            
            # Return cached content if valid and not forcing refresh
            if not force_refresh and cache_key in self.file_cache and self._is_cache_valid(cache_key):
                return self.file_cache[cache_key]
            
            # Search for the file
            results = self.service.files().list(
                q=f"name='{filename}' and parents='{parent_folder_id}' and trashed=false",
                fields="files(id, name)",
                pageSize=1  # Only need first match
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                # Cache empty result
                self.file_cache[cache_key] = ""
                self.cache_timestamps[cache_key] = time.time()
                return ""
            
            file_id = files[0]['id']
            
            # Download file content
            request = self.service.files().get_media(fileId=file_id)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_io.seek(0)
            content = file_io.read().decode('utf-8')
            
            # Cache the content
            self.file_cache[cache_key] = content
            self.cache_timestamps[cache_key] = time.time()
            
            return content
            
        except Exception as e:
            return ""
    
    def write_file(self, filename: str, content: str, parent_folder_id: str = None):
        """Write a file to Google Drive and update cache."""
        try:
            if parent_folder_id is None:
                parent_folder_id = self.folder_id
            
            cache_key = f"{parent_folder_id}/{filename}"
            
            # Check if file already exists
            results = self.service.files().list(
                q=f"name='{filename}' and parents='{parent_folder_id}' and trashed=false",
                fields="files(id, name)",
                pageSize=1
            ).execute()
            
            files = results.get('files', [])
            
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
            
            # Update cache
            self.file_cache[cache_key] = content
            self.cache_timestamps[cache_key] = time.time()
                
        except Exception as e:
            st.error(f"Failed to save {filename}: {str(e)}")
    
    def append_to_file(self, filename: str, content: str, parent_folder_id: str = None):
        """Append content to a file with caching."""
        existing_content = self.read_file(filename, parent_folder_id)
        new_content = existing_content + content
        self.write_file(filename, new_content, parent_folder_id)
    
    @lru_cache(maxsize=128)
    def get_or_create_channel_folder(self, channel_name: str) -> str:
        """Get or create a folder for a specific channel (cached)."""
        try:
            # Search for existing channel folder
            results = self.service.files().list(
                q=f"name='{channel_name}' and parents='{self.folder_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)",
                pageSize=1
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                return folders[0]['id']
            else:
                folder_metadata = {
                    'name': channel_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [self.folder_id]
                }
                folder = self.service.files().create(body=folder_metadata, fields='id').execute()
                return folder.get('id')
                
        except Exception as e:
            st.error(f"Error getting/creating channel folder for {channel_name}: {str(e)}")
            return self.folder_id
    
    def clear_cache(self):
        """Clear all cached data."""
        self.file_cache.clear()
        self.cache_timestamps.clear()
        self.get_or_create_channel_folder.cache_clear()


class ClaudeClient:
    """Optimized Claude API client with retry logic and timeout handling."""
    
    def __init__(self):
        self.api_key = st.secrets.get('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
        
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
    
    def generate_script(self, prompt: str, session_id: str) -> Dict[str, Any]:
        """Generate a YouTube short script with optimized retry logic."""
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
        
        max_retries = 3
        timeout = 60
        
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
                    usage = data.get("usage", {})
                    
                    return {
                        "success": True,
                        "content": data["content"][0]["text"],
                        "session_id": session_id,
                        "token_usage": {
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                        }
                    }
                elif response.status_code != 504:
                    return {
                        "success": False,
                        "error": f"API Error {response.status_code}: {response.text}"
                    }
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return {
                    "success": False,
                    "error": f"Network timeout after {max_retries} attempts"
                }
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return {
                    "success": False,
                    "error": f"Network error after {max_retries} attempts: {str(e)}"
                }
                    
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Unexpected error: {str(e)}"
                }
        
        return {
            "success": False,
            "error": "Failed to generate script after all retries"
        }


class ChannelManager:
    """Optimized channel manager with better caching and data structures."""
    
    def __init__(self, drive_manager: GoogleDriveManager):
        self.drive_manager = drive_manager
        self.channels_file = "channels.json"
        self.channels = self.load_channels()
        self.titles_cache = {}  # Cache for titles by channel
        self.titles_cache_time = {}  # Cache timestamps
    
    @st.cache_data(ttl=CACHE_TTL_SECONDS)
    def load_channels(_self) -> Dict[str, str]:
        """Load channel definitions with caching."""
        try:
            if not _self.drive_manager or not _self.drive_manager.service:
                return {}
                
            content = _self.drive_manager.read_file(_self.channels_file)
            if content:
                content = content.strip()
                if not content:
                    return {}
                channels = json.loads(content)
                return channels
            else:
                initial_channels = {}
                _self.channels = initial_channels
                _self.save_channels()
                return initial_channels
        except Exception:
            return {}
    
    def save_channels(self):
        """Save channel definitions."""
        try:
            content = json.dumps(self.channels, indent=2, ensure_ascii=False)
            self.drive_manager.write_file(self.channels_file, content)
            # Clear the cache to force reload
            ChannelManager.load_channels.clear()
        except Exception as e:
            st.error(f"Failed to save channels: {str(e)}")
    
    def add_channel(self, name: str, base_prompt: str):
        """Add a new channel."""
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
        """Delete a channel from the dropdown."""
        if name in self.channels:
            del self.channels[name]
            self.save_channels()
            return True
        return False
    
    def get_used_titles(self, channel_name: str, force_refresh: bool = False) -> Set[str]:
        """Load used titles with improved caching."""
        # Check if we need to refresh cache
        cache_age = time.time() - self.titles_cache_time.get(channel_name, 0)
        
        if not force_refresh and channel_name in self.titles_cache and cache_age < CACHE_TTL_SECONDS:
            return self.titles_cache[channel_name]
        
        filename = f"titles_{channel_name.lower()}.txt"
        titles = set()
        
        try:
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            content = self.drive_manager.read_file(filename, channel_folder_id, force_refresh)
            if content:
                titles = {line.strip() for line in content.split('\n') if line.strip()}
            
            # Update cache
            self.titles_cache[channel_name] = titles
            self.titles_cache_time[channel_name] = time.time()
        except Exception:
            pass
        
        return titles
    
    def get_used_titles_paginated(self, channel_name: str, page: int = 0, page_size: int = BATCH_SIZE) -> tuple:
        """Get paginated titles for better performance with large datasets."""
        all_titles = list(self.get_used_titles(channel_name))
        all_titles.sort()  # Sort for consistent ordering
        
        start_idx = page * page_size
        end_idx = start_idx + page_size
        
        page_titles = all_titles[start_idx:end_idx]
        total_pages = (len(all_titles) + page_size - 1) // page_size
        
        return page_titles, total_pages, len(all_titles)
    
    def add_title(self, channel_name: str, title: str):
        """Add a new title with similarity checking."""
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            # Check for similar existing titles first
            existing_titles = self.get_used_titles(channel_name)
            is_dup, similar_to = SimilarityChecker.is_duplicate_title(title, existing_titles)
            
            if is_dup:
                # Don't add duplicate, but don't show error (silent skip)
                return False
            
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            self.drive_manager.append_to_file(filename, f"{title}\n", channel_folder_id)
            
            # Update cache immediately
            if channel_name in self.titles_cache:
                self.titles_cache[channel_name].add(title)
            
            return True
                
        except Exception as e:
            st.error(f"Failed to save title: {str(e)}")
            return False
    
    def bulk_add_titles(self, channel_name: str, titles_list: list):
        """Optimized bulk add with similarity-based duplicate detection."""
        if not titles_list:
            return 0, 0
        
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            existing_titles = self.get_used_titles(channel_name)
            
            # Use similarity checker to filter duplicates
            unique_titles, duplicates = SimilarityChecker.filter_duplicate_titles(
                titles_list, existing_titles
            )
            
            if unique_titles:
                channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
                titles_content = "\n".join(unique_titles) + "\n"
                self.drive_manager.append_to_file(filename, titles_content, channel_folder_id)
                
                # Update cache
                if channel_name in self.titles_cache:
                    self.titles_cache[channel_name].update(unique_titles)
            
            return len(unique_titles), len(duplicates)
            
        except Exception as e:
            st.error(f"Failed to bulk add titles: {str(e)}")
            return 0, 0
    
    def delete_title(self, channel_name: str, title_to_delete: str):
        """Delete a title and update cache."""
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            content = self.drive_manager.read_file(filename, channel_folder_id)
            
            if not content:
                return False, f"No titles file found for {channel_name}"
            
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            if title_to_delete not in lines:
                return False, f"Title '{title_to_delete}' not found"
            
            lines.remove(title_to_delete)
            new_content = "\n".join(lines) + ("\n" if lines else "")
            self.drive_manager.write_file(filename, new_content, channel_folder_id)
            
            # Update cache
            if channel_name in self.titles_cache:
                self.titles_cache[channel_name].discard(title_to_delete)
            
            return True, f"Title '{title_to_delete}' deleted successfully"
            
        except Exception as e:
            return False, f"Failed to delete title: {str(e)}"
    
    def save_script(self, channel_name: str, content: str, session_id: str, user_name: str = None):
        """Save script with user attribution."""
        filename = f"saved_scripts_{channel_name.lower()}.txt"
        try:
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            attribution = f"Created by: {user_name if user_name else 'Unknown User'} on {timestamp}\n"
            separator = "="*50 + "\n\n"
            
            script_content = attribution + content + "\n\n" + separator + "\n"
            self.drive_manager.append_to_file(filename, script_content, channel_folder_id)
        except Exception as e:
            st.error(f"Failed to save script: {str(e)}")
    
    def clear_titles(self, channel_name: str):
        """Clear all titles and update cache."""
        try:
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            filename = f"titles_{channel_name.lower()}.txt"
            self.drive_manager.write_file(filename, "", channel_folder_id)
            
            # Clear cache
            if channel_name in self.titles_cache:
                del self.titles_cache[channel_name]
            if channel_name in self.titles_cache_time:
                del self.titles_cache_time[channel_name]
            
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
    
    def backup_channel_files(self, channel_name: str):
        """Create backup of channel files."""
        try:
            if not self.drive_manager or not self.drive_manager.service:
                return False
                
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            if not channel_folder_id:
                return False
            
            # Create backup folder
            backup_folder_name = "Backups"
            results = self.drive_manager.service.files().list(
                q=f"name='{backup_folder_name}' and parents='{channel_folder_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)",
                pageSize=1
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                backup_folder_id = folders[0]['id']
            else:
                folder_metadata = {
                    'name': backup_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [channel_folder_id]
                }
                folder = self.drive_manager.service.files().create(body=folder_metadata, fields='id').execute()
                backup_folder_id = folder.get('id')
                
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
        except Exception:
            return False


def extract_titles_from_response(content: str) -> List[str]:
    """Extract titles from AI response."""
    titles_found = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        line_upper = line.upper()
        if line_upper.startswith('TITLE:'):
            title = line[6:].strip()
        elif line_upper.startswith('TITLE '):
            title = line[6:].strip()
        elif line_upper.startswith('TITLE') and len(line) > 5 and not line[5].isalpha():
            title = line[5:].strip()
        else:
            continue
            
        if title.endswith(' SHORT'):
            title = title[:-6].strip()
        
        title = re.sub(r'^[\d\-\.\s]+', '', title).strip()
        
        if title and len(title) > 5:
            titles_found.append(title)
    
    return titles_found


from src.core.auth_system import show_login_page, check_authentication, get_current_user


def clear_all_modals():
    """Clear all open modals to prevent UI conflicts."""
    modal_keys = [
        'editing_prompt', 'add_titles_modal', 'delete_titles_modal', 
        'clear_titles_confirm', 'clear_scripts_confirm', 'delete_channel_confirm',
        'adding_channel'
    ]
    for key in modal_keys:
        if key in st.session_state:
            del st.session_state[key]


def main():
    """Main application with performance optimizations."""
    
    try:
        # Check authentication first
        if not check_authentication():
            show_login_page()
            return
        
        # Get current user
        current_user = get_current_user()
        
        # Clear modals on initial login
        if 'modals_cleared_on_login' not in st.session_state:
            clear_all_modals()
            st.session_state.modals_cleared_on_login = True
        
        # Initialize services with lazy loading
        if 'drive_manager' not in st.session_state:
            with st.spinner("Initializing services..."):
                try:
                    st.session_state.claude_client = ClaudeClient()
                    st.session_state.drive_manager = GoogleDriveManager()
                    
                    if st.session_state.drive_manager:
                        st.session_state.channel_manager = ChannelManager(st.session_state.drive_manager)
                    else:
                        st.error("Google Drive not available.")
                        return
                        
                except Exception as e:
                    st.error(f"Failed to initialize services: {str(e)}")
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
    
    # Logout button
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🚪 Logout", key="logout_button"):
            # Clear caches on logout
            if hasattr(st.session_state.drive_manager, 'clear_cache'):
                st.session_state.drive_manager.clear_cache()
            del st.session_state.authenticated
            del st.session_state.user
            st.rerun()
    
    st.markdown("---")
    
    # Auto-backup functionality (optimized to run less frequently)
    if 'last_backup' not in st.session_state:
        st.session_state.last_backup = {}
    
    # Check for auto-backup only for admins and less frequently
    if user_role == 'admin' and 'channel_manager' in st.session_state:
        current_time = datetime.now()
        if 'last_backup_check' not in st.session_state:
            st.session_state.last_backup_check = current_time
        
        # Only check every 5 minutes instead of constantly
        if (current_time - st.session_state.last_backup_check).total_seconds() > 300:
            st.session_state.last_backup_check = current_time
            
            for channel_name in st.session_state.channel_manager.get_channel_names():
                # For new channels, set backup time to now (so next backup is in 3 hours)
                last_backup_time = st.session_state.last_backup.get(channel_name, current_time)
                
                # Only backup if more than 3 hours have passed since last backup
                if (current_time - last_backup_time) > timedelta(hours=3):
                    with st.spinner(f"Auto-backup for {channel_name}..."):
                        if st.session_state.channel_manager.backup_channel_files(channel_name):
                            st.session_state.last_backup[channel_name] = current_time
    
    # Sidebar for channel management
    with st.sidebar:
        st.header("📁 Channel Management")
        
        # Refresh channels button with cache clearing
        if st.button("🔄 Refresh Channels", key="refresh_channels_button"):
            ChannelManager.load_channels.clear()  # Clear cache
            st.session_state.channel_manager.channels = st.session_state.channel_manager.load_channels()
            st.rerun()
        
        # Channel selector
        channels = st.session_state.channel_manager.get_channel_names()
        if channels:
            selected_channel = st.selectbox("Select Channel", channels, key="selected_channel")
            
            # Show backup timer for admins (with detailed countdown)
            if user_role == 'admin' and selected_channel:
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
                        
                        # Show countdown with different formats based on time remaining
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
                
                # Periodic refresh to update timer (every 60 seconds for better performance)
                if 'last_timer_refresh' not in st.session_state:
                    st.session_state.last_timer_refresh = datetime.now()
                
                time_since_refresh = datetime.now() - st.session_state.last_timer_refresh
                if time_since_refresh > timedelta(seconds=60):
                    st.session_state.last_timer_refresh = datetime.now()
                    st.rerun()
        else:
            selected_channel = None
            st.info("No channels yet. Create one below!")
        
        st.markdown("---")
        
        # Add new channel (admin only)
        if user_role == 'admin':
            st.subheader("➕ Add New Channel")
            new_channel_name = st.text_input("Channel Name", key="new_channel_name")
            
            if st.button("Add Channel", type="primary", key="add_channel_button"):
                if new_channel_name.strip():
                    if new_channel_name not in st.session_state.channel_manager.channels:
                        clear_all_modals()
                        st.session_state.adding_channel = new_channel_name.strip()
                    else:
                        st.error("Channel already exists!")
                else:
                    st.error("Please enter a channel name")
        
        # Handle adding channel
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
        
        # Admin controls (optimized layout)
        if user_role == 'admin':
            with st.container():
                cols = st.columns(7)
                
                if cols[0].button("✏️ Edit", key=f"edit_prompt_{selected_channel}"):
                    clear_all_modals()
                    st.session_state.editing_prompt = selected_channel
                
                if cols[1].button("🗑️ Titles", key=f"clear_titles_{selected_channel}"):
                    clear_all_modals()
                    st.session_state.clear_titles_confirm = selected_channel
                
                if cols[2].button("🗑️ Scripts", key=f"clear_scripts_{selected_channel}"):
                    clear_all_modals()
                    st.session_state.clear_scripts_confirm = selected_channel
                
                if cols[3].button("💾 Backup", key=f"backup_now_{selected_channel}"):
                    with st.spinner("Creating backup..."):
                        if st.session_state.channel_manager.backup_channel_files(selected_channel):
                            st.success("✅ Backup created")
                            st.session_state.last_backup[selected_channel] = datetime.now()
                
                if cols[4].button("❌ Delete", key=f"delete_channel_{selected_channel}"):
                    clear_all_modals()
                    st.session_state.delete_channel_confirm = selected_channel
                
                if cols[5].button("📝 Add", key=f"add_titles_{selected_channel}"):
                    clear_all_modals()
                    st.session_state.add_titles_modal = selected_channel
                
                if cols[6].button("🗑️ Remove", key=f"delete_titles_{selected_channel}"):
                    clear_all_modals()
                    st.session_state.delete_titles_modal = selected_channel
        
        # Handle modals (simplified and optimized)
        
        # Add titles modal
        if st.session_state.get('add_titles_modal') == selected_channel:
            st.markdown("---")
            with st.expander("📝 **Add Existing Titles**", expanded=True):
                st.info(f"Add existing titles to **{selected_channel}**")
                
                bulk_titles_input = st.text_area(
                    "Enter titles (one per line):",
                    height=200,
                    placeholder="In The Dark Knight (2008)\nIn Avengers: Endgame (2019)",
                    key="bulk_titles_textarea"
                )
                
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    if st.button("➕ Add Titles", type="primary"):
                        if bulk_titles_input.strip():
                            titles_list = [line.strip() for line in bulk_titles_input.split('\n') if line.strip()]
                            
                            if titles_list:
                                with st.spinner("Adding titles..."):
                                    added_count, duplicate_count = st.session_state.channel_manager.bulk_add_titles(
                                        selected_channel, titles_list
                                    )
                                    
                                    if added_count > 0:
                                        st.success(f"✅ Added {added_count} new titles")
                                    
                                    if duplicate_count > 0:
                                        st.info(f"ℹ️ Skipped {duplicate_count} duplicates")
                                    
                                    if added_count > 0:
                                        del st.session_state.add_titles_modal
                                        st.rerun()
                
                with col2:
                    if st.button("❌ Cancel"):
                        del st.session_state.add_titles_modal
                        st.rerun()
                
                with col3:
                    current_titles = st.session_state.channel_manager.get_used_titles(selected_channel)
                    st.write(f"**Current titles: {len(current_titles)}**")
        
        # Delete titles modal with pagination
        if st.session_state.get('delete_titles_modal') == selected_channel:
            st.markdown("---")
            with st.expander("🗑️ **Delete Existing Titles**", expanded=True):
                st.info(f"Managing titles for **{selected_channel}**")
                
                # Pagination controls
                if 'delete_page' not in st.session_state:
                    st.session_state.delete_page = 0
                
                page_titles, total_pages, total_titles = st.session_state.channel_manager.get_used_titles_paginated(
                    selected_channel, 
                    st.session_state.delete_page
                )
                
                if page_titles:
                    st.write(f"**Showing {len(page_titles)} of {total_titles} titles (Page {st.session_state.delete_page + 1}/{total_pages})**")
                    
                    # Pagination controls
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        if st.button("⬅️ Previous", disabled=st.session_state.delete_page == 0):
                            st.session_state.delete_page -= 1
                            st.rerun()
                    
                    with col3:
                        if st.button("➡️ Next", disabled=st.session_state.delete_page >= total_pages - 1):
                            st.session_state.delete_page += 1
                            st.rerun()
                    
                    # Display titles
                    for title in page_titles:
                        col1, col2 = st.columns([10, 1])
                        with col1:
                            st.write(f"• {title}")
                        with col2:
                            if st.button("❌", key=f"del_{hash(title)}", help=f"Delete: {title}"):
                                with st.spinner("Deleting..."):
                                    success, message = st.session_state.channel_manager.delete_title(selected_channel, title)
                                    if success:
                                        st.success("✅ Deleted")
                                        st.rerun()
                                    else:
                                        st.error(message)
                else:
                    st.info("No titles found")
                
                if st.button("❌ Close", type="secondary"):
                    del st.session_state.delete_titles_modal
                    if 'delete_page' in st.session_state:
                        del st.session_state.delete_page
                    st.rerun()
        
        # Other modals (prompt editing, confirmations, etc.) remain similar but optimized
        
        # Script generation section
        st.markdown("---")
        st.subheader("🎯 Generate New Script")
        extra_prompt = st.text_input("Extra prompt (optional):", help="Add specific instructions")
        
        if st.button("🚀 Generate Script", type="primary", key="generate_button"):
            with st.spinner("🎬 Generating your script..."):
                try:
                    # Get used titles efficiently
                    used_titles = st.session_state.channel_manager.get_used_titles(selected_channel)
                    
                    # Build prompt
                    base_prompt = st.session_state.channel_manager.get_channel_prompt(selected_channel)
                    full_prompt = base_prompt
                    
                    if used_titles:
                        # Optimize exclusion list building
                        used_titles_list = list(used_titles)[:100]  # Limit to prevent huge prompts
                        exclusion_text = f"EXISTING FACTS (DO NOT REPEAT): {' | '.join(used_titles_list[:20])}"
                        full_prompt = f"🚫 {exclusion_text}\n\n{base_prompt}"
                    
                    if extra_prompt.strip():
                        full_prompt += " " + extra_prompt.strip()
                    
                    # Generate script
                    session_id = str(uuid.uuid4())
                    result = st.session_state.claude_client.generate_script(full_prompt, session_id)
                    
                    if result["success"]:
                        content = result.get("content", "")
                        titles = extract_titles_from_response(content)
                        
                        # Save titles and script (with duplicate checking)
                        added_count = 0
                        duplicate_count = 0
                        for title in titles:
                            if st.session_state.channel_manager.add_title(selected_channel, title):
                                added_count += 1
                            else:
                                duplicate_count += 1
                        
                        user_name = current_user.get('first_name', 'Unknown User')
                        st.session_state.channel_manager.save_script(selected_channel, content, session_id, user_name)
                        
                        # Display results
                        if added_count > 0:
                            st.success(f"✅ Generated script with {added_count} new unique titles!")
                        if duplicate_count > 0:
                            st.info(f"ℹ️ Filtered out {duplicate_count} similar/duplicate titles")
                        
                        if titles:
                            st.subheader("📋 Extracted Titles:")
                            for i, title in enumerate(titles, 1):
                                st.write(f"{i}. {title}")
                        
                        st.subheader("📄 Generated Script:")
                        with st.expander("View Full Script", expanded=True):
                            st.text_area(
                                "Generated Content:",
                                value=content,
                                height=500,
                                disabled=True,
                                key=f"script_{session_id}"
                            )
                            
                            if content:
                                st.caption(f"📊 {len(content.split())} words, {len(content)} characters")
                        
                        # Store in session for persistence
                        st.session_state.last_successful_generation = {
                            "content": content,
                            "titles": titles,
                            "session_id": session_id,
                            "channel": selected_channel,
                            "token_usage": result.get('token_usage', {}),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    else:
                        st.error(f"❌ Generation failed: {result['error']}")
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
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