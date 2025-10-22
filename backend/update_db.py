import sqlite3

# 连接到SQLite数据库
conn = sqlite3.connect('chat_resume.db')
cursor = conn.cursor()

try:
    # 执行SQL语句
    print("开始更新users表...")
    
    # 添加provider字段
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN provider VARCHAR DEFAULT NULL")
        print("成功添加provider字段")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("provider字段已存在")
        else:
            raise
    
    # 添加provider_user_id字段
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN provider_user_id VARCHAR DEFAULT NULL")
        print("成功添加provider_user_id字段")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("provider_user_id字段已存在")
        else:
            raise
    
    # 添加provider_email字段
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN provider_email VARCHAR DEFAULT NULL")
        print("成功添加provider_email字段")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("provider_email字段已存在")
        else:
            raise
    
    # 添加provider_data字段
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN provider_data VARCHAR DEFAULT NULL")
        print("成功添加provider_data字段")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("provider_data字段已存在")
        else:
            raise
    
    # 修改email和hashed_password字段为可为空
    # SQLite不直接支持ALTER TABLE修改NOT NULL约束
    # 所以我们需要创建新表、复制数据、删除旧表、重命名新表
    print("修改email和hashed_password字段约束...")
    
    # 创建临时表
    cursor.execute('''
    CREATE TABLE users_new (
        id INTEGER NOT NULL PRIMARY KEY,
        email VARCHAR,
        hashed_password VARCHAR,
        full_name VARCHAR,
        is_active BOOLEAN,
        is_superuser BOOLEAN,
        created_at DATETIME,
        updated_at DATETIME,
        provider VARCHAR,
        provider_user_id VARCHAR,
        provider_email VARCHAR,
        provider_data VARCHAR
    )
    ''')
    
    # 复制数据
    cursor.execute('''
    INSERT INTO users_new (id, email, hashed_password, full_name, is_active, is_superuser, created_at, updated_at)
    SELECT id, email, hashed_password, full_name, is_active, is_superuser, created_at, updated_at
    FROM users
    ''')
    
    # 删除旧表
    cursor.execute("DROP TABLE users")
    
    # 重命名新表
    cursor.execute("ALTER TABLE users_new RENAME TO users")
    
    # 重建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    
    print("成功修改字段约束")
    
    # 提交事务
    conn.commit()
    print("数据库更新完成！")
    
    # 验证表结构
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("\n更新后的users表结构:")
    for col in columns:
        print(f"{col[1]}: {col[2]} {'NOT NULL' if col[3] else 'NULL'}")
        
except Exception as e:
    print(f"更新过程中出错: {e}")
    conn.rollback()
finally:
    # 关闭连接
    conn.close()