# API Specification for Frontend Integration

## CSV to Parquet Converter API

### 🌐 **Base Information**

- **Base URL:** `http://localhost:8000`
- **Authentication:** Bearer Token (JWT)
- **Content-Type:** `application/json` (except file uploads)

---

## 🔐 **Authentication**

### POST `/login`

**Description:** Authenticate user and receive access token

**Request Body:**

```json
{
  "username": "test",
  "password": "password"
}
```

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "message": "Login successful"
}
```

**Error (401):**

```json
{
  "detail": "Incorrect username or password"
}
```

---

## 📁 **File Operations**

### POST `/upload`

**Description:** Upload CSV file for processing  
**Auth Required:** ✅

**Request:** Multipart form data with file field

**Response (200):**

```json
{
  "id": 1,
  "filename": "data.csv",
  "upload_timestamp": "2024-01-15T10:30:00.123456",
  "row_count": 150,
  "status": "Processing",
  "parquet_path": "parquet/data.parquet"
}
```

**Status Values:**

- `"Processing"` - File is being converted (3 seconds)
- `"Done"` - Conversion completed successfully
- `"Error"` - File was empty or had errors

### GET `/files`

**Description:** Get all uploaded files  
**Auth Required:** ✅

**Response (200):** Array of file objects

```json
[
  {
    "id": 1,
    "filename": "employees.csv",
    "upload_timestamp": "2024-01-15T10:30:00.123456",
    "row_count": 150,
    "status": "Done",
    "parquet_path": "parquet/employees.parquet"
  }
]
```

### GET `/files/{file_id}`

**Description:** Get specific file metadata  
**Auth Required:** ✅

**Response (200):** Single file object
**Error (404):** `{"detail": "File not found"}`

### GET `/files/{file_id}/data`

**Description:** Get file data content with pagination  
**Auth Required:** ✅

**Query Parameters:**

- `limit` (int): Number of rows to return (default: 100)
- `offset` (int): Number of rows to skip (default: 0)
- `format` (string): Data format 'csv' or 'parquet' (default: 'parquet')

**Response (200):**

```json
{
  "file_id": 1,
  "filename": "data.csv",
  "format": "parquet",
  "total_rows": 1500,
  "returned_rows": 100,
  "offset": 0,
  "limit": 100,
  "columns": ["id", "name", "email", "department"],
  "data": [
    {
      "id": 1,
      "name": "John",
      "email": "john@company.com",
      "department": "Engineering"
    }
  ]
}
```

### GET `/files/{file_id}/statistics`

**Description:** Get comprehensive file statistics and data analysis  
**Auth Required:** ✅

**Response (200):**

```json
{
  "file_info": {
    "id": 1,
    "filename": "employees.csv",
    "total_rows": 1500,
    "total_columns": 5
  },
  "columns": [
    {
      "name": "salary",
      "data_type": "int64",
      "missing_count": 2,
      "missing_percentage": 0.13,
      "unique_count": 847,
      "min_value": 35000,
      "max_value": 150000,
      "mean_value": 72450.5
    }
  ],
  "data_quality": {
    "total_missing_values": 15,
    "missing_percentage": 0.2,
    "duplicate_rows": 3
  },
  "file_sizes": {
    "csv_size_bytes": 125000,
    "parquet_size_bytes": 45000,
    "compression_ratio": 2.78,
    "space_saved_percentage": 64.0
  }
}
```

### GET `/files/{file_id}/preview`

**Description:** Get quick data preview comparing CSV and Parquet formats  
**Auth Required:** ✅

**Query Parameters:**

- `rows` (int): Number of preview rows (default: 10)

**Response (200):**

```json
{
  "file_id": 1,
  "filename": "employees.csv",
  "status": "Done",
  "csv_preview": {
    "columns": ["id", "name", "email"],
    "data": [...],
    "rows_returned": 10
  },
  "parquet_preview": {
    "columns": ["id", "name", "email"],
    "data": [...],
    "rows_returned": 10
  }
}
```

### DELETE `/files/{file_id}`

**Description:** Delete file and metadata  
**Auth Required:** ✅

**Response (200):**

```json
{
  "message": "File deleted successfully"
}
```

---

## 🏥 **System Endpoints**

### GET `/health`

**Description:** API health check  
**Auth Required:** ❌

**Response (200):**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.123456",
  "service": "CSV to Parquet Converter API"
}
```

### GET `/`

**Description:** API information  
**Auth Required:** ❌

**Response (200):**

```json
{
  "message": "CSV to Parquet Converter API",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

---

## 🚨 **Error Handling**

### HTTP Status Codes

- **200** - Success
- **400** - Bad Request (validation errors)
- **401** - Unauthorized (invalid/missing token)
- **404** - Not Found
- **500** - Internal Server Error

### Common Error Format

```json
{
  "detail": "Human-readable error message"
}
```

### File Upload Errors

- `"Only CSV files are allowed"`
- `"File is empty"`
- `"Error processing file: [details]"`

---

## 🔄 **Integration Flow**

1. **Login** → Get access token
2. **Store token** → Use in Authorization header
3. **Upload file** → Receive immediate response with "Processing" status
4. **Poll status** → Check file status until "Done" or "Error"
5. **List files** → Get all uploaded files
6. **Delete files** → Remove unwanted files

### JavaScript Example

```javascript
// 1. Login
const response = await fetch("http://localhost:8000/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username: "test", password: "password" }),
});
const { access_token } = await response.json();

// 2. Upload file
const formData = new FormData();
formData.append("file", csvFile);

const uploadResponse = await fetch("http://localhost:8000/upload", {
  method: "POST",
  headers: { Authorization: `Bearer ${access_token}` },
  body: formData,
});
const fileData = await uploadResponse.json();

// 3. Get files
const filesResponse = await fetch("http://localhost:8000/files", {
  headers: { Authorization: `Bearer ${access_token}` },
});
const files = await filesResponse.json();
```

---

## 📊 **Expected Frontend Features**

### User Interface

- [ ] Login form
- [ ] File upload (drag & drop recommended)
- [ ] File list with status indicators
- [ ] Delete file buttons
- [ ] Error/success notifications

### Technical Requirements

- [ ] JWT token management
- [ ] File validation (CSV only, size limits)
- [ ] Status polling for uploads
- [ ] Error handling for all scenarios
- [ ] Loading states during operations

---

**Interactive Documentation:** http://localhost:8000/docs
