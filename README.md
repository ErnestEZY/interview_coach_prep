# ICP - Interview Coach Prep 🚀

ICP is an AI-powered career preparation platform designed to help job seekers master their interview skills and optimize their professional profiles. By combining advanced AI analysis with real-world job data, ICP provides a comprehensive ecosystem for career advancement.

## 🌟 Key Features 

### 1. AI Resume Analysis
*   **Intelligent Scoring**: Get a 0-100 score based on industry standards.
*   **Semantic Validation**: Ensures only valid professional resumes are processed.
*   **Structured Feedback**: Detailed breakdown of Advantages, Disadvantages, and actionable Suggestions.
*   **Keyword Extraction**: Automatically identifies 10-15 essential skills from your text.
*   **PDF Reports**: Export your analysis results into a professional PDF report.

### 2. Mock Interview Simulator
*   **Dynamic Questions**: AI generates role-specific technical and behavioral questions.
*   **Adaptive Difficulty**: Choose between Beginner, Intermediate, and Advanced levels.
*   **Voice Integration**: Practice using your microphone with AI-powered speech-to-text and text-to-speech.
*   **Readiness Scoring**: Receive an "Interview Readiness Score" and detailed performance feedback after each session.

### 3. Smart Job Search
*   **Tailored Results**: Job recommendations based on your AI-detected skills and job title.
*   **Careerjet Integration**: Access thousands of real-time job listings directly through the dashboard.
*   **Location Awareness**: Automatically detects your preferred work location from your resume.

### 4. Admin Portal
*   **User Management**: Monitor platform usage and manage user accounts.
*   **File Oversight**: View and manage uploaded resumes and interview histories.
*   **Audit Logs**: Detailed tracking of system activities for security and maintenance.

## 🛠️ Tech Stack

*   **Frontend**: HTML5, CSS3 (Bootstrap 5), JavaScript (Alpine.js, HTMX).
*   **Backend**: Python (FastAPI), MongoDB (Motor).
*   **AI Engine**: Mistral AI (Large-latest model), RAG (Retrieval-Augmented Generation) for specialized scoring guidelines.
*   **Security**: JWT Authentication, Rate Limiting, and Semantic File Validation.
*   **Infrastructure**: Docker, Render-ready deployment.

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   MongoDB
*   Mistral AI API Key

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ErnestEZY/interview_coach_prep.git
   cd interview_coach_prep
   ```

2. **Set up environment variables**:
   Create a `.env` file in the root directory based on `.env.example`:
   ```env
   MISTRAL_API_KEY=your_key_here
   MONGO_URI=your_mongodb_uri
   JWT_SECRET=your_secret_key
   ```

3. **Install dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Run the application**:
   ```bash
   python backend/main.py
   ```
   The backend will start on `http://localhost:8000`.

## 📱 Mobile App
The project includes a cross-platform mobile application built with **Flutter**, located in the `mobile_app/` directory.

## 💻 Desktop App
The project now includes a native desktop application built with **Tauri**, located in the `src-tauri/` directory. It leverages the existing web frontend to provide a fast and secure desktop experience. See [DESKTOP_APP.md](DESKTOP_APP.md) for setup instructions.

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.

---
*Built with ❤️ for better career preparation.*
