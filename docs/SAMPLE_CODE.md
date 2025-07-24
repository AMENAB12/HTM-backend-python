# Sample Code for Frontend Integration

## 🔥 **Complete React Example**

```jsx
// App.jsx - Complete working example
import React, { useState, useEffect } from "react";
import "./App.css";

const API_BASE = "http://localhost:8000";

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // API Helper
  const apiCall = async (endpoint, options = {}) => {
    const config = {
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      ...options,
    };

    const response = await fetch(`${API_BASE}${endpoint}`, config);

    if (response.status === 401) {
      setToken(null);
      localStorage.removeItem("token");
      return;
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }

    return response.json();
  };

  // Login
  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const data = await apiCall("/login", {
        method: "POST",
        body: JSON.stringify({ username: "test", password: "password" }),
      });

      setToken(data.access_token);
      localStorage.setItem("token", data.access_token);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  };

  // Fetch Files
  const fetchFiles = async () => {
    setLoading(true);
    try {
      const data = await apiCall("/files");
      setFiles(data || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Upload File
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.endsWith(".csv")) {
      setError("Only CSV files are allowed");
      return;
    }

    setUploading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const result = await apiCall("/upload", {
        method: "POST",
        body: formData,
        headers: {}, // Let browser set Content-Type
      });

      setFiles([result, ...files]);
      e.target.value = ""; // Clear input
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  // Delete File
  const deleteFile = async (id) => {
    try {
      await apiCall(`/files/${id}`, { method: "DELETE" });
      setFiles(files.filter((f) => f.id !== id));
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    if (token) {
      fetchFiles();
    }
  }, [token]);

  if (!token) {
    return (
      <div className="login-container">
        <h1>CSV to Parquet Converter</h1>
        <form onSubmit={handleLogin}>
          <button type="submit">Login (test/password)</button>
        </form>
        {error && <div className="error">{error}</div>}
      </div>
    );
  }

  return (
    <div className="app">
      <header>
        <h1>CSV to Parquet Converter</h1>
        <button
          onClick={() => {
            setToken(null);
            localStorage.removeItem("token");
          }}
        >
          Logout
        </button>
      </header>

      <main>
        <section className="upload-section">
          <h2>Upload CSV File</h2>
          <input
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            disabled={uploading}
          />
          {uploading && <div>Uploading...</div>}
        </section>

        <section className="files-section">
          <h2>Files ({files.length})</h2>
          <button onClick={fetchFiles} disabled={loading}>
            {loading ? "Loading..." : "Refresh"}
          </button>

          {files.length === 0 ? (
            <p>No files uploaded yet.</p>
          ) : (
            <div className="files-grid">
              {files.map((file) => (
                <div key={file.id} className="file-card">
                  <h3>{file.filename}</h3>
                  <p>Rows: {file.row_count}</p>
                  <p>
                    Status:{" "}
                    <span className={`status ${file.status.toLowerCase()}`}>
                      {file.status}
                    </span>
                  </p>
                  <p>
                    Uploaded:{" "}
                    {new Date(file.upload_timestamp).toLocaleDateString()}
                  </p>
                  <button onClick={() => deleteFile(file.id)}>Delete</button>
                </div>
              ))}
            </div>
          )}
        </section>

        {error && <div className="error">{error}</div>}
      </main>
    </div>
  );
}

export default App;
```

## 📱 **Vue.js Example**

```vue
<!-- App.vue -->
<template>
  <div id="app">
    <!-- Login Form -->
    <div v-if="!token" class="login">
      <h1>CSV to Parquet Converter</h1>
      <button @click="login">Login (test/password)</button>
      <div v-if="error" class="error">{{ error }}</div>
    </div>

    <!-- Main App -->
    <div v-else>
      <header>
        <h1>CSV to Parquet Converter</h1>
        <button @click="logout">Logout</button>
      </header>

      <!-- Upload Section -->
      <section>
        <h2>Upload CSV</h2>
        <input
          type="file"
          accept=".csv"
          @change="uploadFile"
          :disabled="uploading"
        />
        <div v-if="uploading">Uploading...</div>
      </section>

      <!-- Files List -->
      <section>
        <h2>Files ({{ files.length }})</h2>
        <button @click="fetchFiles" :disabled="loading">
          {{ loading ? "Loading..." : "Refresh" }}
        </button>

        <div v-if="files.length === 0">No files yet.</div>
        <div v-else class="files-grid">
          <div v-for="file in files" :key="file.id" class="file-card">
            <h3>{{ file.filename }}</h3>
            <p>Rows: {{ file.row_count }}</p>
            <p>
              Status:
              <span :class="`status ${file.status.toLowerCase()}`">
                {{ file.status }}
              </span>
            </p>
            <button @click="deleteFile(file.id)">Delete</button>
          </div>
        </div>
      </section>

      <div v-if="error" class="error">{{ error }}</div>
    </div>
  </div>
</template>

<script>
const API_BASE = "http://localhost:8000";

export default {
  data() {
    return {
      token: localStorage.getItem("token"),
      files: [],
      uploading: false,
      loading: false,
      error: "",
    };
  },

  methods: {
    async apiCall(endpoint, options = {}) {
      const config = {
        headers: {
          "Content-Type": "application/json",
          ...(this.token && { Authorization: `Bearer ${this.token}` }),
        },
        ...options,
      };

      const response = await fetch(`${API_BASE}${endpoint}`, config);

      if (response.status === 401) {
        this.logout();
        return;
      }

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail);
      }

      return response.json();
    },

    async login() {
      try {
        const data = await this.apiCall("/login", {
          method: "POST",
          body: JSON.stringify({ username: "test", password: "password" }),
        });

        this.token = data.access_token;
        localStorage.setItem("token", this.token);
        this.error = "";
        this.fetchFiles();
      } catch (err) {
        this.error = err.message;
      }
    },

    logout() {
      this.token = null;
      localStorage.removeItem("token");
      this.files = [];
    },

    async fetchFiles() {
      this.loading = true;
      try {
        const data = await this.apiCall("/files");
        this.files = data || [];
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    async uploadFile(event) {
      const file = event.target.files[0];
      if (!file) return;

      if (!file.name.endsWith(".csv")) {
        this.error = "Only CSV files are allowed";
        return;
      }

      this.uploading = true;
      this.error = "";

      try {
        const formData = new FormData();
        formData.append("file", file);

        const result = await this.apiCall("/upload", {
          method: "POST",
          body: formData,
          headers: {},
        });

        this.files.unshift(result);
        event.target.value = "";
      } catch (err) {
        this.error = err.message;
      } finally {
        this.uploading = false;
      }
    },

    async deleteFile(id) {
      try {
        await this.apiCall(`/files/${id}`, { method: "DELETE" });
        this.files = this.files.filter((f) => f.id !== id);
      } catch (err) {
        this.error = err.message;
      }
    },
  },

  mounted() {
    if (this.token) {
      this.fetchFiles();
    }
  },
};
</script>
```

## 🚀 **Vanilla JavaScript (No Framework)**

```html
<!DOCTYPE html>
<html>
  <head>
    <title>CSV to Parquet Converter</title>
    <style>
      body {
        font-family: Arial, sans-serif;
        margin: 20px;
      }
      .error {
        color: red;
        margin: 10px 0;
      }
      .file-card {
        border: 1px solid #ddd;
        padding: 15px;
        margin: 10px 0;
      }
      .status.processing {
        color: orange;
      }
      .status.done {
        color: green;
      }
      .status.error {
        color: red;
      }
      button {
        margin: 5px;
        padding: 8px 15px;
      }
      input[type="file"] {
        margin: 10px 0;
      }
    </style>
  </head>
  <body>
    <div id="app"></div>

    <script>
      const API_BASE = "http://localhost:8000";
      let token = localStorage.getItem("token");
      let files = [];

      // API Helper
      async function apiCall(endpoint, options = {}) {
        const config = {
          headers: {
            "Content-Type": "application/json",
            ...(token && { Authorization: `Bearer ${token}` }),
          },
          ...options,
        };

        const response = await fetch(`${API_BASE}${endpoint}`, config);

        if (response.status === 401) {
          token = null;
          localStorage.removeItem("token");
          render();
          return;
        }

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail);
        }

        return response.json();
      }

      // Login
      async function login() {
        try {
          const data = await apiCall("/login", {
            method: "POST",
            body: JSON.stringify({ username: "test", password: "password" }),
          });

          token = data.access_token;
          localStorage.setItem("token", token);
          await fetchFiles();
          render();
        } catch (err) {
          showError(err.message);
        }
      }

      // Fetch Files
      async function fetchFiles() {
        try {
          files = (await apiCall("/files")) || [];
          render();
        } catch (err) {
          showError(err.message);
        }
      }

      // Upload File
      async function uploadFile(event) {
        const file = event.target.files[0];
        if (!file) return;

        if (!file.name.endsWith(".csv")) {
          showError("Only CSV files are allowed");
          return;
        }

        try {
          const formData = new FormData();
          formData.append("file", file);

          const result = await apiCall("/upload", {
            method: "POST",
            body: formData,
            headers: {},
          });

          files.unshift(result);
          event.target.value = "";
          render();
        } catch (err) {
          showError(err.message);
        }
      }

      // Delete File
      async function deleteFile(id) {
        try {
          await apiCall(`/files/${id}`, { method: "DELETE" });
          files = files.filter((f) => f.id !== id);
          render();
        } catch (err) {
          showError(err.message);
        }
      }

      // Show Error
      function showError(message) {
        const errorDiv = document.createElement("div");
        errorDiv.className = "error";
        errorDiv.textContent = message;

        const app = document.getElementById("app");
        app.insertBefore(errorDiv, app.firstChild);

        setTimeout(() => errorDiv.remove(), 5000);
      }

      // Render UI
      function render() {
        const app = document.getElementById("app");

        if (!token) {
          app.innerHTML = `
                    <h1>CSV to Parquet Converter</h1>
                    <button onclick="login()">Login (test/password)</button>
                `;
          return;
        }

        app.innerHTML = `
                <header>
                    <h1>CSV to Parquet Converter</h1>
                    <button onclick="token = null; localStorage.removeItem('token'); render();">
                        Logout
                    </button>
                </header>

                <section>
                    <h2>Upload CSV</h2>
                    <input type="file" accept=".csv" onchange="uploadFile(event)" />
                </section>

                <section>
                    <h2>Files (${files.length})</h2>
                    <button onclick="fetchFiles()">Refresh</button>
                    
                    ${files.length === 0 ? "<p>No files yet.</p>" : ""}
                    
                    <div class="files-grid">
                        ${files
                          .map(
                            (file) => `
                            <div class="file-card">
                                <h3>${file.filename}</h3>
                                <p>Rows: ${file.row_count}</p>
                                <p>Status: <span class="status ${file.status.toLowerCase()}">
                                    ${file.status}
                                </span></p>
                                <p>Uploaded: ${new Date(
                                  file.upload_timestamp
                                ).toLocaleDateString()}</p>
                                <button onclick="deleteFile(${
                                  file.id
                                })">Delete</button>
                            </div>
                        `
                          )
                          .join("")}
                    </div>
                </section>
            `;
      }

      // Initialize
      if (token) {
        fetchFiles();
      } else {
        render();
      }
    </script>
  </body>
</html>
```

## 🎯 **Testing Examples**

```javascript
// test/api.test.js
import { apiClient, authService } from "../services/api";

describe("API Integration", () => {
  beforeEach(() => {
    // Mock successful login
    authService.login = jest.fn().mockResolvedValue({
      access_token: "mock-token",
      token_type: "bearer",
    });
  });

  test("should login successfully", async () => {
    const result = await authService.login("test", "password");
    expect(result.access_token).toBe("mock-token");
  });

  test("should upload file", async () => {
    const mockFile = new File(["csv,data"], "test.csv", { type: "text/csv" });
    const result = await uploadFile(mockFile);

    expect(result).toHaveProperty("id");
    expect(result).toHaveProperty("filename", "test.csv");
    expect(result).toHaveProperty("status", "Processing");
  });

  test("should handle upload errors", async () => {
    const mockFile = new File([""], "empty.csv", { type: "text/csv" });

    await expect(uploadFile(mockFile)).rejects.toThrow("File is empty");
  });
});
```

---

🎉 **Copy, paste, and customize these examples for your project!**
