#!/usr/bin/env python3
"""
YouTube Shorts Script Generator - Desktop Application

This application provides a GUI for generating YouTube Shorts scripts using the Claude API.

INSTALLATION:
1. Install required dependencies:
   pip install requests

2. Set your Claude API key as an environment variable:
   Windows (Command Prompt): set ANTHROPIC_API_KEY=your_api_key_here
   Windows (PowerShell): $env:ANTHROPIC_API_KEY="your_api_key_here"
   Linux/Mac: export ANTHROPIC_API_KEY=your_api_key_here

3. Run the application:
   python youtube_shorts_generator.py

USAGE:
- Enter your prompt in the text field
- Click "Generate" to create a YouTube Shorts script
- The script and session ID will be displayed below
- Each request uses a fresh Claude API session to avoid token limits
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import os
import uuid
import threading
from typing import Optional, Dict, Any


class ClaudeClient:
    """Client for interacting with the Claude API"""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
    
    def validate_api_key(self) -> bool:
        """Check if API key is available"""
        return self.api_key is not None and len(self.api_key.strip()) > 0
    
    def generate_script(self, user_prompt: str, session_id: str) -> Dict[str, Any]:
        """
        Generate a YouTube Shorts script using Claude API
        
        Args:
            user_prompt: The user's input prompt
            session_id: Unique session identifier
            
        Returns:
            Dictionary containing the response or error information
        """
        if not self.validate_api_key():
            return {
                "error": "Claude API key not found. Please set the ANTHROPIC_API_KEY environment variable."
            }
        
        # Wrap the user prompt with ScrollCore-style instruction
        full_prompt = f"You are a ScrollCore-style YouTube Shorts script creator. {user_prompt}"
        
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt
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
                    "error": f"API Error {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Network error: {str(e)}"
            }
        except json.JSONDecodeError as e:
            return {
                "error": f"JSON decode error: {str(e)}"
            }
        except Exception as e:
            return {
                "error": f"Unexpected error: {str(e)}"
            }


class MainApp:
    """Main application GUI class"""
    
    def __init__(self, root):
        self.root = root
        self.claude_client = ClaudeClient()
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the user interface"""
        self.root.title("YouTube Shorts Script Generator")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Configure grid weights for responsive design
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="YouTube Shorts Script Generator", 
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # Input section
        input_frame = ttk.LabelFrame(main_frame, text="Input", padding="10")
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        input_frame.columnconfigure(0, weight=1)
        
        ttk.Label(input_frame, text="Enter your Short prompt:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.prompt_text = tk.Text(
            input_frame, 
            height=4, 
            wrap=tk.WORD,
            font=("Arial", 10)
        )
        self.prompt_text.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Button frame
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=2, column=0)
        
        self.generate_button = ttk.Button(
            button_frame,
            text="Generate Script",
            command=self.generate_script,
            style="Accent.TButton"
        )
        self.generate_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Progress bar (initially hidden)
        self.progress_bar = ttk.Progressbar(
            button_frame,
            mode='indeterminate',
            length=200
        )
        
        self.status_label = ttk.Label(button_frame, text="")
        self.status_label.pack(side=tk.LEFT)
        
        # Output section
        output_frame = ttk.LabelFrame(main_frame, text="Generated Script", padding="10")
        output_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)
        
        # Session ID display
        self.session_frame = ttk.Frame(output_frame)
        self.session_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.session_label = ttk.Label(self.session_frame, text="", font=("Arial", 9, "italic"))
        self.session_label.pack()
        
        # Script output
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Arial", 10)
        )
        self.output_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Check API key on startup
        self.check_api_key()
    
    def check_api_key(self):
        """Check if Claude API key is configured"""
        if not self.claude_client.validate_api_key():
            self.update_status("⚠️ Claude API key not found. Please set ANTHROPIC_API_KEY environment variable.", "error")
            self.generate_button.config(state=tk.DISABLED)
    
    def update_status(self, message: str, status_type: str = "info"):
        """Update the status label with a message"""
        colors = {
            "info": "#0066cc",
            "success": "#28a745",
            "error": "#dc3545",
            "warning": "#ffc107"
        }
        
        self.status_label.config(
            text=message,
            foreground=colors.get(status_type, colors["info"])
        )
    
    def show_progress(self, show: bool):
        """Show or hide the progress indicator"""
        if show:
            self.progress_bar.pack(side=tk.LEFT, padx=(10, 10))
            self.progress_bar.start(10)
            self.generate_button.config(state=tk.DISABLED)
            self.update_status("Generating script...", "info")
        else:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.generate_button.config(state=tk.NORMAL)
    
    def update_output(self, content: str, session_id: str = None):
        """Update the output text area with generated content"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, content)
        self.output_text.config(state=tk.DISABLED)
        
        if session_id:
            self.session_label.config(text=f"Session ID: {session_id}")
        else:
            self.session_label.config(text="")
    
    def generate_script(self):
        """Generate a YouTube Shorts script using Claude API"""
        prompt = self.prompt_text.get(1.0, tk.END).strip()
        
        if not prompt:
            messagebox.showwarning("Warning", "Please enter a prompt before generating.")
            return
        
        if not self.claude_client.validate_api_key():
            messagebox.showerror(
                "Error", 
                "Claude API key not found.\n\nPlease set the ANTHROPIC_API_KEY environment variable and restart the application."
            )
            return
        
        # Generate unique session ID for this request
        session_id = str(uuid.uuid4())
        
        # Start generation in a separate thread to keep UI responsive
        thread = threading.Thread(
            target=self._generate_script_thread,
            args=(prompt, session_id),
            daemon=True
        )
        thread.start()
    
    def _generate_script_thread(self, prompt: str, session_id: str):
        """Thread function for generating script (keeps UI responsive)"""
        self.root.after(0, lambda: self.show_progress(True))
        
        try:
            result = self.claude_client.generate_script(prompt, session_id)
            
            def update_ui():
                self.show_progress(False)
                
                if "error" in result:
                    self.update_status(f"❌ {result['error']}", "error")
                    messagebox.showerror("Error", result["error"])
                    self.update_output("Error occurred. Please check the status message above.")
                else:
                    self.update_status("✅ Script generated successfully!", "success")
                    self.update_output(result["content"], result["session_id"])
            
            self.root.after(0, update_ui)
            
        except Exception as e:
            def show_error():
                self.show_progress(False)
                error_msg = f"Unexpected error: {str(e)}"
                self.update_status(f"❌ {error_msg}", "error")
                messagebox.showerror("Error", error_msg)
            
            self.root.after(0, show_error)


def main():
    """Main application entry point"""
    root = tk.Tk()
    
    # Set application icon (optional)
    try:
        # You can add an icon file here if desired
        # root.iconbitmap("icon.ico")
        pass
    except:
        pass
    
    app = MainApp(root)
    
    # Center the window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    root.mainloop()


if __name__ == "__main__":
    main()