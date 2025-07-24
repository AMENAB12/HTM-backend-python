# CSV to Parquet Converter API

A professional FastAPI backend service for uploading CSV files and converting them to Parquet format with JWT authentication.

## 🏗️ Architecture

This project follows a **senior-level, modular architecture** with clear separation of concerns:

```
app/
├── api/
│   ├── routes/          # API route modules
│   │   ├── auth.py      # Authentication endpoints
│   │   ├── files.py     # File operations
│   │   └── health.py    # Health checks
│   └── dependencies.py  # Shared dependencies
├── core/
│   ├── config.py        # Configuration management
│   ├── database.py      # Database operations
│   └── security.py      # Authentication & security
├── models/
│   └── file_metadata.py # Data models
├── services/            # Business logic services
└── utils/
    └── file_processor.py # File processing utilities
```

## 🚀 Features

- **JWT Authentication** with secure token management
- **CSV to Parquet Conversion** with validation
- **Async File Processing** with status tracking
- **RESTful API** with comprehensive documentation
- **Professional Code Structure** following best practices
- **Interactive Swagger UI** for API testing
- **Error Handling** and validation
- **CORS Support** for frontend integration

## 📋 Prerequisites

- Python 3.8+
- pip package manager

## 🛠️ Installation & Setup

1. **Clone and navigate to the project:**

   ```bash
   cd HTM-backend-python
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Environment configuration:**

   - The `.env` file is already configured with default values
   - Modify `.env` for production settings

4. **Run the application:**
   ```bash
   python run.py --debug --reload
   ```

## 📖 API Documentation

### 🌐 Access Swagger UI

Open your browser and navigate to:
**http://localhost:8000/docs**

### 🔐 Authentication

**Login Endpoint:**

- **URL:** `POST /login`
- **Credentials:**
  ```json
  {
    "username": "test",
    "password": "password"
  }
  ```

### 📁 File Operations

All file endpoints require Bearer token authentication.

**Upload CSV:**

- **URL:** `POST /upload`
- **Body:** Form data with CSV file
- **Response:** File metadata with processing status

**List Files:**

- **URL:** `GET /files`
- **Response:** Array of all uploaded files

**Get File by ID:**

- **URL:** `GET /files/{file_id}`
- **Response:** Specific file metadata

**Delete File:**

- **URL:** `DELETE /files/{file_id}`
- **Response:** Deletion confirmation

## 🧪 Testing

### Using Swagger UI (Recommended)

1. Open http://localhost:8000/docs
2. Click "Authorize" and login with test credentials
3. Test any endpoint interactively

### Using curl commands

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "password"}' | \
  jq -r '.access_token')

# Upload file
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.csv"

# List files
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/files
```

## 📂 Sample Data

The project includes sample CSV files for testing:

- `sample_employees.csv` - Employee data
- `sample_products.csv` - Product catalog
- `empty_file.csv` - For testing error handling

## 🔧 Configuration

Key configuration options in `.env`:

```env
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Database
DATABASE_PATH=metadata.db

# File Storage
UPLOAD_DIR=uploads
PARQUET_DIR=parquet

# Authentication
JWT_SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

## 🏃 Running Options

```bash
# Development mode (auto-reload, debug)
python run.py --debug --reload

# Production mode
python run.py --env production

# Custom host/port
python run.py --host 127.0.0.1 --port 8080

# View all options
python run.py --help
```

## 📊 API Endpoints Summary

| Method | Endpoint      | Description         | Auth Required |
| ------ | ------------- | ------------------- | ------------- |
| POST   | `/login`      | User authentication | ❌            |
| GET    | `/`           | API information     | ❌            |
| GET    | `/health`     | Health check        | ❌            |
| POST   | `/upload`     | Upload CSV file     | ✅            |
| GET    | `/files`      | List all files      | ✅            |
| GET    | `/files/{id}` | Get file by ID      | ✅            |
| DELETE | `/files/{id}` | Delete file         | ✅            |

## 🔄 File Processing Flow

1. **Upload** → CSV file is uploaded and validated
2. **Processing** → File is converted to Parquet format
3. **Storage** → Metadata is stored in SQLite database
4. **Status Update** → Status changes from "Processing" to "Done"

## 📝 Development Notes

- **Modular Design:** Each component has a single responsibility
- **Type Hints:** Full type annotation for better code quality
- **Async/Await:** Non-blocking file operations
- **Error Handling:** Comprehensive error responses
- **Logging:** Structured logging for debugging
- **Security:** JWT tokens with expiration
- **Testing:** Pytest-ready test structure

## 🚀 Production Deployment

For production deployment:

1. Set `ENVIRONMENT=production` in `.env`
2. Update `JWT_SECRET_KEY` with a secure key
3. Configure proper CORS origins
4. Use a production WSGI server like Gunicorn
5. Set up proper logging and monitoring

---

**Ready to test!** 🎉 Open http://localhost:8000/docs and explore the interactive API documentation.
