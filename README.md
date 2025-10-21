# Robin: Your Voice-First Workspace Agent

This repository holds the code for **Robin**, a voice assistant that helps you manage your digital workspace. It includes both the mobile app and the backend server.

The goal of this project is to create a simple, voice-driven way to interact with tools like Gmail, Google Calendar, and Slack without needing to type or click.

## Repository Structure

This project is a monorepo containing two main parts:

-   **/frontend**: A mobile application built with React Native. This is what you'll install on your phone.
    -   *See the [frontend/README.md](frontend/README.md) for setup and build instructions.*

-   **/backend**: A Python server built with FastAPI. This server handles the voice processing, AI logic, and connections to your tools.
    -   *See the [backend/README.md](backend/README.md) for setup and deployment instructions.*

## How It Works

1.  The **frontend** app listens for your voice and streams it to the backend.
2.  The **backend** server sends the audio to Amazon Bedrock to understand what you said.
3.  If you ask to do something (like "check my calendar"), the backend securely connects to your tools.
4.  The backend then tells Amazon Bedrock to generate a spoken response and streams the audio back to the frontend app, which plays it for you.

## Getting Started

To run the full application, you need to set up both the frontend and backend. Please follow the instructions in each of their respective `README.md` files.

---

### **3. Backend `README.md` (in the `backend/` folder)**

*(This is the `README.md` file for your `robin-backend` sub-directory)*

built by isaac okwuzi & his buddy stan
