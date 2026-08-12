/* ==========================================================================
   Figma 1:1 Pixel-Perfect JS Controller with Native keydown Capture
   ========================================================================== */

// ── VK 码与名称的相互对照字典 ─────────────────────────────────────────────
const JS_CODE_TO_VK = {
    "KeyA": 0x41, "KeyB": 0x42, "KeyC": 0x43, "KeyD": 0x44, "KeyE": 0x45, "KeyF": 0x46, "KeyG": 0x47, "KeyH": 0x48,
    "KeyI": 0x49, "KeyJ": 0x4A, "KeyK": 0x4B, "KeyL": 0x4C, "KeyM": 0x4D, "KeyN": 0x4E, "KeyO": 0x4F, "KeyP": 0x50,
    "KeyQ": 0x51, "KeyR": 0x52, "KeyS": 0x53, "KeyT": 0x54, "KeyU": 0x55, "KeyV": 0x56, "KeyW": 0x57, "KeyX": 0x58,
    "KeyY": 0x59, "KeyZ": 0x5A,
    "Digit0": 0x30, "Digit1": 0x31, "Digit2": 0x32, "Digit3": 0x33, "Digit4": 0x34, "Digit5": 0x35, "Digit6": 0x36,
    "Digit7": 0x37, "Digit8": 0x38, "Digit9": 0x39,
    "Backspace": 0x08, "Tab": 0x09, "Enter": 0x0D, "Escape": 0x1B, "Space": 0x20,
    "PageUp": 0x21, "PageDown": 0x22, "End": 0x23, "Home": 0x24,
    "ArrowLeft": 0x25, "ArrowUp": 0x26, "ArrowRight": 0x27, "ArrowDown": 0x28,
    "Insert": 0x2D, "Delete": 0x2E,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "F13": 0x7C, "F14": 0x7D, "F15": 0x7E, "F16": 0x7F, "F17": 0x80, "F18": 0x81, "F19": 0x82, "F20": 0x83,
    "F21": 0x84, "F22": 0x85, "F23": 0x86, "F24": 0x87,
    "Semicolon": 0xBA, "Comma": 0xBC, "Period": 0xBE, "Slash": 0xBF,
    "Minus": 0xBD, "Equal": 0xBB, "BracketLeft": 0xDB, "BracketRight": 0xDD,
    "Backslash": 0xDC, "Quote": 0xDE, "Backquote": 0xC0,
    "ScrollLock": 0x91, "NumLock": 0x90, "Pause": 0x13
};

const VK_TO_NAME = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x1B: "ESC", 0x20: "Space",
    0x21: "PageUp", 0x22: "PageDown", 0x23: "End", 0x24: "Home",
    0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2D: "INS", 0x2E: "Delete",
    0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4", 0x74: "F5", 0x75: "F6",
    0x76: "F7", 0x77: "F8", 0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
    0x7C: "F13", 0x7D: "F14", 0x7E: "F15", 0x7F: "F16", 0x80: "F17", 0x81: "F18",
    0x82: "F19", 0x83: "F20", 0x84: "F21", 0x85: "F22", 0x86: "F23", 0x87: "F24",
    0xBA: ";", 0xBC: ",", 0xBE: ".", 0xBF: "/", 0xBD: "-", 0xBB: "=",
    0xDB: "[", 0xDD: "]", 0xDC: "\\", 0xDE: "'", 0xC0: "`",
    0x91: "SCROLL", 0x90: "NumLock", 0x13: "Pause"
};

// ── 全局状态变量 ─────────────────────────────────────────────────────────
let currentConfigs = [
    { vk: 0, mod: 0 },
    { vk: 0, mod: 0 },
    { vk: 0, mod: 0 },
    { vk: 0, mod: 0 }
];
let selectedOtaPath = "";
let isConnected = false;
let capturingIdx = -1;

// ── 初始化事件绑定 ───────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // 监听连接按钮
    document.getElementById("btn-connect").addEventListener("click", onConnectClick);
    
    // 监听检查更新按钮
    document.getElementById("btn-check-update").addEventListener("click", () => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.check_update();
        }
    });

    // 拖拽文件 OTA 绑定
    const dropzone = document.getElementById("dropzone");
    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });
    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.name.endsWith(".bin")) {
                selectedOtaPath = file.path || file.name; // pywebview 拖拽可拿到绝对路径
                updateOtaSelectedFile(file.name);
            }
        }
    });
    
    // 定时轮询串口（每3秒）
    setInterval(pollPorts, 3000);
});

// ── 串口列表轮询 ─────────────────────────────────────────────────────────
async function pollPorts() {
    if (window.pywebview && window.pywebview.api) {
        const ports = await window.pywebview.api.get_ports();
        updatePorts(ports);
    }
}

function updatePorts(ports) {
    const select = document.getElementById("port-select");
    const currentVal = select.value;
    
    select.innerHTML = "";
    if (!ports || ports.length === 0) {
        select.innerHTML = '<option value="">No Devices</option>';
        return;
    }
    
    ports.forEach(port => {
        const opt = document.createElement("option");
        opt.value = port;
        opt.textContent = port.replace("/dev/cu.", "");
        select.appendChild(opt);
    });
    
    if (ports.includes(currentVal)) {
        select.value = currentVal;
    }
}

// ── 串口连接与断开 ───────────────────────────────────────────────────────
async function onConnectClick() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    const btn = document.getElementById("btn-connect");
    if (!isConnected) {
        const portSelect = document.getElementById("port-select");
        const selectedPort = portSelect.value;
        if (!selectedPort) return;
        
        btn.textContent = "CONNECTING...";
        const ok = await window.pywebview.api.connect_device(selectedPort);
        if (ok) {
            isConnected = true;
            btn.textContent = "DISCONNECT";
            btn.classList.add("connected-state");
            document.getElementById("status-dot").className = "status-dot connected";
            document.getElementById("status-text").textContent = "Connected";
            
            // 拉取配置并渲染
            const config = await window.pywebview.api.fetch_config();
            if (config) {
                renderConfig(config);
            }
        } else {
            btn.textContent = "CONNECT";
            alert("Connection Failed / 连接失败，请检查串口是否已被占用！");
        }
    } else {
        await window.pywebview.api.disconnect_device();
        isConnected = false;
        btn.textContent = "CONNECT";
        btn.classList.remove("connected-state");
        document.getElementById("status-dot").className = "status-dot disconnected";
        document.getElementById("status-text").textContent = "Disconnected";
        document.getElementById("firmware-ver").textContent = "v--";
        resetConfigUi();
    }
}

// ── 渲染配置到界面上 ─────────────────────────────────────────────────────
function renderConfig(config) {
    // 固件版本号
    document.getElementById("firmware-ver").textContent = "v" + (config.version || "1.0.9");
    
    // 麦克风
    document.getElementById("mic-toggle").checked = (config.mic_enabled === 1);
    
    // 自动休眠
    document.getElementById("sleep-toggle").checked = (config.sleep_mode === 1);
    
    // 发射功率 (0-7)
    setTxPowerUi(config.tx_power !== undefined ? config.tx_power : 4);
    
    // 四个按键映射与修饰键
    for (let i = 0; i < 4; i++) {
        const vk = config.mappings[i].vk;
        const mod = config.mappings[i].mod;
        
        currentConfigs[i] = { vk: vk, mod: mod };
        
        // 显示按键字符
        const displayVal = getFriendlyKeyName(vk);
        const cardDisplayEl = document.getElementById(`key-display-${i}`);
        cardDisplayEl.textContent = displayVal;
        
        // 若为主键码非空，添加特定高亮类
        const cardEl = cardDisplayEl.parentElement;
        if (vk > 0) {
            cardEl.classList.add("active-display");
        } else {
            cardEl.classList.remove("active-display");
        }
        
        // 渲染修饰键高亮
        const pills = document.querySelectorAll(`#mods-${i} .mod-pill`);
        pills.forEach(pill => {
            const mask = parseInt(pill.getAttribute("data-mask"));
            if ((mod & mask) > 0) {
                pill.classList.add("active");
            } else {
                pill.classList.remove("active");
            }
        });
    }
}

function resetConfigUi() {
    for (let i = 0; i < 4; i++) {
        document.getElementById(`key-display-${i}`).textContent = "--";
        const cardEl = document.getElementById(`key-display-${i}`).parentElement;
        cardEl.classList.remove("active-display");
        const pills = document.querySelectorAll(`#mods-${i} .mod-pill`);
        pills.forEach(pill => pill.classList.remove("active"));
    }
    document.getElementById("mic-toggle").checked = false;
    document.getElementById("sleep-toggle").checked = false;
    setTxPowerUi(0);
}

// ── 键名转换 ─────────────────────────────────────────────────────────────
function getFriendlyKeyName(vk) {
    if (vk === 0) return "--";
    if (VK_TO_NAME[vk]) return VK_TO_NAME[vk];
    if (vk >= 0x30 && vk <= 0x39) return String.fromCharCode(vk);
    if (vk >= 0x41 && vk <= 0x5A) return String.fromCharCode(vk);
    return `VK_${vk.toString(16).toUpperCase()}`;
}

// ── 点击切换修饰键 (Modifier) ──────────────────────────────────────────
async function toggleMod(btnIdx, mask) {
    if (!isConnected) return;
    
    const pill = document.querySelector(`#mods-${btnIdx} .mod-pill[data-mask="${mask}"]`);
    const wasActive = pill.classList.contains("active");
    
    // 更新本地配置
    if (wasActive) {
        pill.classList.remove("active");
        currentConfigs[btnIdx].mod &= ~mask;
    } else {
        pill.classList.add("active");
        currentConfigs[btnIdx].mod |= mask;
    }
    
    // 一键保存写入到硬件上
    saveAllConfigsToDevice();
}

// ── 功率 (TX Power) 设置交互 ─────────────────────────────────────────────
function setTxPowerUi(level) {
    const dbmMap = ["-12", "-9", "-6", "-3", "0", "3", "6", "9"];
    document.getElementById("tx-power-val").textContent = `${dbmMap[level] || "0"} dBm`;
    
    const segments = document.querySelectorAll("#tx-power-bar .power-segment");
    segments.forEach((seg, idx) => {
        if (idx <= level) {
            seg.classList.add("active");
        } else {
            seg.classList.remove("active");
        }
    });
}

function setTxPower(level) {
    if (!isConnected) return;
    setTxPowerUi(level);
    saveAllConfigsToDevice();
}

// ── 硬件开关设置 ─────────────────────────────────────────────────────────
function onMicToggle() {
    if (!isConnected) return;
    saveAllConfigsToDevice();
}

function onSleepToggle() {
    if (!isConnected) return;
    saveAllConfigsToDevice();
}

// ── 保存配置至开发板 ─────────────────────────────────────────────────────
async function saveAllConfigsToDevice() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    const mic = document.getElementById("mic-toggle").checked ? 1 : 0;
    const sleep = document.getElementById("sleep-toggle").checked ? 1 : 0;
    
    // 获取当前选中的功率格数 (计算 active 的数量 - 1)
    const activeSegments = document.querySelectorAll("#tx-power-bar .power-segment.active");
    const tx = Math.max(0, activeSegments.length - 1);
    
    await window.pywebview.api.write_config(
        currentConfigs, 
        tx, 
        sleep, 
        mic
    );
}

// ── 捕获键盘按键流程 (JS Keydown 原生监听) ─────────────────────────────────
function startKeyCapture(btnIdx) {
    if (!isConnected) {
        alert("Please connect to the ESP32 keyboard first!\n请先建立有线串口连接！");
        return;
    }
    if (capturingIdx !== -1) return; // 已经在捕获中
    
    capturingIdx = btnIdx;
    
    // 渲染 UI 状态
    const cardEl = document.querySelector(`.key-card[data-idx="${btnIdx}"]`);
    cardEl.classList.add("capturing-state");
    const btn = document.getElementById(`btn-capture-${btnIdx}`);
    btn.textContent = "PRESS...";
    
    // 注册网页级全局键盘事件拦截
    document.addEventListener("keydown", onKeyCaptured, { capture: true });
}

async function onKeyCaptured(e) {
    e.preventDefault();
    e.stopPropagation();
    
    const code = e.code;
    let vk = 0;
    
    if (JS_CODE_TO_VK[code]) {
        vk = JS_CODE_TO_VK[code];
    } else {
        // 如果不在映射表里，尝试使用 key
        const key = e.key.toUpperCase();
        if (key.length === 1 && key >= 'A' && key <= 'Z') {
            vk = key.charCodeAt(0);
        } else if (key.length === 1 && key >= '0' && key <= '9') {
            vk = key.charCodeAt(0);
        }
    }
    
    // 卸载事件拦截器
    document.removeEventListener("keydown", onKeyCaptured, { capture: true });
    
    const btnIdx = capturingIdx;
    capturingIdx = -1;
    
    // 复原卡片 UI
    const cardEl = document.querySelector(`.key-card[data-idx="${btnIdx}"]`);
    cardEl.classList.remove("capturing-state");
    const btn = document.getElementById(`btn-capture-${btnIdx}`);
    btn.textContent = "CAPTURE";
    
    if (vk > 0) {
        // 存储并显示
        currentConfigs[btnIdx].vk = vk;
        const displayVal = getFriendlyKeyName(vk);
        const cardDisplayEl = document.getElementById(`key-display-${btnIdx}`);
        cardDisplayEl.textContent = displayVal;
        cardDisplayEl.parentElement.classList.add("active-display");
        
        // 写入开发板
        saveAllConfigsToDevice();
    } else {
        alert(`Unsupported key code: ${code}\n不支持该按键码配置！`);
    }
}

// ── OTA 升级相关逻辑 ──────────────────────────────────────────────────────
async function onBrowseFirmware() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    const filePath = await window.pywebview.api.select_local_bin();
    if (filePath) {
        selectedOtaPath = filePath;
        // 截取文件名
        const name = filePath.split("/").pop();
        updateOtaSelectedFile(name);
    }
}

function updateOtaSelectedFile(filename) {
    document.getElementById("selected-file-name").textContent = filename;
    document.getElementById("selected-file-name").style.color = "var(--accent-orange)";
    document.getElementById("btn-flash").disabled = false;
}

async function onFlashFirmware() {
    if (!selectedOtaPath || !isConnected) return;
    
    const btnFlash = document.getElementById("btn-flash");
    btnFlash.disabled = true;
    btnFlash.textContent = "FLASHING...";
    
    const progressFill = document.getElementById("progress-fill");
    const progressPct = document.getElementById("progress-pct");
    
    progressFill.style.width = "0%";
    progressPct.textContent = "0.0%";
    
    const ok = await window.pywebview.api.trigger_ota(selectedOtaPath);
    
    if (ok) {
        alert("OTA Upgrade Completed Successfully! The device is now rebooting.\n固件升级成功！开发板正在重启，请稍候。");
        btnFlash.textContent = "FLASH FIRMWARE";
        progressFill.style.width = "100%";
        progressPct.textContent = "100%";
    } else {
        alert("OTA Upgrade Failed! Please reconnect and try again.\n固件写入失败，请检查供电线并复位重新连接测试！");
        btnFlash.textContent = "FLASH FIRMWARE";
        btnFlash.disabled = false;
    }
}

// ── 被 Python 侧调用的回调通知接口 ──────────────────────────────────────────
function onOtaProgress(written, total) {
    const pct = ((written / total) * 100).toFixed(1);
    document.getElementById("progress-fill").style.width = `${pct}%`;
    document.getElementById("progress-pct").textContent = `${pct}%`;
}

// ── 自定义关闭窗口 ───────────────────────────────────────────────────────
function closeAppWindow() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.close_window();
    }
}

// ── 物理按键点击高亮闪烁交互与监控 ──────────────────────────────────────────
function onPhysicalButtonEvent(btnId, state) {
    const card = document.getElementById(`key-card-${btnId}`);
    if (!card) return;
    
    if (state === 1) {
        // 卡片弹跳闪烁
        card.classList.add("physical-pressed");
        setTimeout(() => {
            card.classList.remove("physical-pressed");
        }, 250);
        
        // 更新顶部按键监视文本
        const vk = currentConfigs[btnId].vk;
        const keyName = getFriendlyKeyName(vk);
        const mod = currentConfigs[btnId].mod;
        
        const parts = [];
        const modNames = [
            { mask: 0x01, name: "Ctrl" }, { mask: 0x02, name: "Shift" }, 
            { mask: 0x04, name: "Alt" }, { mask: 0x08, name: "Cmd" },
            { mask: 0x10, name: "Ctrl" }, { mask: 0x20, name: "Shift" }, 
            { mask: 0x40, name: "Alt" }, { mask: 0x80, name: "Cmd" }
        ];
        
        // 提取已选中的修饰键并排重
        const seenMods = new Set();
        modNames.forEach(m => {
            if ((mod & m.mask) > 0) {
                seenMods.add(m.name);
            }
        });
        seenMods.forEach(name => parts.push(name));
        parts.push(keyName);
        
        const monitorVal = document.getElementById("monitor-val");
        monitorVal.textContent = parts.join("+");
        
        // 播放最近按键小震颤高亮动效
        monitorVal.style.transform = "scale(1.1)";
        setTimeout(() => {
            monitorVal.style.transform = "scale(1)";
        }, 150);
    }
}
