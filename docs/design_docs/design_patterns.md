# Software Design Patterns Used (GoF 23)

Based on the current implementation of the project, three main categories of Gang of Four (GoF) design patterns have been utilized to ensure the system is maintainable, scalable, and secure.

---

### **1. Creational Pattern: Singleton Pattern**
*   **Location**: `backend/core/db.py` (MongoDB Client)
*   **Description**: The Singleton pattern ensures that a class has only one instance and provides a global point of access to it.
*   **Application**: In this project, the **AsyncIOMotorClient** is initialized once and shared across all backend controllers. This prevents the system from opening thousands of unnecessary database connections, which would lead to memory leaks and connection timeouts.

---

### **2. Structural Pattern: Facade Pattern**
*   **Location**: `backend/services/email_service.py`
*   **Description**: The Facade pattern provides a simplified interface to a larger body of code or a complex underlying subsystem (like an external API).
*   **Application**: Instead of requiring every controller (Auth, Admin, etc.) to handle HTTP headers, template IDs, and API payloads for **EmailJS**, the `email_service.py` acts as a **Facade**. It exposes simple functions like `send_admin_alert()` and `send_reset_password_email()`, hiding the complexity of the REST API calls from the rest of the application.

---

### **3. Behavioral Pattern: Template Method Pattern**
*   **Location**: `backend/services/rag_engine.py` (RAG Retrieval)
*   **Description**: The Template Method pattern defines the skeleton of an algorithm in an operation, deferring some steps to sub-operations while keeping the overall structure fixed.
*   **Application**: The **RAG Engine** follows a strict, step-by-step template for retrieving career coaching knowledge:
    1.  **Initialize**: Load documents and set up settings.
    2.  **Vector Search**: Find initial candidates from the database.
    3.  **Rerank**: Use Mistral AI to re-sort candidates for the highest relevance.
    4.  **Return**: Provide the final context to the AI Feedback service.
    This fixed sequence ensures that the AI always receives the most accurate information in a consistent manner.
