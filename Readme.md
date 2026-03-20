A **real-time multiplayer Sudoku platform** featuring:

- 🎮 Competitive gameplay over WebSockets  
- 🤖 ML-powered difficulty classification  
- 🐳 Fully containerized deployment (Docker)  
- ⚙️ Scalable backend architecture  

This project demonstrates **end-to-end MLOps integration inside a distributed system**.

---

## 🧠 Key Highlights

- Built a **real-time multiplayer system** using FastAPI + WebSockets  
- Designed an ML model (**96% accuracy**) for Sudoku difficulty prediction  
- Engineered features based on **constraint density & candidate complexity**  
- Integrated ML inference directly into backend game logic  
- Containerized the system using Docker for reproducibility  

---

## 🎮 Features

### 🔴 Real-Time Multiplayer
- Simultaneous gameplay (no turn system)
- Independent boards per player
- Server-authoritative validation
- Game rooms with unique IDs

---

### 🧠 Sudoku Engine
- Backtracking-based puzzle generator
- Solver for correctness validation
- Dynamic puzzle generation per player

---

### 🤖 ML Difficulty Prediction
- RandomForest model trained on engineered features
- Features include:
  - Constraint variance
  - Candidate complexity
  - Density metrics
- Real-time difficulty prediction during gameplay

---

### ⏱ Game Mechanics
- 10-minute timer per game
- Score-based competition
- Instant win on completion
- Timeout → highest score wins

---

### 🐳 Dockerized Deployment
- One-command startup using Docker Compose
- Fully reproducible environment
- Ready for scaling

---

## 🏗️ System Architecture


Client (WebSocket) 
```
↓
FastAPI Server (Game Engine)
↓
ML Model (Difficulty Prediction)
↓
Game State Manager
```

---

## ⚙️ How It Works

1. Player joins a game room  
2. Server generates Sudoku puzzle  
3. ML model predicts difficulty  
4. Players solve independently in real-time  
5. Scores update dynamically  
6. Winner determined by completion or timer  

---

## 🧪 Demo

```bash
# Create game
curl -X POST http://localhost:8000/create

# Connect player
websocat ws://localhost:8000/ws/<game_id>

```
## 🧱 Project Structure
```
sudoku/
│
├── engine/        # Sudoku generator & solver
├── server/        # FastAPI + game manager
├── ml/            # Dataset, features, training, inference
├── tests/         # Unit tests
├── Dockerfile
├── docker-compose.yml
└── README.md
```
## ⚙️ Tech Stack

Backend: FastAPI, WebSockets

ML: Scikit-learn (RandomForest)

Data: Custom feature engineering pipeline

Deployment: Docker, Docker Compose

Language: Python