"""
Authentication & User Management Module
JWT-based authentication with user registration and admin roles
"""

import jwt
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Tuple, Optional
import hashlib
import secrets

# Configuration
JWT_SECRET = "your-super-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

USERS_DB = "users.json"
SUBSCRIPTION_DB = "subscriptions.json"

# Subscription plans
SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "features": ["limited_recommendations", "basic_mood_detection", "7_day_history"],
        "video_limit": 10
    },
    "premium": {
        "name": "Premium",
        "price": 99,  # ₹99/month
        "features": ["unlimited_recommendations", "advanced_mood_detection", "30_day_history", "priority_support"],
        "video_limit": 999
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 499,  # ₹499/month
        "features": ["unlimited_everything", "api_access", "custom_integration", "dedicated_support", "analytics"],
        "video_limit": 9999
    }
}

# Admin accounts (predefined)
ADMIN_CREDENTIALS = {
    "admin": {
        "email": "admin@moviepulse.com",
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "name": "Admin User"
    },
    "manager": {
        "email": "manager@moviepulse.com",
        "password_hash": hashlib.sha256("manager123".encode()).hexdigest(),
        "role": "manager",
        "name": "Manager User"
    }
}

def init_users_db():
    """Initialize users database with default admin accounts"""
    if os.path.exists(USERS_DB):
        return
    
    users = {}
    for username, admin_data in ADMIN_CREDENTIALS.items():
        users[username] = {
            "username": username,
            "email": admin_data["email"],
            "password_hash": admin_data["password_hash"],
            "role": admin_data["role"],
            "name": admin_data["name"],
            "subscription": "enterprise",
            "created_at": datetime.now().isoformat(),
            "verified": True,
            "last_login": None
        }
    
    with open(USERS_DB, 'w') as f:
        json.dump(users, f, indent=2)
    
    print(f"✅ Users database initialized with admin accounts")

def init_subscription_db():
    """Initialize subscription database"""
    if os.path.exists(SUBSCRIPTION_DB):
        return
    
    with open(SUBSCRIPTION_DB, 'w') as f:
        json.dump({}, f, indent=2)

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users() -> Dict:
    """Load all users from database"""
    if not os.path.exists(USERS_DB):
        init_users_db()
    
    with open(USERS_DB, 'r') as f:
        return json.load(f)

def save_users(users: Dict):
    """Save users to database"""
    with open(USERS_DB, 'w') as f:
        json.dump(users, f, indent=2)

def load_subscriptions() -> Dict:
    """Load subscription data"""
    if not os.path.exists(SUBSCRIPTION_DB):
        init_subscription_db()
    
    with open(SUBSCRIPTION_DB, 'r') as f:
        return json.load(f)

def save_subscriptions(subscriptions: Dict):
    """Save subscription data"""
    with open(SUBSCRIPTION_DB, 'w') as f:
        json.dump(subscriptions, f, indent=2)

def register_user(username: str, email: str, password: str, name: str) -> Tuple[bool, str]:
    """Register a new user"""
    users = load_users()
    
    # Check if user exists
    if username in users:
        return False, "Username already exists"
    
    # Check email
    for user in users.values():
        if user.get("email") == email:
            return False, "Email already registered"
    
    # Create new user
    users[username] = {
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "role": "user",
        "name": name,
        "subscription": "free",
        "created_at": datetime.now().isoformat(),
        "verified": False,
        "last_login": None,
        "preferences": {}
    }
    
    save_users(users)
    return True, "User registered successfully"

def login_user(username: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
    """Authenticate user and return JWT token"""
    users = load_users()
    
    if username not in users:
        return False, "Invalid username or password", None
    
    user = users[username]
    password_hash = hash_password(password)
    
    if user["password_hash"] != password_hash:
        return False, "Invalid username or password", None
    
    # Update last login
    user["last_login"] = datetime.now().isoformat()
    save_users(users)
    
    # Create JWT token
    payload = {
        "username": username,
        "role": user["role"],
        "email": user["email"],
        "subscription": user["subscription"],
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS)
    }
    
    try:
        import sys
        print(f"\n[AUTH_LOGIN] DEBUG 1: jwt module = {jwt}", file=sys.stderr, flush=True)
        print(f"[AUTH_LOGIN] DEBUG 2: jwt type = {type(jwt)}", file=sys.stderr, flush=True)
        print(f"[AUTH_LOGIN] DEBUG 3: hasattr encode = {hasattr(jwt, 'encode')}", file=sys.stderr, flush=True)
        print(f"[AUTH_LOGIN] DEBUG 4: About to call jwt.encode", file=sys.stderr, flush=True)
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        print(f"[AUTH_LOGIN] DEBUG 5: jwt.encode succeeded, token = {token[:50]}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[ERROR] jwt.encode failed: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise
    
    user_data = {
        "username": username,
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "subscription": user["subscription"]
    }
    
    return True, "Login successful", {"token": token, "user": user_data}

def verify_token(token: str) -> Tuple[bool, Optional[Dict]]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return True, payload
    except jwt.ExpiredSignatureError:
        return False, None
    except jwt.InvalidTokenError:
        return False, None

def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user data by username"""
    users = load_users()
    return users.get(username)

def upgrade_subscription(username: str, plan: str) -> Tuple[bool, str]:
    """Upgrade user subscription"""
    users = load_users()
    
    if username not in users:
        return False, "User not found"
    
    if plan not in SUBSCRIPTION_PLANS:
        return False, "Invalid subscription plan"
    
    users[username]["subscription"] = plan
    save_users(users)
    
    # Log subscription change
    subscriptions = load_subscriptions()
    subscriptions[username] = {
        "plan": plan,
        "upgraded_at": datetime.now().isoformat(),
        "amount": SUBSCRIPTION_PLANS[plan]["price"],
        "status": "active"
    }
    save_subscriptions(subscriptions)
    
    return True, f"Upgraded to {SUBSCRIPTION_PLANS[plan]['name']} plan"

def get_user_stats() -> Dict:
    """Get overall user statistics"""
    users = load_users()
    subscriptions = load_subscriptions()
    
    total_users = len(users)
    admin_users = len([u for u in users.values() if u.get("role") in ["admin", "manager"]])
    premium_users = len([u for u in users.values() if u.get("subscription") == "premium"])
    enterprise_users = len([u for u in users.values() if u.get("subscription") == "enterprise"])
    
    monthly_revenue = 0
    for username, sub in subscriptions.items():
        if sub.get("status") == "active":
            monthly_revenue += sub.get("amount", 0)
    
    return {
        "total_users": total_users,
        "admin_users": admin_users,
        "premium_users": premium_users,
        "enterprise_users": enterprise_users,
        "free_users": total_users - admin_users - premium_users - enterprise_users,
        "monthly_revenue": monthly_revenue,
        "subscription_plans": SUBSCRIPTION_PLANS,
        "timestamp": datetime.now().isoformat()
    }

def get_all_users_admin() -> list:
    """Get all users for admin dashboard"""
    users = load_users()
    users_list = []
    
    for username, user in users.items():
        users_list.append({
            "username": username,
            "email": user.get("email"),
            "name": user.get("name"),
            "role": user.get("role"),
            "subscription": user.get("subscription"),
            "created_at": user.get("created_at"),
            "last_login": user.get("last_login"),
            "verified": user.get("verified")
        })
    
    return users_list

def delete_user(username: str) -> Tuple[bool, str]:
    """Delete a user (admin only)"""
    users = load_users()
    
    if username not in users:
        return False, "User not found"
    
    # Prevent deleting admin accounts
    if users[username].get("role") in ["admin", "manager"]:
        return False, "Cannot delete admin users"
    
    del users[username]
    save_users(users)
    
    return True, "User deleted successfully"

# Initialize databases on import
init_users_db()
init_subscription_db()
