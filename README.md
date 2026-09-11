# 🤖 NexusAI

**NexusAI** is a modern AI chatbot and question-answering web application designed to provide intelligent, conversational responses to user queries.

The application supports multiple AI providers, allowing users to interact with different AI models through a single chatbot interface.

---

## ✨ Features

* 🤖 AI-powered chatbot
* 💬 Question & Answer (Q&A) system
* 🧠 Intelligent conversational responses
* 🔄 Multiple AI model/provider support
* ⚡ Fast and responsive chat interface
* 👤 User authentication
* 📧 OTP-based email verification
* 🔐 Password reset functionality
* 🖼️ AI image generation support
* 💾 Chat history support
* 📱 Responsive web interface
* 🚨 Provider-specific error handling

---

## 🧠 AI Providers

NexusAI integrates multiple AI providers:

### Google Gemini

Used for generating AI responses through the Gemini API.

### Groq

Used for fast AI inference and conversational responses.

### OpenAI

Used for AI-powered responses through the OpenAI API.

The backend routes requests to the selected provider based on the model selected by the user.

---

## 🛠️ Tech Stack

### Frontend

* HTML5
* CSS3
* JavaScript
* Fetch API
* Responsive UI

### Backend

* Python
* FastAPI
* Pydantic
* Uvicorn
* REST APIs

### AI APIs

* Google Gemini API
* Groq API
* OpenAI API

### Other Services

* Google Sheets integration
* SMTP email service
* Hugging Face API for image generation

---

## 🏗️ Project Architecture

```text
                    ┌─────────────────────┐
                    │      NexusAI        │
                    │    Web Interface    │
                    └──────────┬──────────┘
                               │
                               │ HTTP Request
                               ▼
                    ┌─────────────────────┐
                    │    FastAPI Backend   │
                    │       Python        │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
                 ▼             ▼             ▼
             ┌────────┐    ┌────────┐    ┌────────┐
             │ Gemini │    │  Groq  │    │ OpenAI │
             │  API   │    │  API   │    │  API   │
             └────────┘    └────────┘    └────────┘
```

---

## 📁 Project Structure

```text
NexusAI/
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── backend/
│   ├── main.py
│   ├── .env
│   └── requirements.txt
│
└── README.md
```

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/NexusAI.git
cd NexusAI
```

---

## 🐍 Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate the virtual environment.

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🔑 Environment Variables

Create a `.env` file inside the backend directory.

```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_api_key
HF_API_KEY=your_huggingface_api_key

GOOGLE_SCRIPT_URL=your_google_script_url

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email
SMTP_PASSWORD=your_app_password

FRONTEND_URL=http://127.0.0.1:5500
ALLOWED_ORIGINS=*
```

> ⚠️ Never upload your `.env` file or API keys to GitHub.

Add this to `.gitignore`:

```gitignore
.env
venv/
__pycache__/
*.pyc
```

---

## ▶️ Run the Backend

Start the FastAPI server:

```bash
python main.py
```

The backend will run on:

```text
http://127.0.0.1:8000
```

FastAPI documentation will be available at:

```text
http://127.0.0.1:8000/docs
```

---

## 🌐 Run the Frontend

Open the frontend using a local web server.

For example:

```bash
python -m http.server 5500
```

Then open:

```text
http://127.0.0.1:5500
```

---

## 🔌 API Endpoints

### Authentication

| Method | Endpoint         | Description           |
| ------ | ---------------- | --------------------- |
| POST   | `/login`         | User login            |
| POST   | `/send-otp`      | Send registration OTP |
| POST   | `/resend-otp`    | Resend OTP            |
| POST   | `/verify-otp`    | Verify OTP            |
| POST   | `/save-password` | Save user password    |

### Password Management

| Method | Endpoint            | Description                |
| ------ | ------------------- | -------------------------- |
| POST   | `/forgot-password`  | Request password reset     |
| POST   | `/verify-reset-otp` | Verify reset OTP           |
| POST   | `/reset-password`   | Reset password             |
| POST   | `/reset-by-token`   | Reset password using token |
| POST   | `/change-password`  | Change password            |

### AI Chat

```text
POST /api/chat
```

Example request:

```json
{
  "message": "Explain binary search",
  "model": "gpt-5.6-luna",
  "history": [],
  "email": "user@example.com"
}
```

The backend determines which AI provider should handle the request based on the selected model.

---

## 🤖 Supported Models

```text
gemini-2.5-flash
qwen/qwen3.6-27b
gpt-5.6-luna
```

Model routing:

```text
gemini-2.5-flash → Google Gemini

qwen/qwen3.6-27b → Groq

gpt-5.6-luna → OpenAI
```

---

## 🔄 AI Request Flow

```text
User enters question
        ↓
Frontend sends request
        ↓
FastAPI /api/chat
        ↓
Selected model identified
        ↓
Provider selected
        ↓
AI API request
        ↓
AI generates response
        ↓
FastAPI returns response
        ↓
NexusAI displays answer
```

---

## 🖼️ AI Image Generation

NexusAI also supports AI image generation through an external image-generation API.

Endpoint:

```text
POST /generate-image
```

Example:

```json
{
  "prompt": "A futuristic AI robot working in a modern office"
}
```

---

## 🔐 Security

NexusAI keeps API credentials on the backend rather than exposing them directly in frontend JavaScript.

Important security practices:

* Never expose API keys in frontend code.
* Never commit `.env` to GitHub.
* Use environment variables for secrets.
* Configure CORS appropriately for production.
* Use HTTPS when deploying the production application.
* Use secure authentication and password handling in production.

---

## 🎯 Project Goal

The main goal of NexusAI is to create a unified AI chatbot platform where users can ask questions and receive intelligent responses from multiple AI providers through a simple and modern interface.

Instead of building separate interfaces for different AI services, NexusAI provides a single platform for interacting with multiple AI models.

---

## 🚀 Future Improvements

Planned improvements may include:

* Streaming AI responses
* More AI models
* Voice input
* Voice responses
* Advanced chat history
* File/PDF analysis
* Code execution
* AI-powered coding assistant
* Conversation sharing
* User dashboard
* Usage analytics
* Production database
* Rate limiting
* Advanced security
* Cloud deployment

---

## 📸 Screenshots

Add screenshots of your NexusAI interface here:

```text
screenshots/
├── home.png
├── chat.png
├── login.png
└── model-selection.png
```

Example:

```markdown
![NexusAI Chat Interface](screenshots/chat.png)
```

---

## 👨‍💻 Author

**NexusAI**

Built as an AI chatbot project using modern web technologies, FastAPI, Python, and multiple AI APIs.

---

## 📄 License

This project is available for educational and development purposes.

---

⭐ If you find NexusAI useful, consider giving the project a star on GitHub.
