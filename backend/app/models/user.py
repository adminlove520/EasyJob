from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)  # 修改为可为空，支持第三方登录没有email的情况
    hashed_password = Column(String, nullable=True)  # 修改为可为空，第三方登录不需要密码
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 第三方登录相关字段
    provider = Column(String, nullable=True)  # 登录提供商: dingtalk, github
    provider_user_id = Column(String, nullable=True)  # 提供商用户ID
    provider_email = Column(String, nullable=True)  # 提供商返回的邮箱
    provider_data = Column(String, nullable=True)  # 提供商返回的其他数据（JSON格式）
    
    # Relationships
    resumes = relationship("Resume", back_populates="owner")