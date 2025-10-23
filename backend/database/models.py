"""
数据库模型定义
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

Base = declarative_base()


class UserRole(str, Enum):
    """用户角色枚举"""
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.USER.value, nullable=False)
    can_use_avatar = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"

    def to_dict(self, include_sensitive=False):
        """转换为字典"""
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "can_use_avatar": self.can_use_avatar,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_active": self.is_active,
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
        return data


# 数据库连接管理
class DatabaseManager:
    """数据库管理器"""

    def __init__(self, database_url: str = "sqlite:///./lightavatar.db"):
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # SQLite需要
            echo=False
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    def init_admin_user(self, username: str = "admin", email: str = "admin@example.com", password: str = "admin123"):
        """初始化管理员用户"""
        from .auth import AuthService
        
        session = self.get_session()
        try:
            # 检查是否已存在管理员
            existing_admin = session.query(User).filter_by(username=username).first()
            if existing_admin:
                return existing_admin

            # 创建默认管理员
            auth_service = AuthService()
            password_hash = auth_service.hash_password(password)
            
            admin = User(
                username=username,
                email=email,
                password_hash=password_hash,
                role=UserRole.ADMIN.value,
                can_use_avatar=True,
                is_active=True
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
            return admin
        finally:
            session.close()


# 全局数据库管理器实例
db_manager = DatabaseManager()
