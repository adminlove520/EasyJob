from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_v1.api import api_router
from app.core.database import engine, Base
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 添加中间件来记录请求
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# 运行数据库迁移和创建表
try:
    import subprocess
    import os
    
    # 尝试运行Alembic迁移
    logger.info("运行数据库迁移...")
    
    # 尝试不同的工作目录
    possible_dirs = ["/app", "/app/backend", ".", "./backend", "../"]
    migration_success = False
    
    for work_dir in possible_dirs:
        try:
            if os.path.exists(work_dir):
                logger.info(f"尝试在目录 {work_dir} 运行迁移")
                # 首先检查当前迁移状态
                logger.info(f"在 {work_dir} 检查迁移状态")
                
                # 检查当前迁移状态
                current_result = subprocess.run(
                    ["alembic", "current"], 
                    cwd=work_dir,
                    capture_output=True, 
                    text=True
                )
                
                current_revision = None
                if current_result.returncode == 0:
                    # 从输出中提取当前版本号
                    for line in current_result.stdout.strip().split('\n'):
                        if line and not line.startswith('INFO'):
                            current_revision = line.strip()
                            break
                    logger.info(f"当前迁移状态: {current_revision}")
                
                # 如果没有迁移状态，标记基础迁移为已完成
                if not current_revision:
                    stamp_result = subprocess.run(
                        ["alembic", "stamp", "7445f3b0d307"], 
                        cwd=work_dir,
                        capture_output=True, 
                        text=True
                    )
                    
                    if stamp_result.returncode == 0:
                        logger.info("成功标记基础迁移为已完成")
                
                # 然后运行增量迁移
                result = subprocess.run(
                    ["alembic", "upgrade", "head"], 
                    cwd=work_dir,
                    capture_output=True, 
                    text=True
                )
                if result.returncode == 0:
                    logger.info(f"数据库迁移成功 (在 {work_dir})")
                    migration_success = True
                    break
                else:
                    logger.warning(f"在 {work_dir} 迁移失败: {result.stderr}")
        except Exception as e:
            logger.warning(f"在 {work_dir} 迁移出错: {e}")
            continue
    
    if not migration_success:
        logger.error("所有路径的迁移都失败了")
        # 如果迁移失败，使用create_all作为后备
        logger.info("使用create_all作为后备方案")
        Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"迁移过程出错: {e}")
    # 使用create_all作为后备
    Base.metadata.create_all(bind=engine)

# 从环境变量获取CORS配置
cors_origins = settings.BACKEND_CORS_ORIGINS
logger.info(f"CORS Origins from settings: {cors_origins}")
logger.info(f"CORS Origins type: {type(cors_origins)}")

# 为了本地开发方便，始终允许所有来源的CORS请求
logger.info("Using wildcard CORS origins for development")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该限制为特定域名
    allow_credentials=True,  # 允许携带凭证(cookies等)
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
    expose_headers=["*"],  # 暴露所有响应头
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Chat Resume API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/v1/test")
async def test_endpoint():
    return {"message": "API is working", "cors": "enabled"}

# 移除手动OPTIONS处理，让CORS中间件自动处理