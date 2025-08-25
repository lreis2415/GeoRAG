#!/usr/bin/env python3
"""
GeoRAG应用启动脚本
"""

import uvicorn
from app.utils.config import config

if __name__ == "__main__":
    print(f"🚀 启动 {config.APP_NAME}")
    print(f"📍 服务地址: http://{config.HOST}:{config.PORT}")
    print(f"📖 API文档: http://{config.HOST}:{config.PORT}/docs")
    print(f"🔍 健康检查: http://{config.HOST}:{config.PORT}{config.API_PREFIX}/")
    
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,  # 开发模式下自动重载
        log_level="info"
    )