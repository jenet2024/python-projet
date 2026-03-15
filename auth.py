from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from fastapi import FastAPI
from passlib.context import CryptContext


# ========== CONFIGURATION ==========
SECRET_KEY = "YOUR-SECRET-KEY-256-BITS"  # Générer avec: secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Contexte de hachage de mots de passe (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme pour extraire le token du header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ========== MODÈLES PYDANTIC ==========
class User(BaseModel):
    id: int
    username: str
    email: str
    role: str = Field(default="user", description="Rôle : user, admin, moderator")
    disabled: bool = False

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None

# ========== BASE DE DONNÉES SIMULÉE ==========
# En production : remplacer par vraie DB (PostgreSQL via SQLAlchemy)
fake_users_db = {
    "alice": {
        "id": 1,
        "username": "alice",
        "email": "alice@example.com",
        "role": "admin",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "disabled": False,
    },
    "bob": {
        "id": 2,
        "username": "bob",
        "email": "bob@example.com",
        "role": "user",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "disabled": False,
    }
}

# ========== FONCTIONS UTILITAIRES ==========
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie si le mot de passe correspond au hash"""
    return pwd_context.verify(plain_password[:72], hashed_password)

def get_password_hash(password: str) -> str:
    """Hash un mot de passe avec bcrypt"""
    print(pwd_context.hash(password[:72]))
    return pwd_context.hash(password[:72])

def get_user(username: str) -> Optional[UserInDB]:
    """Récupère un utilisateur depuis la DB"""
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authentifie un utilisateur (username + password)"""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crée un access token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crée un refresh token JWT (durée plus longue)"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Dépendance FastAPI : Récupère l'utilisateur actuel depuis le token JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        role: str = payload.get("role")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "access":
            raise credentials_exception
        
        token_data = TokenData(user_id=user_id, username=username, role=role)
    except JWTError:
        raise credentials_exception
    
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Dépendance : Vérifie que l'utilisateur n'est pas désactivé"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(required_role: str):
    """Dépendance : Vérifie que l'utilisateur a le rôle requis"""
    async def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role != required_role and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return current_user
    return role_checker

