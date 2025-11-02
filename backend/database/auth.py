"""
用户认证服务
"""
import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from sqlalchemy.orm import Session

from .models import User, UserRole


class AuthService:
    """认证服务"""

    # JWT配置
    SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

    def hash_password(self, password: str) -> str:
        """密码哈希"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    def create_access_token(self, user_id: int, username: str, role: str) -> str:
        """创建JWT token"""
        expire = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)

    def decode_token(self, token: str) -> Optional[dict]:
        """解码JWT token"""
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def register_user(
        self,
        session: Session,
        username: str,
        email: str,
        password: str,
        role: str = UserRole.USER.value
    ) -> tuple[Optional[User], Optional[str]]:
        """
        注册新用户
        
        Returns:
            (user, error_message)
        """
        # 检查用户名是否已存在
        existing_user = session.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                return None, "用户名已存在"
            else:
                return None, "邮箱已被注册"

        # 创建新用户
        password_hash = self.hash_password(password)
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            can_use_avatar=False if role == UserRole.USER.value else True,
            is_active=True
        )
        
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        
        return new_user, None

    def login(
        self,
        session: Session,
        username: str,
        password: str
    ) -> tuple[Optional[str], Optional[User], Optional[str]]:
        """
        用户登录
        
        Returns:
            (token, user, error_message)
        """
        # 查找用户
        user = session.query(User).filter(User.username == username).first()
        
        if not user:
            return None, None, "用户名或密码错误"
        
        if not user.is_active:
            return None, None, "账户已被禁用"
        
        # 验证密码
        if not self.verify_password(password, user.password_hash):
            return None, None, "用户名或密码错误"
        
        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        session.commit()
        
        # 生成token
        token = self.create_access_token(user.id, user.username, user.role)
        
        return token, user, None

    def get_current_user(self, session: Session, token: str) -> Optional[User]:
        """根据token获取当前用户"""
        payload = self.decode_token(token)
        if not payload:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        return session.query(User).filter(User.id == user_id).first()

    def check_permission(self, user: User, required_permission: str = "use_avatar") -> bool:
        """检查用户权限"""
        if not user or not user.is_active:
            return False
        
        # 管理员拥有所有权限
        if user.role == UserRole.ADMIN.value:
            return True
        
        # 检查特定权限
        if required_permission == "use_avatar":
            return user.can_use_avatar
        
        return False


# 全局认证服务实例
auth_service = AuthService()
