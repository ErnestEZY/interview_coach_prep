# System Architecture Patterns

This document explains the two primary architecture patterns used in this project: **Two-Tier (Client-Server) Architecture** and **4-Layer Architecture**.

---

### **1. Macro Level: Two-Tier (Client-Server) Architecture**

The overall project follows a **Two-Tier Architecture**, which simplifies the system into two main roles: the **Client** and the **Server**.

*   **Tier 1: Client Tier (Presentation)**
    - **Components**: Vue.js Web App, Flutter Mobile App, Tauri Desktop App.
    - **Role**: This is the front-facing part of the application. It handles all user interactions and displays data to the user. It communicates with the Server Tier via RESTful API calls.

*   **Tier 2: Server Tier (Logic, Data & Infrastructure)**
    - **Components**: FastAPI (Python) Backend, MongoDB Atlas, and External APIs.
    - **Role**: This tier acts as the central hub for the entire application. It contains the "Brain" of the system, manages the data, and integrates with external services. **Internally, this tier is organized using a 4-Layer Architecture.**

---

### **2. Internal Level: 4-Layer Architecture (Inside Tier 2)**

To keep the system organized, the **Server Tier** is divided into four logical **Layers**. This ensures a clear separation of concerns between how the server receives requests, processes logic, and manages external resources.

#### Layer 1: Presentation Layer
*   **Location**: `backend/controllers/`
*   **Brief Explanation**: This layer acts as the entry point for all client requests via a **RESTful API**. It manages API routing using the **FastAPI** framework, parses incoming JSON data, and returns the final HTTP response.
*   **Key Modules**: `auth_routes.py`, `interview_routes.py`, `resume_routes.py`, `job_routes.py`, `admin_routes.py`.

#### Layer 2: Application/Business Layer
*   **Location**: `backend/services/`
*   **Brief Explanation**: This layer contains the core logic of the application. It coordinates the execution of complex tasks like resume parsing (using PDF/DOCX libraries), generating AI feedback (via Mistral AI), and managing the RAG knowledge retrieval process.
*   **Key Modules**: `AI Feedback Service`, `Interview Engine`, `RAG Engine` (LlamaIndex), `Email Service`.

#### Layer 3: Data Access Layer
*   **Location**: `backend/core/` and `backend/models/`
*   **Brief Explanation**: This layer acts as the bridge to the infrastructure layer. It uses the **Motor (Async MongoDB Driver)** to communicate with the database while using **Pydantic Schemas** for data validation and structure.
*   **Key Components**: Pydantic Models, MongoDB Connection Setup, Security & JWT Utilities.

#### Layer 4: Infrastructure Layer
*   **Location**: Server Environment, MongoDB Atlas (Cloud), and External APIs.
*   **Brief Explanation**: This layer manages all external dependencies, persistence, and the server runtime environment.
*   **Key Components**: 
    - **Server Runtime**: **Nginx** (Reverse Proxy) and **Uvicorn** (ASGI Server).
    - **Database**: MongoDB Atlas (Collections: `users`, `resumes`, `interviews`, `audit_logs`, `pending_users`, `usage`).
    - **External Integrations**: Mistral AI (AI Intelligence), EmailJS (Communication).

---

### **Conclusion**

By nesting the **4-Layer Architecture** inside the **Server Tier** of the overall **Two-Tier** model, the project achieves a high degree of organization. This structure allows each layer and tier to be maintained, scaled, or updated independently without affecting the rest of the system.
