import httpx
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User
from app.core.security import create_access_token
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class ThirdPartyAuthService:
    """第三方认证服务类"""
    
    @staticmethod
    def generate_dingtalk_auth_url() -> str:
        """生成钉钉认证URL - 根据官方文档修正"""
        if not settings.DINGTALK_CLIENT_ID or not settings.DINGTALK_REDIRECT_URI:
            raise ValueError("钉钉OAuth配置不完整")
        
        # 钉钉扫码登录授权URL
        auth_url = (
            "https://oapi.dingtalk.com/connect/qrconnect?"
            f"appid={settings.DINGTALK_CLIENT_ID}&"
            "response_type=code&"
            "scope=snsapi_login&"
            f"redirect_uri={settings.DINGTALK_REDIRECT_URI}&"
            "state=STATE"
        )
        return auth_url
    
    @staticmethod
    async def handle_dingtalk_callback(code: str, db: Session) -> Optional[Dict[str, Any]]:
        """处理钉钉回调，获取用户信息并生成令牌 - 根据官方文档修正"""
        try:
            # 1. 获取钉钉开放平台的appToken
            token_response = await httpx.post(
                "https://oapi.dingtalk.com/sns/gettoken",
                params={
                    "appid": settings.DINGTALK_CLIENT_ID,
                    "appsecret": settings.DINGTALK_CLIENT_SECRET
                }
            )
            token_data = token_response.json()
            if token_data.get("errcode") != 0:
                logger.error(f"钉钉获取appToken失败: {token_data}")
                return None
            
            app_token = token_data.get("access_token")
            
            # 2. 使用临时授权码获取授权用户的持久授权码
            persistent_code_response = await httpx.post(
                "https://oapi.dingtalk.com/sns/get_persistent_code",
                params={"access_token": app_token},
                json={"tmp_auth_code": code}
            )
            persistent_code_data = persistent_code_response.json()
            if persistent_code_data.get("errcode") != 0:
                logger.error(f"钉钉获取持久授权码失败: {persistent_code_data}")
                return None
            
            openid = persistent_code_data.get("openid")
            persistent_code = persistent_code_data.get("persistent_code")
            
            # 3. 获取用户授权的snsToken
            sns_token_response = await httpx.post(
                "https://oapi.dingtalk.com/sns/get_sns_token",
                params={
                    "appid": settings.DINGTALK_CLIENT_ID,
                    "appsecret": settings.DINGTALK_CLIENT_SECRET
                }
            )
            sns_token_data = sns_token_response.json()
            if sns_token_data.get("errcode") != 0:
                logger.error(f"钉钉获取snsToken失败: {sns_token_data}")
                return None
            
            sns_token = sns_token_data.get("sns_token")
            
            # 4. 使用snsToken获取用户信息
            user_info_response = await httpx.post(
                "https://oapi.dingtalk.com/sns/getuserinfo",
                params={"sns_token": sns_token},
                json={
                    "openid": openid,
                    "persistent_code": persistent_code
                }
            )
            user_info_data = user_info_response.json()
            if user_info_data.get("errcode") != 0:
                logger.error(f"钉钉获取用户信息失败: {user_info_data}")
                return None
            
            # 处理用户信息 - 钉钉用户信息格式: {"nick": "昵称", "unionid": "唯一标识", ...}
            user_data = user_info_data.get("user_info", {})
            # 添加unionid到用户数据中，以便更准确地标识用户
            if "unionid" in persistent_code_data:
                user_data["unionid"] = persistent_code_data["unionid"]
            
            # 5. 查找或创建用户 - 优先使用unionid作为用户标识
            # 钉钉返回的用户标识有两种：
            # - openid: 用户在当前应用内的唯一标识
            # - unionid: 用户在钉钉全平台的唯一标识（更可靠）
            provider_user_id = user_data.get("unionid", openid)  # 优先使用unionid
            
            # 先尝试通过unionid查找用户（如果有）
            if "unionid" in user_data:
                user = db.query(User).filter(
                    User.provider == "dingtalk",
                    User.provider_user_id == user_data["unionid"]
                ).first()
            
            # 如果没有找到，再通过openid查找
            if not user:
                user = db.query(User).filter(
                    User.provider == "dingtalk",
                    User.provider_user_id == openid
                ).first()
            
            if not user:
                # 创建新用户
                # 钉钉用户信息中不一定包含email字段
                user_email = user_data.get("email", f"dingtalk_{provider_user_id[:10]}@example.com")
                user_nickname = user_data.get("nick", f"钉钉用户_{provider_user_id[:8]}")
                
                user = User(
                    provider="dingtalk",
                    provider_user_id=provider_user_id,
                    provider_email=user_email,
                    provider_data=json.dumps(user_data),  # 保存完整的用户信息
                    email=user_email,
                    full_name=user_nickname,
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                # 更新现有用户的信息
                user.provider_data = json.dumps(user_data)
                if user_data.get("nick"):
                    user.full_name = user_data["nick"]
                if user_data.get("email"):
                    user.provider_email = user_data["email"]
                    user.email = user_data["email"]
                db.commit()
                db.refresh(user)
            
            try:
                # 6. 生成访问令牌
                access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = create_access_token(
                    subject=user.id, expires_delta=access_token_expires
                )
                
                logger.info(f"钉钉用户 {user.full_name} 登录成功，用户ID: {user.id}")
                
                # 返回令牌和用户信息
                return {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "full_name": user.full_name,
                        "is_active": user.is_active,
                        "provider": user.provider,
                        "created_at": user.created_at.isoformat() if user.created_at else None
                    }
                }
            except Exception as e:
                logger.error(f"生成钉钉用户访问令牌失败: {str(e)}")
                raise
        
        except httpx.RequestError as e:
            logger.error(f"钉钉API请求异常: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"钉钉API响应解析失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"钉钉认证处理异常: {str(e)}")
            # 记录详细异常堆栈
            logger.exception("钉钉认证异常详情")
            return None
    
    @staticmethod
    def generate_github_auth_url() -> str:
        """生成GitHub认证URL"""
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_REDIRECT_URI:
            raise ValueError("GitHub OAuth配置不完整")
        
        auth_url = (
            "https://github.com/login/oauth/authorize?"
            f"client_id={settings.GITHUB_CLIENT_ID}&"
            f"redirect_uri={settings.GITHUB_REDIRECT_URI}&"
            "scope=user:email,read:user"
        )
        return auth_url
    
    @staticmethod
    async def handle_github_callback(code: str, db: Session) -> Optional[Dict[str, Any]]:
        """处理GitHub回调，获取用户信息并生成令牌"""
        try:
            # 1. 通过code获取access_token
            token_response = await httpx.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                json={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_REDIRECT_URI
                }
            )
            
            token_response.raise_for_status()  # 检查HTTP响应状态
            token_data = token_response.json()
            
            if "access_token" not in token_data:
                logger.error(f"GitHub获取token失败: {token_data}")
                return None
            
            access_token = token_data.get("access_token")
            
            # 2. 使用access_token获取用户信息
            user_response = await httpx.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            user_response.raise_for_status()
            user_data = user_response.json()
            
            # 3. 获取用户邮箱信息
            emails_response = await httpx.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            emails_response.raise_for_status()
            emails_data = emails_response.json()
            
            # 找到主邮箱
            primary_email = next((email["email"] for email in emails_data if email.get("primary", False)), None)
            if not primary_email and emails_data:
                primary_email = emails_data[0]["email"]
            
            # 4. 查找或创建用户
            provider_user_id = str(user_data.get("id"))
            user = db.query(User).filter(
                User.provider == "github",
                User.provider_user_id == provider_user_id
            ).first()
            
            if not user:
                # 创建新用户
                user_email = primary_email or f"github_{provider_user_id}@example.com"
                user_name = user_data.get("name", user_data.get("login", f"GitHub用户_{provider_user_id[:8]}"))
                
                user = User(
                    provider="github",
                    provider_user_id=provider_user_id,
                    provider_email=primary_email,
                    provider_data=json.dumps(user_data),
                    email=user_email,
                    full_name=user_name,
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                # 更新现有用户的信息
                user.provider_data = json.dumps(user_data)
                if user_data.get("name"):
                    user.full_name = user_data["name"]
                elif user_data.get("login"):
                    user.full_name = user_data["login"]
                if primary_email:
                    user.provider_email = primary_email
                    user.email = primary_email
                db.commit()
                db.refresh(user)
            
            try:
                # 5. 生成访问令牌
                access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = create_access_token(
                    subject=user.id, expires_delta=access_token_expires
                )
                
                logger.info(f"GitHub用户 {user.full_name} 登录成功，用户ID: {user.id}")
                
                # 返回令牌和用户信息
                return {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "full_name": user.full_name,
                        "is_active": user.is_active,
                        "provider": user.provider,
                        "created_at": user.created_at.isoformat() if user.created_at else None
                    }
                }
            except Exception as e:
                logger.error(f"生成GitHub用户访问令牌失败: {str(e)}")
                raise
        
        except httpx.RequestError as e:
            logger.error(f"GitHub API请求异常: {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API返回错误状态码: {e.response.status_code}, 响应: {await e.response.text()}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"GitHub API响应解析失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"GitHub认证处理异常: {str(e)}")
            # 记录详细异常堆栈
            logger.exception("GitHub认证异常详情")
            return None