# ICP - Interview Coach Prep 🚀

ICP is an AI-powered career preparation platform designed to help job seekers master their interview skills and optimize their professional profiles. By combining advanced AI analysis with real-world job data, ICP provides a comprehensive ecosystem for career advancement.

## 🌟 Key Features 

### 1. AI Resume Analysis & Builder
*   **Intelligent Scoring**: Get a 0-100 score based on industry standards.
*   **Resume Builder**: Dynamic form with auto-expanding fields (Professional Summary, Achievements, Skills) for easy editing.
*   **Semantic Validation**: Ensures only valid professional resumes are processed.
*   **Structured Feedback**: Detailed breakdown of Advantages, Disadvantages, and actionable Suggestions.
*   **Keyword Extraction**: Automatically identifies 10-15 essential skills from your text.
*   **PDF Reports**: Export your analysis results into a professional PDF report.

### 2. Mock Interview Simulator
*   **Dynamic Questions**: AI generates role-specific technical and behavioral questions.
*   **Adaptive Difficulty**: Choose between Beginner, Intermediate, and Advanced levels.
*   **Voice Integration**: Practice using your microphone with AI-powered speech-to-text (STT) and text-to-speech (TTS).
*   **Real-time Interaction**: Seamless conversation flow with AI interviewers.
*   **Readiness Scoring**: Receive an "Interview Readiness Score" and detailed performance feedback after each session.

### 3. Smart Job Search
*   **Tailored Results**: Job recommendations based on your AI-detected skills and job title.
*   **Careerjet Integration**: Access thousands of real-time job listings directly through the dashboard.
*   **Location Awareness**: Automatically detects your preferred work location from your resume for localized searching.

### 4. Advanced Admin Portal
*   **Dashboard Analytics**: Monitor platform usage, user activity, and system health.
*   **User Management**: Full control over user accounts and platform access.
*   **File & History Oversight**: View and manage uploaded resumes and interview histories with integrated previews.
*   **Clean UI**: Modern, responsive administrative interface with advanced filtering and pagination.

## 🛠️ Tech Stack

*   **Frontend**: HTML5, CSS3 (Bootstrap 5), JavaScript (Vue.js 3, Axios).
*   **Backend**: Python (FastAPI), MongoDB (Motor).
*   **AI Framework**: **LlamaIndex** for advanced RAG (Retrieval-Augmented Generation) processing.
*   **AI Engine**: Mistral AI (Large-latest model) for intelligent analysis and generation.
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
   Create a `.env` file in the root directory:
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

## 📱 Mobile & Desktop Apps

*   **Mobile App**: A cross-platform mobile application built with **Flutter**, located in the `mobile_app/` directory.
*   **Desktop App**: A native desktop application built with **Tauri**, located in the `src-tauri/` directory. See [DESKTOP_APP.md](DESKTOP_APP.md) for setup instructions.

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.

---
*Built with ❤️ for better career preparation.*
