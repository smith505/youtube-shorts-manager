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
    
    def register_user(self, first_name: str, email: str) -> dict:
        """Register a new user (pending approval) - no password required."""
        # Validation
        if not first_name.strip():
            return {"success": False, "error": "First name is required"}
        
        if not self.validate_email(email):
            return {"success": False, "error": "Invalid email format"}
        
        # Check if user already exists
        if email in self.users:
            return {"success": False, "error": "User already exists and is approved"}
        
        if email in self.pending:
            return {"success": False, "error": "Registration already pending approval"}
        
        # Create pending user
        user_data = {
            "first_name": first_name.strip(),
            "email": email.lower(),
            "requested_at": datetime.now(),
            "token": str(uuid.uuid4())
        }
        
        self.pending[email] = user_data
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
                # Move from pending to approved
                self.users[email] = {
                    "first_name": user_data['first_name'],
                    "email": user_data['email'],
                    "approved_at": datetime.now(),
                    "status": "active"
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
    
    def login_user(self, email: str) -> dict:
        """Authenticate a user login with email only."""
        email = email.lower()
        
        if email not in self.users:
            if email in self.pending:
                return {"success": False, "error": "Account pending approval"}
            return {"success": False, "error": "Email not found or not approved"}
        
        user = self.users[email]
        if user.get('status') != 'active':
            return {"success": False, "error": "Account is not active"}
        
        return {
            "success": True, 
            "user": {
                "first_name": user['first_name'],
                "email": user['email']
            }
        }
    
    
    def get_all_users(self) -> list:
        """Get list of all approved users for admin management."""
        return [
            {
                "first_name": data['first_name'],
                "email": email,
                "approved_at": data.get('approved_at', 'Unknown'),
                "status": data.get('status', 'active')
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
    st.markdown("---")
    
    # Create tabs for Login and Registration
    login_tab, register_tab, admin_tab = st.tabs(["🔑 Login", "📝 Create Account", "⚙️ Admin"])
    
    with login_tab:
        st.subheader("Login to Your Account")
        
        with st.form("login_form"):
            email = st.text_input("Email:", key="login_email", help="Enter your approved email address")
            login_button = st.form_submit_button("🔑 Login with Email", type="primary")
            
            if login_button:
                if email:
                    result = st.session_state.user_manager.login_user(email)
                    if result["success"]:
                        st.session_state.authenticated = True
                        st.session_state.user = result["user"]
                        st.success(f"Welcome back, {result['user']['first_name']}!")
                        st.rerun()
                    else:
                        st.error(result["error"])
                else:
                    st.error("Please enter your email address")
        
        st.info("💡 **No password needed!** Just enter your approved email address to login.")
    
    with register_tab:
        st.subheader("Create New Account")
        st.info("New accounts require admin approval before you can login.")
        
        with st.form("register_form"):
            first_name = st.text_input("First Name:", key="reg_first_name")
            email = st.text_input("Email:", key="reg_email")
            register_button = st.form_submit_button("📝 Create Account", type="primary")
            
            if register_button:
                if not all([first_name, email]):
                    st.error("Please fill in all fields")
                else:
                    result = st.session_state.user_manager.register_user(first_name, email)
                    if result["success"]:
                        st.success(result["message"])
                        st.info("Once approved, you can login with just your email address - no password needed!")
                    else:
                        st.error(result["error"])
    
    with admin_tab:
        st.subheader("Admin Panel")
        admin_password = st.text_input("Admin Password:", type="password", key="admin_password")
        
        if admin_password == "admin123":  # Change this password
            st.success("✅ Admin access granted")
            
            # Create tabs for different admin functions  
            approval_tab, users_tab = st.tabs(["👥 Pending Approvals", "👤 All Users"])
            
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
                        with st.expander(f"{user['first_name']} ({user['email']})"):
                            st.write(f"**Name:** {user['first_name']}")
                            st.write(f"**Email:** {user['email']}")
                            st.write(f"**Approved:** {user['approved_at']}")
                            st.write(f"**Status:** {user['status']}")
                else:
                    st.info("No approved users found")
            
            
            st.markdown("---")
            st.success("💡 **Passwordless System Active!** Users only need email approval to login.")
            
        elif admin_password:
            st.error("❌ Invalid admin password")


def check_authentication():
    """Check if user is authenticated."""
    return st.session_state.get('authenticated', False)


def get_current_user():
    """Get current logged-in user."""
    return st.session_state.get('user', None)