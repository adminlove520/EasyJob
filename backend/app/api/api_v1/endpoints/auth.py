from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserUpdate, UserResponse, LoginResponse
from app.services.user_service import UserService
from app.services.third_party_auth import ThirdPartyAuthService
from app.api.deps import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# 第三方登录相关端点
@router.get("/dingtalk/login")
async def dingtalk_login():
    """钉钉登录入口"""
    try:
        auth_url = ThirdPartyAuthService.generate_dingtalk_auth_url()
        return RedirectResponse(auth_url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/dingtalk/callback")
async def dingtalk_callback(
    code: str = Query(...),
    db: Session = Depends(get_db)
):
    """钉钉回调处理"""
    result = await ThirdPartyAuthService.handle_dingtalk_callback(code, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="钉钉认证失败"
        )
    
    # 认证成功后，将token作为URL参数传递给前端回调页面
    # 这样前端可以直接从URL中获取token，避免cookie传递的问题
    callback_url = f"{settings.FRONTEND_BASE_URL}/auth/dingtalk/callback?access_token={result['access_token']}"
    
    # 创建重定向响应
    response = RedirectResponse(callback_url)
    
    return response

@router.get("/github/login")
async def github_login():
    """GitHub登录入口"""
    try:
        auth_url = ThirdPartyAuthService.generate_github_auth_url()
        return RedirectResponse(auth_url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/github/callback")
async def github_callback(
    code: str = Query(...),
    db: Session = Depends(get_db)
):
    """GitHub回调处理"""
    result = await ThirdPartyAuthService.handle_github_callback(code, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub认证失败"
        )
    
    # 认证成功后，将token作为URL参数传递给前端回调页面
    # 这样前端可以直接从URL中获取token，避免cookie传递的问题
    callback_url = f"{settings.FRONTEND_BASE_URL}/auth/github/callback?access_token={result['access_token']}"
    
    # 创建重定向响应
    response = RedirectResponse(callback_url)
    
    return response

@router.post("/register", response_model=UserResponse)
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Register endpoint called with email: {user_create.email}")
    user_service = UserService(db)
    
    # 检查用户是否已存在
    existing_user = user_service.get_by_email(user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 创建用户
    user = user_service.create(user_create)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at
    )

@router.post("/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user_service = UserService(db)
    
    # 验证用户
    user = user_service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    
    # 返回包含用户信息的响应
    return LoginResponse(
        access_token=access_token, 
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"]
    )

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新当前用户信息"""
    logger.info(f"更新用户信息请求 - 用户ID: {current_user['id']}, 更新数据: {user_update.model_dump()}")
    user_service = UserService(db)
    
    # 更新用户信息
    updated_user = user_service.update(current_user["id"], user_update)
    if not updated_user:
        logger.error(f"用户不存在: {current_user['id']}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info(f"用户信息更新成功 - 用户ID: {updated_user.id}, 新姓名: {updated_user.full_name}")
    
    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        full_name=updated_user.full_name,
        is_active=updated_user.is_active,
        created_at=updated_user.created_at
    )