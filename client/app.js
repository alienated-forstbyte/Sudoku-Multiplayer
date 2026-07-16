let ws = null;
let currentGameId = null;

let timeLeft = 0;
let timerInterval = null;

function setStatus(text) {
    document.getElementById("status").innerText = text;
}

function setMoveFeedback(message, success) {
    const el = document.getElementById("moveFeedback");
    if (!el) {
        return;
    }
    el.innerText = message || "";
    el.style.color = success === false ? "#b00020" : "#0b6b0b";
}

async function startGame() {
    try {
        const res = await fetch("/create", { method: "POST" });
        const data = await res.json();

        currentGameId = data.game_id;

        setStatus("Game ID: " + currentGameId);
        setMoveFeedback("", true);
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
            setStatus("Game ID: " + currentGameId + " | Waiting...");
        }

        if (data.type === "error") {
            setMoveFeedback(data.message, false);
            setStatus("Game ID: " + currentGameId + " | " + data.message);
            alert(data.message);
        }

        if (data.type === "start") {
            timeLeft = data.time_left;
            startTimer();

            setStatus("Game ID: " + currentGameId + " | Started");
            setMoveFeedback("Game started — enter a digit in an empty cell", true);

            document.getElementById("difficulty").innerText =
                "Difficulty: " + data.difficulty;

            renderBoard(data.board);
        }

        if (data.type === "update") {
            timeLeft = Math.min(timeLeft, data.time_left);

            renderBoard(data.board);
            setMoveFeedback(data.message, data.success);

            document.getElementById("scores").innerText =
                "Scores: " + JSON.stringify(data.scores);
        }

        if (data.type === "game_over" || data.game_over) {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
            const winnerText = "Winner: " + data.winner;
            setMoveFeedback(winnerText, true);
            alert(winnerText);
            document.querySelectorAll("input").forEach(i => i.disabled = true);
        }
    };

    ws.onerror = () => {
        setStatus("Connection error");
    };

    ws.onclose = () => {
        setStatus("Game ID: " + (currentGameId || "?") + " | Disconnected");
    };
}

function joinGame() {
    const id = document.getElementById("gameIdInput").value.trim();

    currentGameId = id;

    setStatus("Game ID: " + currentGameId);
    setMoveFeedback("", true);

    connect(id);
}

function startTimer() {
    if (timerInterval) clearInterval(timerInterval);

    timerInterval = setInterval(() => {
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            timerInterval = null;
            document.getElementById("timer").innerText = "Time Up!";
            return;
        }

        document.getElementById("timer").innerText =
            "Time Left: " + timeLeft + "s";

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
