from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password

class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, user_id: int) -> User:
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_by_email(self, email: str) -> User:
        return self.db.query(User).filter(User.email == email).first()
    
    def create(self, user_create: UserCreate) -> User:
        hashed_password = get_password_hash(user_create.password)
        user = User(
            email=user_create.email,
            hashed_password=hashed_password,
            full_name=user_create.full_name
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def authenticate(self, email: str, password: str) -> User:
        user = self.get_by_email(email)
        if not user:
            return None
        # 对于第三方登录的用户，可能没有密码字段（hashed_password为None）
        if user.hashed_password is None:
            return None  # 第三方登录用户不能通过密码登录
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    def update(self, user_id: int, user_update: UserUpdate) -> User:
        """更新用户信息"""
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        # 更新用户信息
        if user_update.full_name is not None:
            user.full_name = user_update.full_name
        
        self.db.commit()
        self.db.refresh(user)
        return user