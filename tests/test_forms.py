#!/usr/bin/env python3
"""
Test version to check if forms are working
"""
import streamlit as st

st.title("🧪 Form Test")

# Test registration form
with st.expander("Registration Form Test"):
    with st.form("test_register_form"):
        first_name = st.text_input("First Name:", key="test_first_name")
        email = st.text_input("Email:", key="test_email")
        password = st.text_input("Password:", type="password", key="test_password")
        confirm_password = st.text_input("Confirm Password:", type="password", key="test_confirm_password")
        register_button = st.form_submit_button("Test Register", type="primary")
        
        if register_button:
            st.write(f"First Name: {first_name}")
            st.write(f"Email: {email}")
            st.write(f"Password: {'*' * len(password)}")
            st.write(f"Confirm: {'*' * len(confirm_password)}")

# Test login form  
with st.expander("Login Form Test"):
    with st.form("test_login_form"):
        email = st.text_input("Email:", key="test_login_email")
        password = st.text_input("Password:", type="password", key="test_login_password")
        login_button = st.form_submit_button("Test Login", type="primary")
        
        if login_button:
            st.write(f"Email: {email}")
            st.write(f"Password: {'*' * len(password)}")

st.success("✅ If you see form fields above, forms are working!")