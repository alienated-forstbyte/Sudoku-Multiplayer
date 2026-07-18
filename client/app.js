let ws = null;
let currentGameId = null;

let timeLeft = 0;
let timerInterval = null;
let gameActive = false;

function setStatus(text) {
    document.getElementById("status").innerText = text;
}

function setMoveFeedback(message, success) {
    const el = document.getElementById("moveFeedback");
    if (!el) return;
    el.innerText = message || "";
    el.className = success === false ? "feedback-error" : success === true ? "feedback-success" : "";
}

function showGameOver(data) {
    gameActive = false;
    stopTimer();

    document.querySelectorAll("#board input").forEach(i => i.disabled = true);

    const overlay = document.getElementById("gameOverlay");
    const msg = document.getElementById("overlayMessage");

    if (data.reason === "room_expired") {
        msg.innerText = "Room expired — no second player joined in time.";
    } else if (data.reason === "time_up") {
        if (data.winner === null || data.winner === undefined) {
            msg.innerText = "Time's up! Draw.";
        } else if (data.winner === "draw") {
            msg.innerText = "Time's up! It's a draw.";
        } else {
            msg.innerText = "Time's up! Player " + data.winner + " wins!";
        }
    } else if (data.reason === "board_complete") {
        if (data.winner === "draw") {
            msg.innerText = "Board completed! It's a draw.";
        } else {
            msg.innerText = "Board completed! Player " + data.winner + " wins!";
        }
    } else {
        const text = data.message || ("Game over. Winner: " + data.winner);
        msg.innerText = text;
    }

    overlay.classList.add("visible");
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

async function startGame() {
    try {
        const res = await fetch("/create", { method: "POST" });
        const data = await res.json();

        currentGameId = data.game_id;

        document.getElementById("gameIdInput").value = currentGameId;
        setStatus("Game ID: " + currentGameId + " | Creating...");
        setMoveFeedback("", null);
        connect(currentGameId);

    } catch (err) {
        console.error(err);
        setStatus("Error creating game");
    }
}

function connect(gameId) {
    ws = new WebSocket(`ws://${window.location.host}/ws/${gameId}`);

    ws.onopen = () => {
        setStatus("Game ID: " + currentGameId + " | Connected");
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "waiting") {
            setStatus("Game ID: " + currentGameId + " | Waiting for opponent...");
            setMoveFeedback("Share this Game ID with a friend to start playing.", null);
        }

        if (data.type === "error") {
            setMoveFeedback(data.message, false);
            if (data.message === "Room expired" || data.message === "Game not found") {
                showGameOver({ reason: "room_expired", message: data.message });
            }
        }

        if (data.type === "start") {
            gameActive = true;
            timeLeft = data.time_left;
            startTimer();

            document.getElementById("gameOverlay").classList.remove("visible");
            setStatus("Game ID: " + currentGameId + " | In Progress");
            setMoveFeedback("Game started — fill in the empty cells!", true);

            document.getElementById("difficulty").innerText =
                "Difficulty: " + data.difficulty;

            renderBoard(data.board);
        }

        if (data.type === "update") {
            timeLeft = Math.min(timeLeft, data.time_left);

            renderBoard(data.board);

            if (data.game_over) {
                showGameOver(data);
            } else {
                setMoveFeedback(data.message, data.success);
            }

            document.getElementById("scores").innerText =
                "Scores — You: " + (data.scores["0"] || 0) +
                "  |  Opponent: " + (data.scores["1"] || 0);
        }

        if (data.type === "game_over") {
            showGameOver(data);
        }
    };

    ws.onerror = () => {
        setStatus("Connection error");
    };

    ws.onclose = () => {
        if (gameActive) {
            setMoveFeedback("Disconnected from server.", false);
        }
        setStatus("Game ID: " + (currentGameId || "?") + " | Disconnected");
    };
}

function joinGame() {
    const id = document.getElementById("gameIdInput").value.trim();
    if (!id) {
        setMoveFeedback("Enter a Game ID first.", false);
        return;
    }

    currentGameId = id;
    document.getElementById("gameOverlay").classList.remove("visible");
    setStatus("Game ID: " + currentGameId + " | Connecting...");
    setMoveFeedback("", null);

    connect(id);
}

function startTimer() {
    stopTimer();

    const timerEl = document.getElementById("timer");
    timerEl.classList.remove("timer-warning");

    timerInterval = setInterval(() => {
        if (timeLeft <= 0) {
            stopTimer();
            timerEl.innerText = "Time's up!";
            timerEl.classList.add("timer-warning");
            return;
        }

        timerEl.innerText = "Time Left: " + timeLeft + "s";

        if (timeLeft <= 10) {
            timerEl.classList.add("timer-warning");
        }

        timeLeft--;
    }, 1000);
}

function renderBoard(board) {
    const table = document.getElementById("board");
    table.innerHTML = "";

    for (let i = 0; i < 9; i++) {
        const row = document.createElement("tr");

        for (let j = 0; j < 9; j++) {
            const cell = document.createElement("td");
            const input = document.createElement("input");

            input.value = board[i][j] || "";
            input.maxLength = 1;
            input.inputMode = "numeric";

            if (board[i][j] !== 0) {
                input.disabled = true;
            }

            input.oninput = () => {
                const val = parseInt(input.value, 10);

                if (isNaN(val) || val < 1 || val > 9) {
                    input.value = "";
                    return;
                }

                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    setMoveFeedback("Not connected", false);
                    return;
                }

                if (!gameActive) {
                    input.value = "";
                    return;
                }

                ws.send(JSON.stringify({
                    type: "move",
                    row: i,
                    col: j,
                    value: val
                }));
            };

            cell.appendChild(input);
            row.appendChild(cell);
        }

        table.appendChild(row);
    }
}
