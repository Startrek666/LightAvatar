"""
用户认证API路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from backend.database.models import db_manager, User, UserRole
from backend.database.auth import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


# ==================== 请求/响应模型 ====================

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    can_use_avatar: bool
    created_at: str
    last_login: Optional[str]
    is_active: bool


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


class UpdatePermissionRequest(BaseModel):
    can_use_avatar: bool


class UpdateRoleRequest(BaseModel):
    role: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


# ==================== 依赖项：获取当前用户 ====================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """获取当前登录用户"""
    token = credentials.credentials
    session = db_manager.get_session()
    try:
        user = auth_service.get_current_user(session, token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭据"
            )
        return user
    finally:
        session.close()


async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """要求当前用户为管理员"""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


# ==================== 路由 ====================

@router.post("/register", response_model=LoginResponse)
async def register(request: RegisterRequest):
    """用户注册"""
    session = db_manager.get_session()
    try:
        user, error = auth_service.register_user(
            session,
            username=request.username,
            email=request.email,
            password=request.password
        )
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error
            )
        
        # 自动登录
        token = auth_service.create_access_token(
            user.id,
            user.username,
            user.role
        )
        
        return LoginResponse(
            token=token,
            user=UserResponse(**user.to_dict())
        )
    finally:
        session.close()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """用户登录"""
    session = db_manager.get_session()
    try:
        token, user, error = auth_service.login(
            session,
            username=request.username,
            password=request.password
        )
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error
            )
        
        return LoginResponse(
            token=token,
            user=UserResponse(**user.to_dict())
        )
    finally:
        session.close()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(**current_user.to_dict())


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_admin: User = Depends(get_current_admin)
):
    """获取用户列表（仅管理员）"""
    session = db_manager.get_session()
    try:
        users = session.query(User).offset(skip).limit(limit).all()
        return [UserResponse(**user.to_dict()) for user in users]
    finally:
        session.close()


@router.put("/users/{user_id}/permission")
async def update_user_permission(
    user_id: int,
    request: UpdatePermissionRequest,
    current_admin: User = Depends(get_current_admin)
):
    """更新用户权限（仅管理员）"""
    session = db_manager.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        user.can_use_avatar = request.can_use_avatar
        session.commit()
        session.refresh(user)
        
        return {"message": "权限更新成功", "user": UserResponse(**user.to_dict())}
    finally:
        session.close()


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    request: UpdateRoleRequest,
    current_admin: User = Depends(get_current_admin)
):
    """更新用户角色（仅管理员）"""
    if request.role not in [UserRole.USER.value, UserRole.ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的角色类型"
        )
    
    session = db_manager.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 不允许修改自己的角色
        if user.id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能修改自己的角色"
            )
        
        user.role = request.role
        session.commit()
        session.refresh(user)
        
        return {"message": "角色更新成功", "user": UserResponse(**user.to_dict())}
    finally:
        session.close()


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin)
):
    """删除用户（仅管理员）"""
    session = db_manager.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 不允许删除自己
        if user.id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除自己"
            )
        
        session.delete(user)
        session.commit()
        
        return {"message": "用户删除成功"}
    finally:
        session.close()


@router.put("/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: int,
    current_admin: User = Depends(get_current_admin)
):
    """启用/禁用用户（仅管理员）"""
    session = db_manager.get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 不允许禁用自己
        if user.id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能禁用自己"
            )
        
        user.is_active = not user.is_active
        session.commit()
        session.refresh(user)
        
        status_text = "启用" if user.is_active else "禁用"
        return {"message": f"用户已{status_text}", "user": UserResponse(**user.to_dict())}
    finally:
        session.close()


@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user)
):
    """修改密码"""
    session = db_manager.get_session()
    try:
        # 验证旧密码
        if not auth_service.verify_password(request.old_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前密码错误"
            )
        
        # 更新密码
        current_user.password_hash = auth_service.hash_password(request.new_password)
        session.merge(current_user)
        session.commit()
        
        return {"message": "密码修改成功"}
    finally:
        session.close()
