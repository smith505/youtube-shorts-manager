#!/usr/bin/env python3
"""
Minimal test version to identify startup issues
"""
import streamlit as st

st.set_page_config(
    page_title="YouTube Shorts Manager Test",
    page_icon="🎬",
    layout="wide"
)

def main():
    st.title("🎬 YouTube Shorts Manager - Test Version")
    st.success("✅ Basic Streamlit is working!")
    
    # Test imports one by one
    try:
        import os
        st.success("✅ os import works")
    except Exception as e:
        st.error(f"❌ os import failed: {e}")
    
    try:
        import json
        st.success("✅ json import works")
    except Exception as e:
        st.error(f"❌ json import failed: {e}")
    
    try:
        import requests
        st.success("✅ requests import works")
    except Exception as e:
        st.error(f"❌ requests import failed: {e}")
    
    try:
        from google.oauth2.credentials import Credentials
        st.success("✅ Google auth import works")
    except Exception as e:
        st.error(f"❌ Google auth import failed: {e}")
    
    try:
        import bcrypt
        st.success("✅ bcrypt import works")
    except Exception as e:
        st.error(f"❌ bcrypt import failed: {e}")
    
    # Test secrets access
    try:
        if 'ANTHROPIC_API_KEY' in st.secrets:
            st.success("✅ ANTHROPIC_API_KEY found in secrets")
        else:
            st.warning("⚠️ ANTHROPIC_API_KEY not found in secrets")
    except Exception as e:
        st.error(f"❌ Secrets access failed: {e}")
    
    try:
        if 'GOOGLE_CREDENTIALS' in st.secrets:
            st.success("✅ GOOGLE_CREDENTIALS found in secrets")
        else:
            st.warning("⚠️ GOOGLE_CREDENTIALS not found in secrets")
    except Exception as e:
        st.error(f"❌ Google credentials access failed: {e}")

if __name__ == "__main__":
    main()