#!/usr/bin/env python3
"""
YouTube Shorts Channel Manager & Script Generator with Google Drive Integration

Dependencies: 
  pip install requests google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2

Setup:
  1. Set environment variable: set ANTHROPIC_API_KEY=your_key_here (Windows) or export ANTHROPIC_API_KEY="your_key_here" (Mac/Linux)
  2. Google Drive API Setup:
     a) Go to https://console.cloud.google.com/
     b) Create a new project or select existing one
     c) Enable the Google Drive API
     d) Create credentials (OAuth 2.0 Client ID) for "Desktop application"
     e) Download the credentials JSON file and save it as "credentials.json" in the same folder as this script
  3. Run: python app.py
  
Features:
  • All files (channels.json, titles_*.txt, saved_scripts_*.txt) are stored on Google Drive
  • Real-time collaboration - multiple users can use the same Google Drive folder
  • Automatic sync - changes are immediately visible to all users
  • Creates a "YouTube Shorts Manager" folder in your Google Drive

First run will open a browser for Google authentication. Grant access to Google Drive.
"""

import os
import json
import uuid
import requests
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import threading
from typing import Dict, List, Set, Optional, Any
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


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
        
        # Load existing token if available
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    messagebox.showerror(
                        "Authentication Error", 
                        "credentials.json file not found. Please follow the setup instructions."
                    )
                    return False
                
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=8080, open_browser=True)
            
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('drive', 'v3', credentials=creds)
        self.setup_app_folder()
        return True
    
    def setup_app_folder(self):
        """Create or find the app folder on Google Drive."""
        try:
            # Search for existing folder
            results = self.service.files().list(
                q="name='YouTube Shorts Manager' and mimeType='application/vnd.google-apps.folder'",
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
            messagebox.showerror("Google Drive Error", f"Failed to setup folder: {str(e)}")
    
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
            print(f"Error reading {filename}: {str(e)}")
            return ""
    
    def write_file(self, filename: str, content: str, parent_folder_id: str = None):
        """Write a file to Google Drive."""
        try:
            if parent_folder_id is None:
                parent_folder_id = self.folder_id
                
            print(f"DEBUG: write_file called - filename={filename}, parent_folder_id={parent_folder_id}")
            
            # Check if file already exists (exclude trashed files)
            results = self.service.files().list(
                q=f"name='{filename}' and parents='{parent_folder_id}' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            print(f"DEBUG: Found {len(files)} existing files with name {filename}")
            
            # Prepare content
            media = MediaIoBaseUpload(
                io.BytesIO(content.encode('utf-8')),
                mimetype='text/plain',
                resumable=True
            )
            
            if files:
                # Update existing file
                file_id = files[0]['id']
                print(f"DEBUG: Updating existing file {file_id}")
                self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                print(f"DEBUG: File updated successfully")
            else:
                # Create new file
                print(f"DEBUG: Creating new file {filename}")
                file_metadata = {
                    'name': filename,
                    'parents': [parent_folder_id]
                }
                result = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                print(f"DEBUG: New file created with ID: {result.get('id')}")
                
        except Exception as e:
            print(f"DEBUG: write_file failed: {str(e)}")
            messagebox.showerror("Google Drive Error", f"Failed to save {filename}: {str(e)}")
            raise e
    
    def append_to_file(self, filename: str, content: str, parent_folder_id: str = None):
        """Append content to a file on Google Drive."""
        try:
            print(f"DEBUG: append_to_file called with filename={filename}, parent_folder_id={parent_folder_id}")
            existing_content = self.read_file(filename, parent_folder_id)
            print(f"DEBUG: Existing content length: {len(existing_content)} chars")
            new_content = existing_content + content
            print(f"DEBUG: New total content length: {len(new_content)} chars")
            self.write_file(filename, new_content, parent_folder_id)
            print(f"DEBUG: append_to_file completed successfully")
        except Exception as e:
            print(f"DEBUG: append_to_file failed: {str(e)}")
            raise e
    
    def list_folder_contents(self, folder_id: str = None) -> List[Dict]:
        """List contents of a folder on Google Drive."""
        try:
            if folder_id is None:
                folder_id = self.folder_id
                
            results = self.service.files().list(
                q=f"parents='{folder_id}' and trashed=false",
                fields="files(id, name, mimeType, modifiedTime)",
                orderBy="name"
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            print(f"Error listing folder contents: {str(e)}")
            return []
    
    def create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Create a new folder on Google Drive."""
        try:
            if parent_id is None:
                parent_id = self.folder_id
                
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            folder = self.service.files().create(body=folder_metadata, fields='id').execute()
            return folder.get('id')
        except Exception as e:
            messagebox.showerror("Google Drive Error", f"Failed to create folder: {str(e)}")
            return None
    
    def delete_file_or_folder(self, file_id: str) -> bool:
        """Delete a file or folder from Google Drive."""
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            messagebox.showerror("Google Drive Error", f"Failed to delete: {str(e)}")
            return False
    
    def get_folder_path(self, folder_id: str) -> str:
        """Get the full path of a folder."""
        try:
            if folder_id == self.folder_id:
                return "YouTube Shorts Manager"
                
            file = self.service.files().get(fileId=folder_id, fields='name, parents').execute()
            folder_name = file.get('name')
            parents = file.get('parents', [])
            
            if parents and parents[0] != self.folder_id:
                parent_path = self.get_folder_path(parents[0])
                return f"{parent_path}/{folder_name}"
            else:
                return f"YouTube Shorts Manager/{folder_name}"
        except:
            return "Unknown"
    
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
                print(f"DEBUG: Found existing folder for {channel_name}: {folders[0]['id']}")
                return folders[0]['id']
            else:
                # Create new channel folder
                new_folder_id = self.create_folder(channel_name, self.folder_id)
                print(f"DEBUG: Created new folder for {channel_name}: {new_folder_id}")
                return new_folder_id
                
        except Exception as e:
            print(f"DEBUG: Error getting/creating channel folder for {channel_name}: {str(e)}")
            return self.folder_id  # Fallback to main folder


class ClaudeClient:
    """Handles all Claude API interactions."""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
    
    def generate_script(self, prompt: str, session_id: str) -> Dict[str, Any]:
        """
        Generate a YouTube short script using Claude API.
        
        Args:
            prompt: The complete prompt including base + extra instructions
            session_id: Unique session identifier for fresh chat
            
        Returns:
            Dict with success status, content, and session_id
        """
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
            content = self.drive_manager.read_file(self.channels_file)
            if content:
                return json.loads(content)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Failed to load channels from Google Drive: {str(e)}")
        return {}
    
    def save_channels(self):
        """Save channel definitions to Google Drive channels.json."""
        try:
            content = json.dumps(self.channels, indent=2, ensure_ascii=False)
            self.drive_manager.write_file(self.channels_file, content)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save channels to Google Drive: {str(e)}")
    
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
            print(f"Failed to load titles for {channel_name} from Google Drive: {str(e)}")
        return titles
    
    def add_title(self, channel_name: str, title: str):
        """Add a new title to a channel's Google Drive folder."""
        filename = f"titles_{channel_name.lower()}.txt"
        try:
            # Get or create the channel folder
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            print(f"DEBUG: Channel folder ID for {channel_name}: {channel_folder_id}")
            self.drive_manager.append_to_file(filename, f"{title}\n", channel_folder_id)
            print(f"DEBUG: Successfully saved title '{title}' to {channel_name}/{filename}")
        except Exception as e:
            print(f"DEBUG: Error saving title: {str(e)}")
            messagebox.showerror("Error", f"Failed to save title for {channel_name} to Google Drive: {str(e)}")
    
    def save_script(self, channel_name: str, content: str, session_id: str):
        """Save the full generated script to a channel's Google Drive folder."""
        filename = f"saved_scripts_{channel_name.lower()}.txt"
        try:
            # Get or create the channel folder
            channel_folder_id = self.drive_manager.get_or_create_channel_folder(channel_name)
            print(f"DEBUG: Saving script to folder {channel_folder_id}, filename: {filename}")
            print(f"DEBUG: Script content length: {len(content)} chars")
            script_content = content + "\n\n\n"  # Add three blank lines between scripts
            self.drive_manager.append_to_file(filename, script_content, channel_folder_id)
            print(f"DEBUG: Successfully saved script to Google Drive {channel_name}/{filename}")
            
            # Verify the file was created/updated
            verification_content = self.drive_manager.read_file(filename, channel_folder_id)
            print(f"DEBUG: Verification - file now contains {len(verification_content)} chars")
            
            # List contents of channel folder to verify file exists
            folder_contents = self.drive_manager.list_folder_contents(channel_folder_id)
            print(f"DEBUG: Channel folder contains {len(folder_contents)} files:")
            for file_info in folder_contents:
                print(f"  - {file_info.get('name', 'Unknown')} ({file_info.get('mimeType', 'Unknown type')})")
        except Exception as e:
            print(f"DEBUG: Error saving script: {str(e)}")
            messagebox.showerror("Error", f"Failed to save script for {channel_name} to Google Drive: {str(e)}")
    
    def is_title_used(self, channel_name: str, title: str) -> bool:
        """Check if a title has already been used for this channel."""
        used_titles = self.get_used_titles(channel_name)
        return title.lower().strip() in {t.lower().strip() for t in used_titles}


class MainApp:
    """Main Tkinter GUI application."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Shorts Channel Manager")
        self.root.geometry("800x700")
        
        # Initialize components
        try:
            self.claude_client = ClaudeClient()
        except ValueError as e:
            messagebox.showerror("Configuration Error", str(e))
            self.root.quit()
            return
        
        # Initialize Google Drive Manager
        try:
            self.drive_manager = GoogleDriveManager()
            if not self.drive_manager.service:
                messagebox.showerror("Google Drive Error", "Failed to authenticate with Google Drive")
                self.root.quit()
                return
        except Exception as e:
            messagebox.showerror("Google Drive Error", f"Failed to initialize Google Drive: {str(e)}")
            self.root.quit()
            return
        
        self.channel_manager = ChannelManager(self.drive_manager)
        self.is_generating = False
        self.saved_password = None  # Store password if user chooses to remember it
        
        self.setup_gui()
        self.refresh_channels()
    
    def setup_gui(self):
        """Create and layout all GUI components."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Channel Management Section
        ttk.Label(main_frame, text="Channel Management", font=("Arial", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10)
        )
        
        # Channel selector
        ttk.Label(main_frame, text="Select Channel:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.channel_var = tk.StringVar()
        self.channel_combo = ttk.Combobox(main_frame, textvariable=self.channel_var, state="readonly", width=30)
        self.channel_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.channel_combo.bind("<<ComboboxSelected>>", self.on_channel_selected)
        
        # Edit prompt button
        self.edit_prompt_btn = ttk.Button(main_frame, text="Edit Prompt", command=self.edit_channel_prompt)
        self.edit_prompt_btn.grid(row=1, column=2)
        
        # Add channel section
        ttk.Label(main_frame, text="New Channel Name:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.new_channel_var = tk.StringVar()
        self.new_channel_entry = ttk.Entry(main_frame, textvariable=self.new_channel_var, width=30)
        self.new_channel_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(10, 0))
        
        self.add_channel_btn = ttk.Button(main_frame, text="Add Channel", command=self.add_channel)
        self.add_channel_btn.grid(row=2, column=2, pady=(10, 0))
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=20)
        
        # Generation Section
        ttk.Label(main_frame, text="Short Generation", font=("Arial", 12, "bold")).grid(
            row=4, column=0, columnspan=3, sticky=tk.W, pady=(0, 10)
        )
        
        # Extra prompt
        ttk.Label(main_frame, text="Extra Prompt (optional):").grid(row=5, column=0, sticky=tk.W, padx=(0, 10))
        self.extra_prompt_var = tk.StringVar()
        self.extra_prompt_entry = ttk.Entry(main_frame, textvariable=self.extra_prompt_var, width=50)
        self.extra_prompt_entry.grid(row=5, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # Generate button and status
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)
        
        self.generate_btn = ttk.Button(button_frame, text="Generate Short", command=self.generate_short)
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.status_label = ttk.Label(button_frame, text="Ready", foreground="green")
        self.status_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_btn = ttk.Button(button_frame, text="Clear Output", command=self.clear_output)
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.refresh_btn = ttk.Button(button_frame, text="Refresh Channels", command=self.refresh_channels)
        self.refresh_btn.pack(side=tk.LEFT)
        
        # Output Section
        ttk.Label(main_frame, text="Generated Script", font=("Arial", 12, "bold")).grid(
            row=7, column=0, columnspan=3, sticky=tk.W, pady=(20, 10)
        )
        
        # Movie title display
        self.title_frame = ttk.Frame(main_frame)
        self.title_frame.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        self.title_frame.columnconfigure(1, weight=1)
        
        ttk.Label(self.title_frame, text="Movie Title:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.movie_title_label = ttk.Label(self.title_frame, text="", font=("Arial", 10, "bold"), foreground="blue")
        self.movie_title_label.grid(row=0, column=1, sticky=tk.W)
        
        # Session ID display
        ttk.Label(self.title_frame, text="Session ID:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.session_id_label = ttk.Label(self.title_frame, text="", font=("Arial", 8), foreground="gray")
        self.session_id_label.grid(row=1, column=1, sticky=tk.W)
        
        # Script output
        self.output_text = scrolledtext.ScrolledText(main_frame, height=15, width=80, wrap=tk.WORD)
        self.output_text.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Configure grid weights for resizing
        main_frame.rowconfigure(9, weight=1)
    
    def on_channel_selected(self, event=None):
        """Handle channel selection change - no longer displays prompt."""
        pass
    
    def edit_channel_prompt(self):
        """Edit the base prompt for the selected channel with password protection."""
        channel_name = self.channel_var.get()
        if not channel_name:
            messagebox.showwarning("Selection Error", "Please select a channel to edit.")
            return
        
        # Check if we have a saved password
        if self.saved_password and self.saved_password == "admin":
            # Use saved password
            password = self.saved_password
        else:
            # Create custom password dialog with remember option
            password_dialog = tk.Toplevel(self.root)
            password_dialog.title("Password Required")
            password_dialog.geometry("400x180")
            password_dialog.transient(self.root)
            password_dialog.grab_set()
            
            # Center the dialog
            password_dialog.update_idletasks()
            x = (password_dialog.winfo_screenwidth() // 2) - 200
            y = (password_dialog.winfo_screenheight() // 2) - 90
            password_dialog.geometry(f"400x180+{x}+{y}")
            
            # Dialog content
            frame = ttk.Frame(password_dialog, padding="20")
            frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(frame, text="Enter password to edit prompt:").pack(anchor=tk.W, pady=(0, 10))
            
            password_var = tk.StringVar()
            password_entry = ttk.Entry(frame, textvariable=password_var, show='*', width=30)
            password_entry.pack(fill=tk.X, pady=(0, 10))
            password_entry.focus()
            
            remember_var = tk.BooleanVar()
            remember_check = ttk.Checkbutton(frame, text="Remember password for this session", variable=remember_var)
            remember_check.pack(anchor=tk.W, pady=(0, 10))
            
            result = {'password': None}
            
            def ok_clicked():
                result['password'] = password_var.get()
                if remember_var.get() and result['password'] == "admin":
                    self.saved_password = result['password']
                password_dialog.destroy()
            
            def cancel_clicked():
                password_dialog.destroy()
            
            button_frame = ttk.Frame(frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            ttk.Button(button_frame, text="OK", command=ok_clicked, width=10).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Cancel", command=cancel_clicked, width=10).pack(side=tk.LEFT)
            
            # Bind Enter key to OK
            password_entry.bind('<Return>', lambda e: ok_clicked())
            
            # Wait for dialog to close
            self.root.wait_window(password_dialog)
            
            password = result['password']
            
            if password is None:  # User cancelled
                return
        
        if password != "admin":  # Change this password as needed
            messagebox.showerror("Access Denied", "Incorrect password")
            return
        
        current_prompt = self.channel_manager.get_channel_prompt(channel_name)
        
        # Create a custom dialog for editing the prompt
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Prompt for '{channel_name}'")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (dialog.winfo_screenheight() // 2) - (400 // 2)
        dialog.geometry(f"600x400+{x}+{y}")
        
        # Create dialog content
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text=f"Edit base prompt for channel '{channel_name}':", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Text area for editing with proper formatting
        text_area = scrolledtext.ScrolledText(frame, height=15, width=70, wrap=tk.NONE, font=('Consolas', 10))
        text_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_area.insert(1.0, current_prompt)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)
        
        def save_changes():
            new_prompt = text_area.get(1.0, tk.END).strip()
            if not new_prompt:
                messagebox.showwarning("Input Error", "Prompt cannot be empty.", parent=dialog)
                return
            
            if self.channel_manager.update_channel_prompt(channel_name, new_prompt):
                messagebox.showinfo("Success", f"Prompt for '{channel_name}' updated successfully!", parent=dialog)
                dialog.destroy()
            else:
                messagebox.showerror("Error", f"Failed to update prompt for '{channel_name}'", parent=dialog)
        
        ttk.Button(button_frame, text="Save", command=save_changes).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
        
        # Focus on the text area
        text_area.focus()
    
    def refresh_channels(self):
        """Refresh the channel dropdown with current channels."""
        self.channel_manager.channels = self.channel_manager.load_channels()
        channels = self.channel_manager.get_channel_names()
        self.channel_combo['values'] = channels
        
        if channels and not self.channel_var.get():
            self.channel_var.set(channels[0])
    
    def add_channel(self):
        """Add a new channel with user-provided base prompt."""
        channel_name = self.new_channel_var.get().strip()
        if not channel_name:
            messagebox.showwarning("Input Error", "Please enter a channel name.")
            return
        
        if channel_name in self.channel_manager.channels:
            messagebox.showwarning("Duplicate Channel", f"Channel '{channel_name}' already exists.")
            return
        
        # Prompt for base prompt
        base_prompt = simpledialog.askstring(
            "Channel Base Prompt",
            f"Enter the base prompt for channel '{channel_name}':",
            parent=self.root
        )
        
        if base_prompt is None:  # User cancelled
            return
        
        if not base_prompt.strip():
            messagebox.showwarning("Input Error", "Base prompt cannot be empty.")
            return
        
        # Add channel
        self.channel_manager.add_channel(channel_name, base_prompt.strip())
        self.new_channel_var.set("")
        self.refresh_channels()
        self.channel_var.set(channel_name)  # Select the newly added channel
        
        messagebox.showinfo("Success", f"Channel '{channel_name}' added successfully!")
    
    def extract_titles_from_response(self, content: str) -> List[str]:
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
                    print(f"DEBUG: Found title: {title}")
        
        print(f"DEBUG: Total titles found in response: {len(titles_found)}")
        return titles_found
    
    def generate_short(self):
        """Generate a new short for the selected channel."""
        if self.is_generating:
            return
        
        channel_name = self.channel_var.get()
        if not channel_name:
            messagebox.showwarning("Selection Error", "Please select a channel.")
            return
        
        # Start generation in background thread
        self.is_generating = True
        self.set_generating_state(True)
        
        thread = threading.Thread(
            target=self._generate_short_thread,
            args=(channel_name, self.extra_prompt_var.get().strip()),
            daemon=True
        )
        thread.start()
    
    def _generate_short_thread(self, channel_name: str, extra_prompt: str):
        """Background thread for short generation."""
        try:
            base_prompt = self.channel_manager.get_channel_prompt(channel_name)
            
            # Generate script
            session_id = str(uuid.uuid4())
            
            # Get list of already used titles for this channel (fresh read each time)
            used_titles = self.channel_manager.get_used_titles(channel_name)
            print(f"DEBUG: Found {len(used_titles)} existing titles for {channel_name}")
            
            # Build full prompt with exclusion list
            full_prompt = base_prompt
            
            # Add exclusion instruction if there are used titles
            if used_titles:
                # Extract movie names from titles (everything before the year in parentheses)
                used_movies = set()
                for title in used_titles:
                    # Try to extract movie name
                    import re
                    match = re.search(r'^In (.+?) \(\d{4}\)', title)
                    if match:
                        used_movies.add(match.group(1))
                
                if used_movies:
                    exclusion_list = ", ".join(list(used_movies)[:10])  # Limit to 10 to avoid huge prompts
                    full_prompt = f"DO NOT use any of these movies: {exclusion_list}. Pick something completely different. {base_prompt}"
                else:
                    full_prompt = base_prompt
            
            if extra_prompt:
                full_prompt += " " + extra_prompt
            
            # Call Claude API
            result = self.claude_client.generate_script(full_prompt, session_id)
            
            if not result["success"]:
                self.root.after(0, self.handle_generation_error, result["error"])
                return
            
            # Extract ALL titles from the response
            content = result["content"]
            print(f"DEBUG: AI Response first 500 chars: {content[:500]}")
            titles = self.extract_titles_from_response(content)
            
            # Save ALL titles to channel's txt file
            if titles and channel_name:
                for title in titles:
                    self.channel_manager.add_title(channel_name, title)
                    print(f"DEBUG: Saved title '{title}' to titles_{channel_name.lower()}.txt")
            else:
                print(f"DEBUG: No titles extracted from response")
            
            # Save the full script content
            self.channel_manager.save_script(channel_name, content, session_id)
            
            # Success! Show the content
            self.root.after(0, self.handle_generation_success, content, session_id)
        
        except Exception as e:
            self.root.after(0, self.handle_generation_error, f"Unexpected error: {str(e)}")
    
    def handle_generation_success(self, content: str, session_id: str):
        """Handle successful script generation."""
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(1.0, content)
        
        self.movie_title_label.config(text="")
        self.session_id_label.config(text=session_id)
        
        self.set_generating_state(False)
        self.status_label.config(text="Generation completed successfully!", foreground="green")
    
    def handle_generation_error(self, error_message: str):
        """Handle generation errors."""
        self.set_generating_state(False)
        self.status_label.config(text="Generation failed", foreground="red")
        messagebox.showerror("Generation Error", error_message)
    
    def set_generating_state(self, generating: bool):
        """Update UI state during generation."""
        self.is_generating = generating
        
        # Disable/enable buttons
        state = "disabled" if generating else "normal"
        self.generate_btn.config(state=state)
        self.add_channel_btn.config(state=state)
        self.edit_prompt_btn.config(state=state)
        self.channel_combo.config(state="disabled" if generating else "readonly")
        self.new_channel_entry.config(state=state)
        self.extra_prompt_entry.config(state=state)
        
        # Update status
        if generating:
            self.status_label.config(text="Generating...", foreground="orange")
        else:
            self.status_label.config(text="Ready", foreground="green")
    
    def clear_output(self):
        """Clear all output displays."""
        self.output_text.delete(1.0, tk.END)
        self.movie_title_label.config(text="")
        self.session_id_label.config(text="")
        self.status_label.config(text="Output cleared", foreground="green")


def main():
    """Main application entry point."""
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()