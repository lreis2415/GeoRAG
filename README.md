# GeoRAG

[中文](./README.zh-CN.md) | English

## Overview

GeoRAG is a geographic information Q&A system based on Retrieval-Augmented Generation (RAG) technology. It adopts a layered architecture design, providing document management, vector database management, and intelligent Q&A capabilities.

## Features

- **Document Management**: Upload, download, and delete CSV, JSON, and TXT format files
- **Vector Database Management**: Create, add files, delete, and query vector databases
- **Intelligent Q&A**: Provide accurate geographic information Q&A services based on RAG technology, combining vector retrieval and generative models
- **Multi-Model Support**: Support multiple embedding models and chat models with flexible configuration
- **Multi-Database**: Support both Pgvector and ChromaDB vector databases
- **MCP Tool Integration**: Integrate Model Context Protocol tools to extend system functionality

## Quick Start

### Prerequisites

- Python 3.9+ (3.11 recommended)
- Docker (for containerized deployment)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file or set via command line:

```bash
export OPENAI_API_KEY=your_api_key
export OPENAI_API_BASE=your_api_base
export EMBEDDING_API_URL=your_embedding_api_url
export DB_URL=postgresql://user:password@host:port/database
export USE_PGVECTOR=true  # Use Pgvector (recommended)
# export USE_PGVECTOR=false  # Use ChromaDB
export DEFAULT_EMBEDDING_MODEL=text-embedding-v4
export JWT_PUBLIC_KEY_PATH=.secrets/jwt/public.pem
export AUTH_ENABLED=true

# One-click launcher (start-mac.sh / start-win.bat): conda environment name.
# Leave unset to use the script's default (langchain_v03).
export GEORAG_CONDA_ENV=langchain_v03

# Local debugging only: bypass JWT and use a fixed synthetic user identity.
# export AUTH_ENABLED=false
# export AUTH_DEBUG_USER_ID=local-debug-user
```

### Start Database

**When using Pgvector, you need to start the PostgreSQL database first:**

```bash
# Start only PostgreSQL database service (local development mode)
docker-compose up -d postgres

# Verify pgvector extension is installed successfully
docker exec -it georag-postgres psql -U geo -d georag_dev -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"

# View container logs
docker-compose logs -f postgres
```

> **Note**: For local development, only the `postgres` service needs to be started, and the application is started via `python main.py`. For full containerized deployment, use `docker-compose up -d` to start all services.

**To reset the database:**

```bash
# Stop and delete old containers and data volumes
docker-compose down -v

# Restart containers
docker-compose up -d postgres
```

### Start Service

```bash
# Development mode start (recommended)
python main.py

# Or use uvicorn to start directly
uvicorn main:app --host 0.0.0.0 --port 7512 --reload
```

After the service starts:
- Service URL: http://0.0.0.0:7512
- API Docs: http://0.0.0.0:7512/docs
- Health Check: http://0.0.0.0:7512/llm/

### One-Click Launch

Repository ships with two launcher scripts (per platform):

| Script | Platform |
|--------|----------|
| `start-mac.sh` | macOS / Linux |
| `start-win.bat` | Windows |

The scripts automate the whole startup flow:
1. Read the conda environment name (priority: CLI argument > `GEORAG_CONDA_ENV` env var > project `.env` file > default `langchain_v03`)
2. Locate conda automatically and activate the environment
3. Check that project dependencies are installed (auto-install if missing)
4. Optionally start the Pgvector database container when `USE_PGVECTOR=true`
5. Start the service and open the API docs in your browser

**Configure the environment name** — add it to your local `.env` (ignored by git, never committed):

```bash
# .env
GEORAG_CONDA_ENV=langchain_v03
```

Or set it as a system environment variable:

```bash
# macOS / Linux
echo 'export GEORAG_CONDA_ENV=langchain_v03' >> ~/.zshrc && source ~/.zshrc

# Windows (run once)
setx GEORAG_CONDA_ENV langchain_v03
```

**Run:**

```bash
# macOS / Linux
./start-mac.sh

# Windows (double-click or in cmd)
start-win.bat
```

Optional arguments (both scripts):
- `<env_name>` — temporarily launch with another conda environment
- `--skip-db` — skip the Pgvector database check/startup

### Local Debug Authentication

Authentication is enabled by default. Protected endpoints require a Java-issued
RS256 JWT with a valid `sub` and `exp` claim.

For local debugging, authentication can be disabled through environment
variables:

```bash
export AUTH_ENABLED=false
export AUTH_DEBUG_USER_ID=local-debug-user
python main.py
```

When `AUTH_ENABLED=false`, the service does not require an `Authorization`
header or verify a JWT. It creates a synthetic debug identity and passes
`AUTH_DEBUG_USER_ID` to all user-scoped queries. The value is only a stable
string; it does not need to exist in the Java user database.

To access data that was previously assigned to a specific user ID, set
`AUTH_DEBUG_USER_ID` to that exact value. Restore `AUTH_ENABLED=true` after
debugging. Never disable authentication in production or on a publicly
reachable service.

## Usage

### Document Management

| Function | Method | Path |
|----------|--------|------|
| Upload Document | POST | `/llm/documents/upload` |
| Download Document | GET | `/llm/documents/download/{filename}` |
| Delete Document | DELETE | `/llm/documents/{filename}` |
| List Documents | GET | `/llm/documents` |

### Database Management

| Function | Method | Path |
|----------|--------|------|
| Create Database | POST | `/llm/databases` |
| Add Files to Database | POST | `/llm/databases/add` |
| Delete Database | DELETE | `/llm/databases/{db_name}` |
| List Databases | GET | `/llm/databases` |

### Intelligent Q&A

| Function | Method | Path |
|----------|--------|------|
| Ask Question | POST | `/llm/chat/ask` |
| Agent Q&A | POST | `/llm/chat/agent` |

## Configuration Details

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `OPENAI_API_BASE` | OpenAI API base URL | Yes |
| `EMBEDDING_API_URL` | Embedding model API URL | Yes |
| `DB_URL` | PostgreSQL database connection string | Yes (Pgvector) |
| `USE_PGVECTOR` | Vector database backend selection (true=pgvector, false=chromadb) | No |
| `DEFAULT_EMBEDDING_MODEL` | Default embedding model | No |
| `JWT_PUBLIC_KEY_PATH` | Path to the Java JWT RSA public key | Yes when authentication is enabled |
| `AUTH_ENABLED` | Enable JWT authentication (default: true) | No |
| `AUTH_DEBUG_USER_ID` | Synthetic user ID used when `AUTH_ENABLED=false` | No |

### Model Configuration (models.yaml)

#### Embedding Models
- `llama3.3-70b-instruct`
- `llama3.1-70b-instruct`
- `text-embedding-v4`

#### Chat Models
- `qwen-turbo-latest`
- `deepseek-v3`
- `qwen-plus-2025-07-28`
- `qwen3-235b-a22b-instruct-2507`

### Vector Database Backends

#### Pgvector (Recommended)
- **Advantages**: Unified PostgreSQL tech stack, ACID transaction support, high-performance HNSW indexing
- **Configuration**: `USE_PGVECTOR=true`
- **Requirements**: PostgreSQL 16+ with pgvector extension

#### ChromaDB (Alternative)
- **Advantages**: Standalone deployment, easy testing, backward compatibility
- **Configuration**: `USE_PGVECTOR=false`
- **Data Storage**: Local file system

## Docker Deployment

### Using Docker Compose

```bash
# Start PostgreSQL container (Pgvector)
docker-compose up -d

# Verify pgvector extension
docker exec -it georag-postgres psql -U geo -d georag_dev -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

### Using Dockerfile

```bash
# Build and run Docker container
./run_docker.sh
```

## Code Quality

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Manually run all checks
pre-commit run --all-files
```

### Code Quality Tools

```bash
# Format code
black .

# Sort imports
isort .

# Code style check
flake8 .

# Type check
mypy .

# Security check
bandit -r .
```

## Architecture

### Layered Architecture Design

```
app/
├── routers/          # API router layer - Handle HTTP requests
├── services/         # Business logic layer - Implement core functionality
├── dao/             # Data access layer - Database operations
└── utils/           # Utility layer - Configuration, exception handling, etc.
```

### Project Structure

```
GeoRAG/
├── .gitignore
├── .pre-commit-config.yaml  # Pre-commit hooks configuration
├── Dockerfile
├── docker-compose.yml       # Docker Compose configuration
├── main.py                  # Main application entry point
├── models.yaml              # Model configuration file
├── pyproject.toml           # Code quality tools configuration
├── requirements.txt         # Dependency list
├── run_docker.sh            # Script to run Docker container
├── app/                     # Application core code
│   ├── dao/                # Data access layer
│   │   ├── VectorDB.py          # Vector database abstract base class
│   │   ├── PgvectorVectorDB.py  # Pgvector implementation
│   │   ├── FlexibleVectorDB.py  # ChromaDB implementation
│   │   └── DataBase.py          # Base database operations
│   ├── routers/            # API router layer
│   │   ├── chat.py             # Chat and Q&A endpoints
│   │   ├── databases.py        # Vector database management endpoints
│   │   ├── documents.py        # Document management endpoints
│   │   ├── models.py           # Model management endpoints
│   │   └── health.py           # Health check endpoint
│   ├── services/           # Business logic layer
│   │   ├── chat_service.py      # Chat service
│   │   ├── database_service.py  # Database service
│   │   ├── document_service.py  # Document service
│   │   ├── model_service.py     # Model service
│   │   ├── mcp_service.py       # MCP tool integration service
│   │   └── rag_service.py       # RAG core service
│   └── utils/              # Utility layer
│       ├── config.py           # Application configuration management
│       ├── dependencies.py     # Dependency injection
│       ├── exceptions.py       # Exception handling
│       ├── models.py           # Data models
│       └── response.py         # Response formatting
├── data/                  # Data storage directory
│   ├── documents/         # Document storage
│   └── database/          # Vector database storage (ChromaDB)
├── tests/                 # Test files
└── archive/               # Archive directory
    └── GeoRAGService/     # Legacy code archive
```

## Notes

- API Documentation: Visit http://0.0.0.0:7512/docs after starting the service to view the complete interactive API documentation
- Document Storage: `data/documents/` directory
- Vector Database Storage:
  - Pgvector: PostgreSQL database
  - ChromaDB: `data/database/` directory

## Development Guide

For detailed development guidelines, please refer to the [CLAUDE.md](./CLAUDE.md) file.

## License

MIT License
