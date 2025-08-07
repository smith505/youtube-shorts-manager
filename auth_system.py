"""
Advanced Authentication System with Email Approval
"""
import streamlit as st
import json
import os
import bcrypt
import smtplib
import email.mime.text
import email.mime.multipart
from datetime import datetime, timedelta
import uuid
import re

class UserManager:
    def __init__(self):
        self.users_file = "users.json"
        self.pending_file = "pending_users.json"
        self.admin_email = "corysmth14@gmail.com"
        self.load_users()
        
    def load_users(self):
        """Load approved and pending users from files."""
        # Load approved users
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r') as f:
                    self.users = json.load(f)
            else:
                self.users = {}
        except:
            self.users = {}
            
        # Load pending users
        try:
            if os.path.exists(self.pending_file):
                with open(self.pending_file, 'r') as f:
                    self.pending = json.load(f)
            else:
                self.pending = {}
        except:
            self.pending = {}
    
    def save_users(self):
        """Save approved users to file."""
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2, default=str)
    
    def save_pending(self):
        """Save pending users to file."""
        with open(self.pending_file, 'w') as f:
            json.dump(self.pending, f, indent=2, default=str)
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def register_user(self, first_name: str, email: str, password: str) -> dict:
        """Register a new user (pending approval)."""
        # Validation
        if not first_name.strip():
            return {"success": False, "error": "First name is required"}
        
        if not self.validate_email(email):
            return {"success": False, "error": "Invalid email format"}
        
        if len(password) < 6:
            return {"success": False, "error": "Password must be at least 6 characters"}
        
        # Check if user already exists (case-insensitive)
        for existing_email in self.users.keys():
            if existing_email.lower() == email.lower():
                return {"success": False, "error": "User already exists and is approved"}
        
        for existing_email in self.pending.keys():
            if existing_email.lower() == email.lower():
                return {"success": False, "error": "Registration already pending approval"}
        
        # Create pending user (preserve original email case)
        user_data = {
            "first_name": first_name.strip(),
            "email": email,  # Keep original case
            "password": self.hash_password(password),
            "requested_at": datetime.now(),
            "token": str(uuid.uuid4())
        }
        
        self.pending[email] = user_data  # Use original case as key
        self.save_pending()
        
        # Send approval email to admin
        self.send_approval_email(user_data)
        
        return {"success": True, "message": "Registration submitted! Waiting for admin approval."}
    
    def send_approval_email(self, user_data: dict):
        """Send approval email to admin."""
        try:
            # You'll need to set up your email credentials
            # For Gmail, you'll need an App Password
            sender_email = "your-email@gmail.com"  # Change this
            sender_password = "your-app-password"   # Change this
            
            msg = email.mime.multipart.MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = self.admin_email
            msg['Subject'] = f"New User Registration Request - {user_data['first_name']}"
            
            # Create approval and rejection URLs
            base_url = "http://localhost:8502"  # Change when deployed
            approve_url = f"{base_url}/?action=approve&token={user_data['token']}"
            reject_url = f"{base_url}/?action=reject&token={user_data['token']}"
            
            body = f"""
            New user registration request:
            
            Name: {user_data['first_name']}
            Email: {user_data['email']}
            Requested: {user_data['requested_at']}
            
            To approve this user, click here:
            {approve_url}
            
            To reject this user, click here:
            {reject_url}
            
            Or you can approve/reject manually in the admin panel.
            """
            
            msg.attach(email.mime.text.MIMEText(body, 'plain'))
            
            # Send email (commented out for now - you'll need to configure)
            # server = smtplib.SMTP('smtp.gmail.com', 587)
            # server.starttls()
            # server.login(sender_email, sender_password)
            # server.send_message(msg)
            # server.quit()
            
            # For now, just save to a file for testing
            with open("approval_emails.txt", "a") as f:
                f.write(f"\\n{'='*50}\\n")
                f.write(f"APPROVAL EMAIL SENT AT {datetime.now()}\\n")
                f.write(body)
                f.write("\\n")
            
        except Exception as e:
            st.error(f"Failed to send approval email: {str(e)}")
    
    def approve_user(self, token: str) -> bool:
        """Approve a pending user."""
        for email, user_data in self.pending.items():
            if user_data.get('token') == token:
                # Move from pending to approved (preserve email case)
                self.users[email] = {
                    "first_name": user_data['first_name'],
                    "email": user_data['email'],
                    "password": user_data['password'],
                    "approved_at": datetime.now(),
                    "status": "active",
                    "role": "default"  # New users get default role
                }
                del self.pending[email]
                self.save_users()
                self.save_pending()
                return True
        return False
    
    def reject_user(self, token: str) -> bool:
        """Reject a pending user."""
        for email, user_data in self.pending.items():
            if user_data.get('token') == token:
                del self.pending[email]
                self.save_pending()
                return True
        return False
    
    def login_user(self, email: str, password: str) -> dict:
        """Authenticate a user login."""
        # Find user with case-insensitive email search
        found_user = None
        found_email = None
        
        for user_email, user_data in self.users.items():
            if user_email.lower() == email.lower():
                found_user = user_data
                found_email = user_email
                break
        
        if not found_user:
            # Check if pending
            for pending_email in self.pending.keys():
                if pending_email.lower() == email.lower():
                    return {"success": False, "error": "Account pending approval"}
            return {"success": False, "error": "Invalid email or password"}
        
        # Check if user has password field (for backwards compatibility)
        if 'password' not in found_user:
            return {"success": False, "error": "Account needs password update. Please contact admin."}
            
        if not self.verify_password(password, found_user['password']):
            return {"success": False, "error": "Invalid email or password"}
        
        if found_user.get('status') != 'active':
            return {"success": False, "error": "Account is not active"}
        
        return {
            "success": True, 
            "user": {
                "first_name": found_user['first_name'],
                "email": found_user['email'],  # Return original case
                "role": found_user.get('role', 'default')  # Include role
            }
        }
    
    
    def delete_user(self, email: str) -> dict:
        """Delete a user account from both approved and pending lists (admin only)."""
        original_email = email
        email_lower = email.lower()
        deleted_from = []
        user_name = email
        actual_email_found = None
        
        # Check and remove from approved users (case-insensitive search)
        for user_email in list(self.users.keys()):
            if user_email.lower() == email_lower:
                user_name = self.users[user_email]['first_name']
                actual_email_found = user_email
                del self.users[user_email]
                self.save_users()
                deleted_from.append("approved users")
                break
        
        # Check and remove from pending users (case-insensitive search)  
        for user_email in list(self.pending.keys()):
            if user_email.lower() == email_lower:
                if user_name == email or user_name == email_lower:  # If we didn't get name from approved users
                    user_name = self.pending[user_email]['first_name']
                if not actual_email_found:
                    actual_email_found = user_email
                del self.pending[user_email]
                self.save_pending()
                deleted_from.append("pending users")
                break
        
        if not deleted_from:
            # Show debug info
            approved_emails = list(self.users.keys())
            pending_emails = list(self.pending.keys())
            return {
                "success": False, 
                "error": f"User '{original_email}' not found. Available emails - Approved: {approved_emails}, Pending: {pending_emails}"
            }
        
        return {"success": True, "message": f"User {user_name} ({actual_email_found}) deleted from {' and '.join(deleted_from)}"}
    
    def change_user_role(self, email: str, new_role: str) -> dict:
        """Change a user's role (admin only)."""
        if new_role not in ['default', 'admin']:
            return {"success": False, "error": "Invalid role. Must be 'default' or 'admin'"}
        
        # Find user with case-insensitive search
        for user_email in list(self.users.keys()):
            if user_email.lower() == email.lower():
                user_name = self.users[user_email]['first_name']
                # Update the user's role
                self.users[user_email]['role'] = new_role
                self.save_users()
                return {"success": True, "message": f"Role changed to {new_role} for {user_name} ({user_email})"}
        
        return {"success": False, "error": f"User {email} not found"}
    
    def reset_user_password(self, email: str, new_password: str) -> dict:
        """Reset a user's password (admin only)."""
        if len(new_password) < 6:
            return {"success": False, "error": "Password must be at least 6 characters"}
        
        # Find user with case-insensitive search
        for user_email in list(self.users.keys()):
            if user_email.lower() == email.lower():
                user_name = self.users[user_email]['first_name']
                # Update the user's password
                self.users[user_email]['password'] = self.hash_password(new_password)
                self.save_users()
                return {"success": True, "message": f"Password reset for {user_name} ({user_email})"}
        
        return {"success": False, "error": f"User {email} not found"}
    
    def get_all_users(self) -> list:
        """Get list of all approved users for admin management."""
        return [
            {
                "first_name": data['first_name'],
                "email": email,
                "approved_at": data.get('approved_at', 'Unknown'),
                "status": data.get('status', 'active'),
                "role": data.get('role', 'default')
            }
            for email, data in self.users.items()
        ]
    
    def get_pending_users(self) -> list:
        """Get list of pending users for admin approval."""
        return [
            {
                "first_name": data['first_name'],
                "email": email,
                "requested_at": data['requested_at'],
                "token": data['token']
            }
            for email, data in self.pending.items()
        ]


def show_login_page():
    """Show login and registration interface."""
    
    # Clear any old authentication state (but keep saved credentials)
    keys_to_clear = ['authenticated', 'user', 'drive_manager', 'claude_client', 'channel_manager']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # Initialize user manager
    if 'user_manager' not in st.session_state:
        st.session_state.user_manager = UserManager()
    
    # Handle URL parameters for approval/rejection
    query_params = st.query_params
    if 'action' in query_params and 'token' in query_params:
        action = query_params['action']
        token = query_params['token']
        
        if action == 'approve':
            if st.session_state.user_manager.approve_user(token):
                st.success("✅ User approved successfully!")
            else:
                st.error("❌ Invalid approval token")
        elif action == 'reject':
            if st.session_state.user_manager.reject_user(token):
                st.success("✅ User rejected successfully!")
            else:
                st.error("❌ Invalid rejection token")
        
        # Clear URL parameters
        st.query_params.clear()
    
    st.title("🎬 YouTube Shorts Manager")
    
    # Debug button to clear cache
    if st.button("🔄 Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    
    # Create tabs for Login and Registration
    login_tab, register_tab, admin_tab = st.tabs(["🔑 Login", "📝 Create Account", "⚙️ Admin"])
    
    with login_tab:
        st.subheader("Login to Your Account")
        
        # Load saved credentials from file
        def load_saved_credentials():
            try:
                if os.path.exists('.remember_me.json'):
                    with open('.remember_me.json', 'r') as f:
                        return json.load(f)
                return {"email": "", "password": "", "remember": False}
            except:
                return {"email": "", "password": "", "remember": False}
        
        def save_credentials(email, password, remember):
            try:
                data = {"email": email if remember else "", "password": password if remember else "", "remember": remember}
                with open('.remember_me.json', 'w') as f:
                    json.dump(data, f)
            except:
                pass
        
        # Load saved credentials
        saved_creds = load_saved_credentials()
        saved_email = saved_creds.get("email", "")
        saved_password = saved_creds.get("password", "")
        saved_remember = saved_creds.get("remember", False)
        
        with st.form("login_form"):
            email = st.text_input("Email:", value=saved_email, key="login_email")
            password = st.text_input("Password:", type="password", value=saved_password, key="login_password")
            remember_me = st.checkbox("Remember me", value=saved_remember, key="remember_me")
            login_button = st.form_submit_button("🔑 Login", type="primary")
            
            if login_button:
                if email and password:
                    result = st.session_state.user_manager.login_user(email, password)
                    if result["success"]:
                        # Save credentials to file if remember me is checked
                        save_credentials(email, password, remember_me)
                        
                        st.session_state.authenticated = True
                        st.session_state.user = result["user"]
                        st.success(f"Welcome back, {result['user']['first_name']}!")
                        st.rerun()
                    else:
                        st.error(result["error"])
                else:
                    st.error("Please enter both email and password")
        
        # Forgot Password button
        if st.button("🔒 Forgot Password?"):
            st.session_state.show_forgot_password = True
            st.rerun()
        
        # Show forgot password form
        if st.session_state.get('show_forgot_password', False):
            st.markdown("---")
            st.subheader("🔒 Forgot Password")
            st.info("Please contact the administrator to reset your password.")
            st.write("**Admin Email:** corysmth14@gmail.com")
            st.write("**Instructions:** Send an email with your account email address and request a password reset.")
            
            if st.button("❌ Cancel"):
                st.session_state.show_forgot_password = False
                st.rerun()
    
    with register_tab:
        st.subheader("Create New Account")
        st.info("New accounts require admin approval before you can login.")
        
        with st.form("register_form"):
            first_name = st.text_input("First Name:", key="reg_first_name")
            email = st.text_input("Email:", key="reg_email")
            password = st.text_input("Password:", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password:", type="password", key="reg_confirm_password")
            register_button = st.form_submit_button("📝 Create Account", type="primary")
            
            if register_button:
                if not all([first_name, email, password, confirm_password]):
                    st.error("Please fill in all fields")
                elif password != confirm_password:
                    st.error("Passwords don't match")
                else:
                    result = st.session_state.user_manager.register_user(first_name, email, password)
                    if result["success"]:
                        st.success(result["message"])
                        st.info("You'll receive an email once your account is approved.")
                    else:
                        st.error(result["error"])
    
    with admin_tab:
        st.subheader("Admin Panel")
        admin_password = st.text_input("Admin Password:", type="password", key="admin_password")
        
        if admin_password == "admin123":  # Change this password
            st.success("✅ Admin access granted")
            
            # Create tabs for different admin functions  
            approval_tab, users_tab, reset_tab, debug_tab = st.tabs(["👥 Pending Approvals", "👤 All Users", "🔑 Reset Password", "🔧 Debug & Manage"])
            
            with approval_tab:
                # Show pending users
                pending_users = st.session_state.user_manager.get_pending_users()
                
                if pending_users:
                    st.subheader("👥 Pending User Approvals")
                    
                    for user in pending_users:
                        with st.expander(f"{user['first_name']} ({user['email']})"):
                            st.write(f"**Name:** {user['first_name']}")
                            st.write(f"**Email:** {user['email']}")
                            st.write(f"**Requested:** {user['requested_at']}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"✅ Approve", key=f"approve_{user['token']}"):
                                    if st.session_state.user_manager.approve_user(user['token']):
                                        st.success("User approved!")
                                        st.rerun()
                            
                            with col2:
                                if st.button(f"❌ Reject", key=f"reject_{user['token']}"):
                                    if st.session_state.user_manager.reject_user(user['token']):
                                        st.success("User rejected!")
                                        st.rerun()
                else:
                    st.info("No pending user approvals")
            
            with users_tab:
                # Show all approved users
                all_users = st.session_state.user_manager.get_all_users()
                
                if all_users:
                    st.subheader("👤 All Approved Users")
                    
                    for user in all_users:
                        with st.expander(f"{user['first_name']} ({user['email']}) - {user['role'].upper()}"):
                            st.write(f"**Name:** {user['first_name']}")
                            st.write(f"**Email:** {user['email']}")
                            st.write(f"**Approved:** {user['approved_at']}")
                            st.write(f"**Status:** {user['status']}")
                            st.write(f"**Role:** {user['role']}")
                            
                            # Role change section
                            st.markdown("---")
                            st.write("**Change Role:**")
                            col1, col2 = st.columns(2)
                            with col1:
                                new_role = st.selectbox(
                                    "New role",
                                    ["default", "admin"],
                                    index=0 if user['role'] == 'default' else 1,
                                    key=f"role_{user['email']}"
                                )
                            with col2:
                                if st.button("Update Role", key=f"update_role_{user['email']}"):
                                    result = st.session_state.user_manager.change_user_role(user['email'], new_role)
                                    if result["success"]:
                                        st.success(f"✅ {result['message']}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {result['error']}")
                            
                            # Delete user button
                            st.markdown("---")
                            col1, col2 = st.columns([3, 1])
                            with col2:
                                if st.button("🗑️ Delete User", key=f"delete_{user['email']}", type="secondary"):
                                    st.session_state[f"confirm_delete_{user['email']}"] = True
                                    st.rerun()
                            
                            # Confirmation dialog
                            if st.session_state.get(f"confirm_delete_{user['email']}", False):
                                st.error(f"⚠️ **Confirm deletion of {user['first_name']} ({user['email']})?**")
                                col1, col2, col3 = st.columns([1, 1, 2])
                                with col1:
                                    if st.button("✅ Yes, Delete", key=f"confirm_yes_{user['email']}", type="primary"):
                                        result = st.session_state.user_manager.delete_user(user['email'])
                                        if result["success"]:
                                            st.success(f"✅ {result['message']}")
                                            # Clear confirmation state
                                            if f"confirm_delete_{user['email']}" in st.session_state:
                                                del st.session_state[f"confirm_delete_{user['email']}"]
                                            st.rerun()
                                        else:
                                            st.error(f"❌ {result['error']}")
                                with col2:
                                    if st.button("❌ Cancel", key=f"confirm_no_{user['email']}"):
                                        # Clear confirmation state
                                        if f"confirm_delete_{user['email']}" in st.session_state:
                                            del st.session_state[f"confirm_delete_{user['email']}"]
                                        st.rerun()
                else:
                    st.info("No approved users found")
            
            with reset_tab:
                # Password reset functionality
                st.subheader("🔑 Reset User Password")
                
                all_users = st.session_state.user_manager.get_all_users()
                if all_users:
                    # Select user to reset
                    user_emails = [user['email'] for user in all_users]
                    user_options = [f"{user['first_name']} ({user['email']})" for user in all_users]
                    
                    selected_index = st.selectbox(
                        "Select user to reset password:",
                        range(len(user_options)),
                        format_func=lambda x: user_options[x],
                        key="reset_user_select"
                    )
                    
                    selected_email = user_emails[selected_index]
                    
                    with st.form("reset_password_form"):
                        new_password = st.text_input("New Password (min 6 characters):", type="password", key="new_password")
                        confirm_password = st.text_input("Confirm New Password:", type="password", key="confirm_new_password")
                        reset_button = st.form_submit_button("🔑 Reset Password", type="primary")
                        
                        if reset_button:
                            if not new_password:
                                st.error("Please enter a new password")
                            elif len(new_password) < 6:
                                st.error("Password must be at least 6 characters")
                            elif new_password != confirm_password:
                                st.error("Passwords don't match")
                            else:
                                result = st.session_state.user_manager.reset_user_password(selected_email, new_password)
                                if result["success"]:
                                    st.success(f"✅ {result['message']}")
                                    st.info(f"New password for {selected_email}: **{new_password}**")
                                else:
                                    st.error(f"❌ {result['error']}")
                else:
                    st.info("No users available for password reset")
            
            with debug_tab:
                st.subheader("🔧 Debug & User Management")
                
                # Show raw user data
                st.write("**📊 System Status:**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Approved Users", len(st.session_state.user_manager.users))
                with col2:
                    st.metric("Pending Users", len(st.session_state.user_manager.pending))
                
                # Show all users (approved and pending)
                st.write("**📝 All Users in System:**")
                
                # Approved users
                if st.session_state.user_manager.users:
                    st.write("**✅ Approved Users:**")
                    for email, data in st.session_state.user_manager.users.items():
                        st.write(f"- {data['first_name']} ({email}) - Status: {data.get('status', 'active')}")
                
                # Pending users
                if st.session_state.user_manager.pending:
                    st.write("**⏳ Pending Users:**")
                    for email, data in st.session_state.user_manager.pending.items():
                        st.write(f"- {data['first_name']} ({email}) - Requested: {data['requested_at']}")
                
                if not st.session_state.user_manager.users and not st.session_state.user_manager.pending:
                    st.info("No users found in system")
                
                # Manual user deletion by email
                st.markdown("---")
                st.subheader("🗑️ Delete User by Email")
                delete_email = st.text_input("Enter email to delete:", key="manual_delete_email")
                if st.button("🗑️ Delete User", key="manual_delete_btn"):
                    if delete_email:
                        result = st.session_state.user_manager.delete_user(delete_email)
                        if result["success"]:
                            st.success(f"✅ {result['message']}")
                            st.rerun()
                        else:
                            st.error(f"❌ {result['error']}")
                    else:
                        st.error("Please enter an email address")
            
            st.markdown("---")
            st.success("💡 **Password System Active!** Users need email approval and password to login.")
            
        elif admin_password:
            st.error("❌ Invalid admin password")


def check_authentication():
    """Check if user is authenticated."""
    return st.session_state.get('authenticated', False)


def get_current_user():
    """Get current logged-in user."""
    return st.session_state.get('user', None)