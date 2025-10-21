
# Robin: Your Voice-First Workspace Agent

<p align="center">
  <img src="https://raw.githubusercontent.com/your-username/your-repo/main/path/to/your/image.jpg" alt="Robin Architecture Diagram" width="750"/>
</p>

Robin is a voice-first assistant that helps you manage your digital workspace using natural language. With support for tools like Gmail, Google Calendar, and Slack, Robin enables productivity through simple voice commands—no typing required.

This monorepo contains:

- A **React Native frontend** for capturing voice and playing responses.
- A **FastAPI backend** that processes speech, connects to services, and returns intelligent responses using Amazon Bedrock.

---

## Table of Contents

1. [How It Works](#1-how-it-works)  
2. [Repository Structure](#2-repository-structure)  
3. [Backend Setup (Required First)](#3-backend-setup-required-first)  
4. [Frontend Setup](#4-frontend-setup)  
5. [Connecting the Frontend to the Backend](#5-connecting-the-frontend-to-the-backend)

---

## 1. How It Works

1. The **frontend** app records your voice and streams it to the backend over WebSocket.
2. The **backend** transcribes, interprets, and routes the request via Amazon Bedrock and AgentCore connectors.
3. If an action is needed (e.g., check calendar), it performs it using the user's credentials.
4. The backend generates a spoken response and streams audio back to the app, which plays it aloud.

---

## 2. Repository Structure

```bash
Robin/
├── backend/        # FastAPI server, Bedrock integration, WebSocket audio handling
├── frontend/       # React Native app for iOS/Android
├── README.md       # You're here!
└── ...
````

---

## 3. Backend Setup (Required First)

> ✅ **The backend must be running before the frontend can function.**

### Requirements

* Python 3.12+
* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) (configured with credentials)
* [Docker](https://www.docker.com/products/docker-desktop) (optional, but helpful)

### Installation

1. **Navigate to the backend directory:**

   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Edit the .env file with your credentials
   ```

   You'll need:

   * AWS access keys
   * AgentCore config (if applicable)
   * Any 3rd-party tool tokens (Google, Slack, etc.)

### Running the Backend

Start the API server:

```bash
python run.py
```

Once running, the backend will be accessible at:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 4. Frontend Setup

This React Native app records microphone input and streams audio to the backend.

### Requirements

* Node.js (LTS)
* [Expo CLI](https://docs.expo.dev/get-started/installation/)
* iOS or Android simulator/emulator — or real device

### Steps

1. **Navigate to the frontend folder:**

   ```bash
   cd frontend
   ```

2. **Install dependencies:**

   ```bash
   npm install
   ```

3. **Configure environment variables:**

   Create `.env` file (or use `app.config.js` depending on setup):

   ```env
   BACKEND_URL=http://localhost:8000
   ```

4. **Run the app:**

   * iOS:

     ```bash
     npm run ios
     ```
   * Android:

     ```bash
     npm run android
     ```

   You may need a physical device or emulator with microphone support.

---

## 5. Connecting the Frontend to the Backend

Robin uses a WebSocket connection for streaming audio and responses.

### Step 1: Start a New Session

Make a `POST` request to initialize a voice session:

```ts
const response = await fetch('http://localhost:8000/api/sessions/start', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ userId: 'user-123' })  // Optional user ID
});

const session = await response.json();
// Response: { session_id, websocket_url }
```

### Step 2: Connect via WebSocket

Use the provided WebSocket URL to start streaming audio:

```ts
const ws = new WebSocket(session.websocket_url);

ws.onopen = () => {
  console.log('Connected to WebSocket!');
  // Start sending PCM audio chunks
};

ws.onmessage = (event) => {
  // event.data contains audio response from backend (e.g. MP3 or PCM)
  // Play audio using your audio playback module
};

ws.onerror = (err) => {
  console.error('WebSocket error:', err);
};
```

### Audio Streaming Format

* **Outbound**: PCM audio (16-bit, mono)
* **Inbound**: Audio stream (usually MP3 or WAV)

React Native app should have:

* Permissions to access microphone
* A method for capturing real-time audio and sending it in chunks
* Playback functionality for the returned audio


