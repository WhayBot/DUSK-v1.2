/**
 * DUSK - Web Control Panel JavaScript
 * Handles mode switching, motor control, status polling, and camera feed.
 */

// ===== STATE =====
let currentMode = "manual";
let statusInterval = null;
const STATUS_POLL_MS = 1000;

// ===== API HELPERS =====
async function apiPost(endpoint, data) {
    try {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        return null;
    }
}

async function apiGet(endpoint) {
    try {
        const response = await fetch(endpoint);
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        return null;
    }
}

// ===== MODE CONTROL =====
async function setMode(mode) {
    const result = await apiPost("/api/mode", { mode: mode });
    if (result && result.success) {
        currentMode = mode;
        updateModeUI(mode);
    }
}

function updateModeUI(mode) {
    const btnManual = document.getElementById("btnManual");
    const btnAuto = document.getElementById("btnAuto");
    const controlsCard = document.getElementById("controlsCard");
    const cameraFeed = document.getElementById("cameraFeed");
    const cameraPlaceholder = document.getElementById("cameraPlaceholder");
    const cameraStatus = document.getElementById("cameraStatus");

    if (mode === "manual") {
        btnManual.classList.add("active");
        btnAuto.classList.remove("active");
        controlsCard.style.opacity = "1";
        controlsCard.style.pointerEvents = "auto";

        // Start camera feed
        cameraFeed.src = "/video_feed";
        cameraFeed.style.display = "block";
        cameraPlaceholder.style.display = "none";
        cameraStatus.textContent = "LIVE";
        cameraStatus.classList.add("active");
    } else {
        btnAuto.classList.add("active");
        btnManual.classList.remove("active");
        controlsCard.style.opacity = "0.5";
        controlsCard.style.pointerEvents = "none";

        // Stop camera feed
        cameraFeed.src = "";
        cameraFeed.style.display = "none";
        cameraPlaceholder.style.display = "flex";
        cameraStatus.textContent = "OFF";
        cameraStatus.classList.remove("active");
    }
}

// ===== DRIVE CONTROL =====
async function sendControl(command) {
    if (currentMode !== "manual") return;
    await apiPost("/api/control", { command: command });
}

// ===== VACUUM CONTROL =====
function updateVacuumSpeed(value) {
    document.getElementById("vacuumSpeedLabel").textContent = value + "%";
}

async function vacuumAction(action) {
    const speed = parseInt(document.getElementById("vacuumSlider").value);
    const result = await apiPost("/api/vacuum", { action: action, speed: speed });
    if (result && result.vacuum) {
        updateVacuumUI(result.vacuum);
    }
}

function updateVacuumUI(vacuumStatus) {
    const badge = document.getElementById("vacuumStatus");
    if (vacuumStatus.running) {
        badge.textContent = `${vacuumStatus.speed}%`;
        badge.classList.add("active");
    } else {
        badge.textContent = "OFF";
        badge.classList.remove("active");
    }
}

// ===== SWEEPER CONTROL =====
async function toggleSweeper() {
    const result = await apiPost("/api/sweeper", { action: "toggle" });
    if (result && result.sweeper) {
        updateSweeperUI(result.sweeper);
    }
}

function updateSweeperUI(sweeperStatus) {
    const badge = document.getElementById("sweeperStatus");
    const btn = document.getElementById("btnSweeperToggle");
    if (sweeperStatus.running) {
        badge.textContent = "ON";
        badge.classList.add("active");
        btn.classList.add("active");
    } else {
        badge.textContent = "OFF";
        badge.classList.remove("active");
        btn.classList.remove("active");
    }
}

// ===== STATUS POLLING =====
async function pollStatus() {
    const status = await apiGet("/api/status");
    if (!status || status.error) {
        setConnectionStatus(false);
        return;
    }

    setConnectionStatus(true);

    // Update battery
    if (status.battery) {
        const pct = status.battery.percentage;
        document.getElementById("batteryPercent").textContent = pct + "%";
        document.getElementById("batteryVoltage").textContent = status.battery.voltage + "V";
        document.getElementById("batteryCurrent").textContent = status.battery.current + "A";

        const levelEl = document.getElementById("batteryLevel");
        levelEl.style.width = pct + "%";
        levelEl.classList.remove("low", "critical");
        if (status.battery.critical) {
            levelEl.classList.add("critical");
        } else if (status.battery.low_battery) {
            levelEl.classList.add("low");
        }
    }

    // Update sensors
    if (status.distances) {
        document.getElementById("tofLeft").textContent = status.distances.left_mm + " mm";
        document.getElementById("tofRight").textContent = status.distances.right_mm + " mm";
    }

    if (status.imu) {
        document.getElementById("heading").textContent = status.imu.heading + "°";
    }

    if (status.navigation) {
        document.getElementById("navState").textContent = status.navigation.state || "IDLE";
    }

    if (status.encoders && status.encoders.speeds) {
        document.getElementById("speedLeft").textContent =
            Math.round(status.encoders.speeds.left) + " mm/s";
        document.getElementById("speedRight").textContent =
            Math.round(status.encoders.speeds.right) + " mm/s";
    }

    // Update vacuum & sweeper status
    if (status.vacuum) updateVacuumUI(status.vacuum);
    if (status.sweeper) updateSweeperUI(status.sweeper);

    // Update mode
    if (status.mode && status.mode !== currentMode) {
        currentMode = status.mode;
        updateModeUI(status.mode);
    }
}

function setConnectionStatus(connected) {
    const dot = document.getElementById("connectionDot");
    const text = document.getElementById("connectionText");
    if (connected) {
        dot.classList.add("connected");
        text.textContent = "Connected";
    } else {
        dot.classList.remove("connected");
        text.textContent = "Disconnected";
    }
}

// ===== KEYBOARD CONTROLS =====
document.addEventListener("keydown", function (e) {
    if (currentMode !== "manual") return;
    
    const keyMap = {
        ArrowUp: "forward",
        w: "forward",
        W: "forward",
        ArrowDown: "backward",
        s: "backward",
        S: "backward",
        ArrowLeft: "left",
        a: "left",
        A: "left",
        ArrowRight: "right",
        d: "right",
        D: "right",
    };

    const command = keyMap[e.key];
    if (command) {
        e.preventDefault();
        sendControl(command);

        // Visual feedback on D-pad
        const btnMap = {
            forward: "btnForward",
            backward: "btnBackward",
            left: "btnLeft",
            right: "btnRight",
        };
        const btnId = btnMap[command];
        if (btnId) {
            document.getElementById(btnId).classList.add("active");
        }
    }
});

document.addEventListener("keyup", function (e) {
    if (currentMode !== "manual") return;

    const movementKeys = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", 
                           "w", "W", "a", "A", "s", "S", "d", "D"];
    if (movementKeys.includes(e.key)) {
        e.preventDefault();
        sendControl("stop");

        // Remove visual feedback
        ["btnForward", "btnBackward", "btnLeft", "btnRight"].forEach(function (id) {
            document.getElementById(id).classList.remove("active");
        });
    }
});

// ===== TOUCH EVENTS (prevent default for D-pad) =====
document.querySelectorAll(".dpad-btn").forEach(function (btn) {
    btn.addEventListener("touchstart", function (e) {
        e.preventDefault();
    });
    btn.addEventListener("touchend", function (e) {
        e.preventDefault();
    });
});

// ===== INITIALIZATION =====
document.addEventListener("DOMContentLoaded", function () {
    // Start status polling
    statusInterval = setInterval(pollStatus, STATUS_POLL_MS);
    pollStatus();

    // Set initial mode UI
    updateModeUI(currentMode);
});
