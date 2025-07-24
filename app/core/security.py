from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
import secrets

class AuthManager:
    """Manages authentication and JWT tokens with enhanced security"""
    
    def __init__(self):
        # Use environment variable for secret key in production, fallback to generated one
        self.secret_key = os.getenv("JWT_SECRET_KEY", self._generate_secret_key())
        self.algorithm = "HS256"
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Fixed credentials for this test assignment
        self.valid_users = {
            "test": {
                "username": "test",
                "password_hash": self.get_password_hash("password"),
                "is_active": True
            }
        }
    
    def _generate_secret_key(self) -> str:
        """Generate a secure random secret key"""
        return secrets.token_urlsafe(32)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> bool:
        """Verify if a JWT token is valid"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            token_type: str = payload.get("type")
            
            if username is None or token_type != "access":
                return False
            
            # Check if user exists and is active
            user = self.valid_users.get(username)
            if not user or not user.get("is_active", False):
                return False
            
            return True
        except JWTError:
            return False
        except Exception:
            return False
    
    def get_token_data(self, token: str) -> Optional[Dict[str, Any]]:
        """Get data from a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user with username and password"""
        user = self.valid_users.get(username)
        if not user:
            return None
        
        if not self.verify_password(password, user["password_hash"]):
            return None
        
        if not user.get("is_active", False):
            return None
        
        return {
            "username": user["username"],
            "is_active": user["is_active"]
        }
    
    def get_user_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user information from a valid token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            
            if username is None:
                return None
            
            user = self.valid_users.get(username)
            if not user or not user.get("is_active", False):
                return None
            
            return {
                "username": user["username"],
                "is_active": user["is_active"]
            }
        except JWTError:
            return None
    
    def is_token_expired(self, token: str) -> bool:
        """Check if a token is expired"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            exp = payload.get("exp")
            if exp is None:
                return True
            
            return datetime.utcnow() > datetime.fromtimestamp(exp)
        except JWTError:
            return True
    
    def refresh_token(self, token: str) -> Optional[str]:
        """Refresh an access token if it's valid but close to expiry"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username = payload.get("sub")
            
            if username and self.valid_users.get(username):
                return self.create_access_token({"sub": username})
            
            return None
        except JWTError:
            return None 