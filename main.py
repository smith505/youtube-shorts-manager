#!/usr/bin/env python3
"""
Main entry point for YouTube Shorts Manager
"""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def run_streamlit():
    """Run the Streamlit web application."""
    os.system('streamlit run streamlit_app.py')

def run_tkinter():
    """Run the Tkinter desktop application."""
    from src.apps.app import MainApp
    import tkinter as tk
    
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="YouTube Shorts Manager")
    parser.add_argument('--app', choices=['streamlit', 'tkinter'], default='streamlit',
                       help='Choose which app to run (default: streamlit)')
    
    args = parser.parse_args()
    
    if args.app == 'streamlit':
        run_streamlit()
    elif args.app == 'tkinter':
        run_tkinter()