# Frontend Integration Guide

## CSV to Parquet Converter API

> Complete guide for frontend developers to integrate with the CSV to Parquet Converter API

---

## 🌐 **Base Configuration**

```javascript
// config.js
export const API_CONFIG = {
  BASE_URL: process.env.REACT_APP_API_URL || "http://localhost:8000",
  CREDENTIALS: { username: "test", password: "password" },
  MAX_FILE_SIZE: 100 * 1024 * 1024, // 100MB
};
```

---

## 🔐 **Authentication Flow**

### **1. Login & Token Management**

```javascript
// services/auth.js
class AuthService {
  async login(username, password) {
    const response = await fetch(`${API_CONFIG.BASE_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) throw new Error("Login failed");

    const data = await response.json();
    localStorage.setItem("token", data.access_token);
    return data;
  }

  getToken() {
    return localStorage.getItem("token");
  }

  logout() {
    localStorage.removeItem("token");
  }

  isAuthenticated() {
    return !!this.getToken();
  }
}

export const authService = new AuthService();
```

### **2. API Client with Auto-Auth**

```javascript
// services/apiClient.js
class APIClient {
  async request(endpoint, options = {}) {
    const token = authService.getToken();
    const config = {
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      ...options,
    };

    const response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`, config);

    if (response.status === 401) {
      authService.logout();
      window.location.href = "/login";
      return;
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }

    return response.json();
  }
}

export const apiClient = new APIClient();
```

---

## 📁 **API Endpoints & Responses**

### **File Upload**

```javascript
// POST /upload
const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  return apiClient.request('/upload', {
    method: 'POST',
    body: formData,
    headers: {} // Let browser set Content-Type for FormData
  });
};

// Response:
{
  "id": 1,
  "filename": "data.csv",
  "upload_timestamp": "2024-01-15T10:30:00",
  "row_count": 150,
  "status": "Processing", // "Processing" | "Done" | "Error"
  "parquet_path": "parquet/data.parquet"
}
```

### **Get Files**

```javascript
// GET /files
const getFiles = () => apiClient.request("/files");

// Response: Array of file objects
[
  {
    id: 1,
    filename: "employees.csv",
    upload_timestamp: "2024-01-15T10:30:00",
    row_count: 150,
    status: "Done",
    parquet_path: "parquet/employees.parquet",
  },
];
```

### **Delete File**

```javascript
// DELETE /files/{id}
const deleteFile = (id) => apiClient.request(`/files/${id}`, { method: 'DELETE' });

// Response:
{ "message": "File deleted successfully" }
```

---

## 🎯 **Status Processing Flow**

Files go through this lifecycle:

1. **Upload** → Status: `"Processing"`
2. **3 seconds later** → Status: `"Done"` (if successful) or `"Error"` (if failed)

```javascript
// Monitor status changes
const pollFileStatus = async (fileId) => {
  const checkStatus = async () => {
    try {
      const file = await apiClient.request(`/files/${fileId}`);

      if (file.status === "Done" || file.status === "Error") {
        return file; // Processing complete
      }

      setTimeout(checkStatus, 2000); // Check again in 2 seconds
    } catch (error) {
      console.error("Status check failed:", error);
    }
  };

  return checkStatus();
};
```

---

## 💻 **React Components**

### **File Upload Component**

```jsx
// components/FileUpload.jsx
import React, { useState } from "react";

const FileUpload = ({ onSuccess, onError }) => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async () => {
    if (!file) return;

    // Validate file
    if (!file.name.endsWith(".csv")) {
      onError("Only CSV files allowed");
      return;
    }

    if (file.size > API_CONFIG.MAX_FILE_SIZE) {
      onError("File too large (max 100MB)");
      return;
    }

    setUploading(true);
    try {
      const result = await uploadFile(file);
      onSuccess(result);
      setFile(null);
    } catch (error) {
      onError(error.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <input
        type="file"
        accept=".csv"
        onChange={(e) => setFile(e.target.files[0])}
        disabled={uploading}
      />
      <button onClick={handleUpload} disabled={!file || uploading}>
        {uploading ? "Uploading..." : "Upload"}
      </button>
    </div>
  );
};
```

### **File List Component**

```jsx
// components/FileList.jsx
import React, { useState, useEffect } from "react";

const FileList = () => {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchFiles = async () => {
    try {
      const data = await getFiles();
      setFiles(data);
    } catch (error) {
      console.error("Failed to fetch files:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteFile(id);
      setFiles(files.filter((f) => f.id !== id));
    } catch (error) {
      alert("Delete failed: " + error.message);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <h2>Files ({files.length})</h2>
      {files.map((file) => (
        <div key={file.id} className="file-item">
          <span>{file.filename}</span>
          <span className={`status ${file.status.toLowerCase()}`}>
            {file.status}
          </span>
          <span>{file.row_count} rows</span>
          <button onClick={() => handleDelete(file.id)}>Delete</button>
        </div>
      ))}
    </div>
  );
};
```

---

## 🚨 **Error Handling**

### **HTTP Status Codes**

```javascript
const handleAPIError = (error, status) => {
  switch (status) {
    case 400:
      return "Invalid request - check your data";
    case 401:
      return "Please log in again";
    case 404:
      return "File not found";
    case 500:
      return "Server error - try again later";
    default:
      return error.message || "Something went wrong";
  }
};
```

### **Common Error Responses**

```json
// Login errors
{ "detail": "Incorrect username or password" }

// Upload errors
{ "detail": "Only CSV files are allowed" }
{ "detail": "File is empty" }

// Auth errors
{ "detail": "Invalid authentication credentials" }
```

---

## 🎨 **UI States & Styling**

### **Status Badges**

```css
.status {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
}

.status.processing {
  background: #fff3cd;
  color: #856404;
}
.status.done {
  background: #d4edda;
  color: #155724;
}
.status.error {
  background: #f8d7da;
  color: #721c24;
}
```

### **Loading States**

```jsx
// Loading spinner component
const LoadingSpinner = () => <div className="spinner">Processing...</div>;

// Usage in components
{
  uploading && <LoadingSpinner />;
}
```

---

## 🔧 **Development Setup**

### **Environment Variables**

```bash
# .env
REACT_APP_API_URL=http://localhost:8000
```

### **CORS Headers**

The API is configured to accept requests from:

- `http://localhost:3000` (React dev server)
- `http://localhost:3001` (Alternative dev server)

---

## 📋 **Integration Checklist**

### **Authentication ✅**

- [ ] Login form
- [ ] Token storage
- [ ] Auto-logout on 401
- [ ] Protected routes

### **File Operations ✅**

- [ ] File upload with validation
- [ ] File list with status
- [ ] Delete functionality
- [ ] Error handling

### **UX Enhancements ✅**

- [ ] Loading indicators
- [ ] Error messages
- [ ] Success notifications
- [ ] Status badges

### **Testing ✅**

- [ ] API client tests
- [ ] Component tests
- [ ] Error scenarios
- [ ] File upload edge cases

---

## 🚀 **Quick Start**

1. **Install dependencies:**

   ```bash
   npm install # or yarn install
   ```

2. **Set environment:**

   ```bash
   echo "REACT_APP_API_URL=http://localhost:8000" > .env
   ```

3. **Start backend:**

   ```bash
   cd backend/python
   python run.py --debug --reload
   ```

4. **Use in your app:**

   ```jsx
   import { authService, uploadFile, getFiles } from "./services/api";

   // Login
   await authService.login("test", "password");

   // Upload file
   const result = await uploadFile(csvFile);

   // Get files
   const files = await getFiles();
   ```

---

## 📚 **API Reference**

| Method | Endpoint      | Auth | Description         |
| ------ | ------------- | ---- | ------------------- |
| POST   | `/login`      | ❌   | User authentication |
| POST   | `/upload`     | ✅   | Upload CSV file     |
| GET    | `/files`      | ✅   | Get all files       |
| GET    | `/files/{id}` | ✅   | Get file by ID      |
| DELETE | `/files/{id}` | ✅   | Delete file         |
| GET    | `/health`     | ❌   | Health check        |

**Base URL:** `http://localhost:8000`  
**Auth:** Bearer token in Authorization header  
**Content-Type:** `application/json` (except file uploads)

---

🎉 **Ready for seamless integration!** Check the [Swagger docs](http://localhost:8000/docs) for interactive testing.
