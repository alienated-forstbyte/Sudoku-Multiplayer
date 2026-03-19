# 🧩 Multiplayer Sudoku with ML & Blockchain (MLOps Project)

## 📌 Overview
This project is a **containerized multiplayer Sudoku platform** designed to demonstrate concepts across:

- Backend systems (FastAPI, WebSockets)
- Distributed systems (real-time multiplayer sync)
- MLOps (upcoming: difficulty prediction model)
- Cryptography / Blockchain (upcoming: puzzle verification)

Players connect to a central server and solve the same Sudoku puzzle in a **turn-based, time-constrained competitive environment**.

---

## 🚀 Features (Current)

### 🎮 Multiplayer Gameplay
- Real-time multiplayer using WebSockets
- Game rooms with unique IDs
- Turn-based move system
- Server-authoritative validation

### 🧠 Sudoku Engine
- Algorithmic Sudoku generator (backtracking)
- Puzzle creation with difficulty presets
- Solver for validation

### ⚖️ Game Mechanics
- Strict move validation (checked against solution)
- Score tracking per player
- Turn enforcement

### ⏱ Timer System
- 10-minute time limit per game
- Server-side timer (anti-cheat)
- Game ends on:
  - Puzzle completion OR
  - Time expiration

### 🏆 Win Conditions
- First to complete board → wins
- If time expires → player with highest score wins
- Tie → draw

---

## 🧱 Project Structure

```
sudoku/
│
├── engine/
│ ├── solver.py
│ ├── generator.py
│ └── utils.py
│
├── server/
│ ├── main.py
│ ├── game_manager.py
│
├── tests/
│ └── test_engine.py
│
└── README.md
```

---

## ⚙️ Tech Stack

| Layer        | Technology |
|-------------|-----------|
| Backend     | FastAPI |
| Realtime    | WebSockets |
| Language    | Python 3.11 |
| Testing     | Pytest (basic) |
| Container   | Docker (planned) |
| ML (planned)| Scikit-learn / XGBoost |
| Blockchain (planned) | Custom ledger / Ethereum |

---

## ▶️ Running the Project

### 1. Install dependencies
```bash
pip install fastapi uvicorn websockets
```
2. Start the server
```
uvicorn server.main:app --reload
```
3. Create a game
```
curl -X POST http://127.0.0.1:8000/create
```
Response:
```
{
  "game_id": "your-game-id"
}
```
4. Connect players

Open two terminals:
```
websocat ws://127.0.0.1:8000/ws/<game_id>
```
5. Send a move
```
{
  "type": "move",
  "row": 0,
  "col": 1,
  "value": 5
}
```
### 🔄 Game Flow

- Player joins game

- Server assigns:

- player_id

- initial board

- Players alternate turns

- Server validates moves

- Scores update

- Game ends when:

- board is complete OR

- timer expires

### ⚠️ Current Limitations

- Puzzle may have multiple solutions

- Only "correct" moves allowed (strict mode)

- No UI (CLI/Web UI planned)

- Timer depends on client activity (no background scheduler yet)

## 🧠 Upcoming Features
### 🤖 Phase 3 — ML Integration

- Train model to predict puzzle difficulty

- Feature engineering from Sudoku structure

- Dataset generation pipeline

### ⛓️ Phase 4 — Blockchain Integration

- Store puzzle hash on blockchain

- Verify puzzle integrity

- Prevent tampering

### 🐳 Phase 5 — Dockerization

- Separate services:

- Game server

- ML service

- Blockchain service

- Docker Compose orchestration

## 💡 Learning Outcomes

This project demonstrates:

- Real-time distributed system design

- State synchronization across clients

- Server-authoritative architecture

- Game logic enforcement

-Foundations of MLOps pipelines

- Practical use of cryptographic verification (planned)

## 📌 Future Improvements

- GUI (React / Streamlit)

- Matchmaking system

- Spectator mode

- Leaderboards

- AI opponent (ML agent)

- Persistent storage (Redis/PostgreSQL)

