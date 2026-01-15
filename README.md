# Address Management API

A production-ready FastAPI microservice for address validation and recognition, built with modern async Python patterns and following best practices for scalable API development.

## Overview

This service provides comprehensive address management capabilities including:

- **Address Validation** - Validate and normalize addresses with batch processing support
- **Address Recognition** - Extract structured address data from unstructured text
- **Async Processing** - Background job processing with ARQ and Redis
- **RESTful API** - Clean, well-documented API endpoints following REST principles

## Technology Stack

- **Python 3.13** - Latest Python features and performance improvements
- **FastAPI** - Modern, fast web framework for building APIs
- **SQLAlchemy 2.x** - Async ORM with type safety
- **PostgreSQL** - Robust relational database
- **asyncpg** - High-performance async PostgreSQL driver
- **Alembic** - Database migration management
- **Redis** - Caching and message queue backend
- **ARQ** - Async task queue for background processing
- **Docker & Docker Compose** - Containerized deployment

## Project Structure

```
src/
├── app/
│   ├── api/v1/endpoints/     # API route handlers
│   ├── services/              # Business logic layer
│   ├── models/                # SQLAlchemy database models
│   ├── schemas/               # Pydantic validation schemas
│   ├── crud/                  # Database operation helpers
│   ├── workers/               # Background job workers
│   └── core/                  # Core configuration and utilities
│       ├── config.py          # Application settings
│       └── db/                # Database connection management
├── alembic/                   # Database migrations
└── main.py                    # Application entry point
```

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Python 3.13+ (for local development)

### Environment Setup

Create a `.env` file in the project root:

```env
ENVIRONMENT=local

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_SERVER=postgres
POSTGRES_PORT=5432
POSTGRES_DB=address_api

REDIS_URL=redis://redis:6379/0
SQL_ECHO=false
```

### Running with Docker

Start all services:

```bash
docker compose up --build
```

This will:
- Start PostgreSQL and Redis containers
- Run database migrations automatically
- Start the FastAPI application on port `8000`
- Start the ARQ worker for background processing

### API Documentation

Interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Address Validation

#### Validate Addresses

```http
POST /v1/addresses/validate
```

Validates addresses synchronously and returns results immediately.

**Query Parameters:**
- `async` (boolean): If `true`, queues validation for background processing

**Response:**
- `200 OK`: Validation results (sync mode)
- `202 Accepted`: Batch queued (async mode, empty body)
- Header `X-Validation-Batch-Id`: Batch identifier

#### Get Validation Results

```http
GET /v1/addresses/validate/{batch_id}
```

Retrieve validation results for a specific batch.

#### Batch Management

```http
GET    /v1/validation-batches              # List all batches
GET    /v1/validation-batches/{batch_id}   # Get batch details
POST   /v1/validation-batches/{batch_id}/requeue  # Requeue batch
DELETE /v1/validation-batches/{batch_id}   # Delete batch
```

### Address Recognition

#### Recognize Addresses

```http
PUT /v1/addresses/recognize
```

Extract structured address data from text input.

**Query Parameters:**
- `async` (boolean): If `true`, queues recognition for background processing

**Response:**
- `200 OK`: Recognition results (sync mode)
- `202 Accepted`: Batch queued (async mode, empty body)
- Header `X-Recognition-Id`: Recognition batch identifier

#### Get Recognition Results

```http
GET /v1/addresses/recognize/{recognition_id}
```

Retrieve recognition results for a specific batch.

## Background Processing

The service uses ARQ (Async Redis Queue) for background job processing:

- Jobs are enqueued via Redis
- Worker processes jobs transactionally
- Batch status transitions: `queued` → `processing` → `completed` / `failed`

## Example Requests

### Address Validation

```json
POST /v1/addresses/validate
[
  {
    "name": "John Doe",
    "address_line1": "123 Main Street",
    "city_locality": "New York",
    "state_province": "NY",
    "postal_code": "10001",
    "country_code": "US"
  }
]
```

### Address Recognition

```json
PUT /v1/addresses/recognize
[
  {
    "text": "John Doe, 123 Main St, New York, NY 10001, US",
    "address": {
      "name": "John Doe",
      "address_line1": "123 Main St",
      "city_locality": "New York",
      "state_province": "NY",
      "postal_code": "10001",
      "country_code": "US"
    }
  }
]
```

## Development

### Local Development Setup

1. Install dependencies:
```bash
uv sync
```

2. Run migrations:
```bash
alembic upgrade head
```

3. Start the development server:
```bash
uvicorn app.main:app --reload
```

4. Start the worker (in separate terminal):
```bash
arq app.workers.arq_worker.ARQWorkerConfig
```

### Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "Description"
```

Apply migrations:
```bash
alembic upgrade head
```

## Architecture Notes

- **Async/Await**: Full async support throughout the application
- **Type Safety**: Comprehensive type hints and Pydantic validation
- **Transaction Safety**: All database operations are transactional
- **Error Handling**: Proper HTTP status codes and error messages
- **Scalability**: Designed for horizontal scaling with stateless workers

## License

This project is provided as-is for demonstration and development purposes.
