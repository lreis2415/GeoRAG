# 案例推理代码库

## 1. 仓库概述
本代码库实现了一个基于案例推理的系统，主要用于地理空间数据分析。它包含两种主要的推理方法：DSM（数字表面模型）案例推理和RF（随机森林）案例推理。该库可用于处理地理空间数据，生成新的案例，并进行统计分析。

主要功能：
- 支持多种地理空间数据格式（如TIFF、Excel）
- 提供两种不同的案例推理方法
- 自动化Docker镜像构建和部署
- 可扩展的案例管理框架

## 2. 目录结构
```
├── .gitignore                # Git忽略规则
├── CaseFormat.py             # 案例格式处理工具
├── caseReasoningApp.py       # 主应用程序入口
├── CaseReasonmingMethod.py   # 案例推理方法实现
├── config.yaml               # 配置文件
├── Dockerfile                # Docker构建文件
├── README.md                 # 项目文档
├── Reasoning.py              # 推理核心逻辑
├── request.txt               # 示例请求文件
├── run_docker.sh             # Docker运行脚本
├── Docker/                   # Docker相关文件
│   └── dockerfile.txt        # Dockerfile说明文档
├── DSMCaseReasoning/         # DSM案例推理模块
│   ├── CaseReasoning.py      # DSM推理实现
│   ├── NewCase.py            # 新案例生成
│   └── src/                  # 数据文件
│       ├── cases.xlsx        # 案例数据
│       ├── dem_xc.tif        # 宣城DEM数据
│       ├── demhs.tif         # 鹤山DEM数据
│       ├── envClass.xlsx     # 环境分类数据
│       ├── finalStatistic_MS.xls  # 统计结果
│       ├── newCase.xlsx      # 新案例模板
│       ├── heshan/           # 鹤山数据
│       │   └── dem_hs_rp.tif # 鹤山重投影数据
│       └── xuancheng/        # 宣城数据
│           └── dem_xc_rp.tif # 宣城重投影数据
└── RFCaseReasoning/          # RF案例推理模块
    ├── CaseReasoning.py      # RF推理实现
    └── NewCase.py            # 新案例生成
```

## 3. 文件描述

### 核心文件
- `caseReasoningApp.py`: 主应用程序入口，负责初始化系统和处理请求
- `Reasoning.py`: 包含案例推理的核心逻辑和算法实现
- `CaseFormat.py`: 处理案例数据的格式转换和验证
- `config.yaml`: 系统配置文件，包含路径、参数等设置

### 数据文件
- `DSMCaseReasoning/src/`: 包含所有DSM案例推理所需的数据文件
- `RFCaseReasoning/src/`: 包含所有RF案例推理所需的数据文件

## 4. 镜像打包说明

### 前提条件
- 已安装Docker
- 已安装Python 3.8+

### 构建镜像
```bash
docker build -t case-reasoning .
```

### 运行容器
```bash
docker run -it --rm case-reasoning
```

或使用提供的脚本：
```bash
./run_docker.sh
```

## 5. 依赖项

### Python依赖
- numpy
- pandas
- scikit-learn
- rasterio
- openpyxl

安装所有依赖：
```bash
pip install -r requirements.txt
```

### 系统依赖
- GDAL
- Docker

## 6. 使用示例

### 运行DSM案例推理
```python
from DSMCaseReasoning import CaseReasoning

reasoner = CaseReasoning()
result = reasoner.process_case('path/to/case.xlsx')
```

### 生成新案例
```python
from DSMCaseReasoning import NewCase

new_case = NewCase()
new_case.generate('output_case.xlsx')
```

## 7. 贡献指南

欢迎贡献！请遵循以下步骤：
1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

请确保代码符合PEP8标准，并添加适当的单元测试。

## 8. 许可证信息
本项目采用MIT许可证。详情请见LICENSE文件。

## 9. 附加资源
- [GDAL文档](https://gdal.org/documentation.html)
- [Rasterio文档](https://rasterio.readthedocs.io/)
- [Scikit-learn文档](https://scikit-learn.org/stable/)