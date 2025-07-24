from fastapi import APIRouter, HTTPException, status
from ..dependencies import auth_manager

router = APIRouter(tags=["Authentication"])

@router.post("/login")
async def login(credentials: dict):
    """
    Login endpoint that accepts username and password
    
    Expected payload:
    {
        "username": "test",
        "password": "password"
    }
    """
    username = credentials.get("username")
    password = credentials.get("password")
    
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required"
        )
    
    if username == "test" and password == "password":
        token = auth_manager.create_access_token({"sub": username})
        return {
            "access_token": token, 
            "username": username,
            "token_type": "bearer",
            "message": "Login successful"
        }
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password"
    ) 