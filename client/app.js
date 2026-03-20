let ws = null;
let currentGameId = null;

async function startGame() {
    try {
        const res = await fetch("/create", { method: "POST" });
        const data = await res.json();

        const gameId = data.game_id;
        currentGameId = gameId;
        console.log("Game ID:", gameId);

        document.getElementById("status").innerText =
            "Game ID: " + gameId;

        connect(gameId);

    } catch (err) {
        console.error(err);
        document.getElementById("status").innerText =
            "Error creating game";
    }
}

function connect(gameId) {
    ws = new WebSocket(`ws://${window.location.host}/ws/${gameId}`);

    ws.onopen = () => {
        document.getElementById("status").innerText += " | Connected";
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("Received:", data);

        if (data.type === "waiting") {
            document.getElementById("status").innerText =
                "Game ID: " + currentGameId + " | Waiting for second player...";
        }

        if (data.type === "error") {
            alert(data.message);
        }

        if (data.type === "start") {
            document.getElementById("status").innerText = "Game Started!";
            document.getElementById("difficulty").innerText =
                "Difficulty: " + data.difficulty;

            renderBoard(data.board);
        }

        if (data.type === "update") {
            renderBoard(data.your_board);

            document.getElementById("scores").innerText =
                "Scores: " + JSON.stringify(data.scores);
        }

        if (data.time_left !== undefined) {
            document.getElementById("timer").innerText =
                "Time Left: " + data.time_left + "s";
        }

        if (data.game_over) {
            alert("Winner: " + data.winner);
         document.querySelectorAll("input").forEach(i => i.disabled = true);
        }
    };

    ws.onerror = () => {
        document.getElementById("status").innerText =
            "Connection error";
    };
}

function joinGame() {
    const id = document.getElementById("gameIdInput").value;
    connect(id);
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

            if (board[i][j] !== 0) {
                input.disabled = true;
            }

            input.oninput = () => {
                const val = parseInt(input.value);

                if (isNaN(val) || val < 1 || val > 9) {
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

// start automatically
startGame();