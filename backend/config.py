import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
DATABASE = os.path.join(INSTANCE_DIR, 'opinion.db')
JWT_SECRET = os.getenv('JWT_SECRET', 'opinion-system-secret-key-2026')
JWT_ALGORITHM = 'HS256'

# 成员 C 产出的数据文件
DATA_FILE = os.path.join(BASE_DIR, '..', 'crawler', 'data', 'analysis_result.json')

# LLM 服务包路径（成员 D）
LLM_SERVICE_DIR = os.path.join(BASE_DIR, '..', 'LLM', 'llm_service')
