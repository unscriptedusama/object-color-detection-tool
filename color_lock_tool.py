from flask import Flask, render_template_string, Response, jsonify
import cv2
import numpy as np

app = Flask(__name__)
camera = None
camera_running = False

latest_color = {"hex": "#------", "rgb": "(---,---,---)"}
saved_colors = []


# ---------------- UI -----------------
html_template = """
<!DOCTYPE html>
<html>
<head>
<title> Usama Color Detection </title>
<style>
body {
    margin: 0;
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    font-family: 'Segoe UI', Tahoma, sans-serif;
    color: white;
}
header { text-align: center; padding: 20px; font-size: 2em; font-weight: bold; }
.controls { text-align: center; margin-bottom: 15px; }
button {
    background: #00ff88; border: none; padding: 12px 25px;
    font-size: 1em; border-radius: 8px; cursor: pointer;
    font-weight: bold; margin: 5px; transition: 0.3s;
}
button:hover { background: #00cc6a; }
.container { display: flex; justify-content: center; gap: 20px; padding: 10px; }
.video-container {
    background: #111; padding: 10px; border-radius: 15px;
    box-shadow: 0 0 20px rgba(0,0,0,0.5);
}
#video {
    border-radius: 15px; width: 640px; height: 480px;
    border: 3px solid #00ff88;
}
.side-panel {
    background: rgba(255,255,255,0.05);
    padding: 20px; border-radius: 15px;
    width: 250px; text-align: center;
    box-shadow: 0 0 15px rgba(0,0,0,0.3);
}
.color-box {
    width: 100px; height: 100px; border-radius: 50%;
    margin: auto; border: 3px solid white;
}
.code-box {
    background: rgba(0,0,0,0.4); padding: 8px; margin-top: 10px;
    border-radius: 5px; cursor: pointer; user-select: all;
}
.history { margin-top: 15px; text-align: left; }
.history-item {
    display: flex; align-items: center;
    background: rgba(0,0,0,0.4); margin-bottom: 5px;
    padding: 5px; border-radius: 5px; cursor: pointer;
}
.history-color {
    width: 25px; height: 25px; border-radius: 50%;
    margin-right: 8px;
}
</style>
</head>
<body>
<header> USAMA COLOR DETECTION TOOL</header>
<div class="controls">
    <button onclick="startFeed()">▶ Start</button>
    <button onclick="stopFeed()">⏹ Stop</button>
    <button onclick="saveColor()">💾 Save</button>
</div>
<div class="container">
    <div class="video-container">
        <img id="video" src="">
    </div>
    <div class="side-panel">
        <h2>Current Color</h2>
        <div id="color-box" class="color-box"></div>
        <div class="code-box" id="hex-code" onclick="copyText('hex-code')">HEX: #------</div>
        <div class="code-box" id="rgb-code" onclick="copyText('rgb-code')">RGB: (---,---,---)</div>
        <small>Click to copy</small>
        <div class="history" id="history">
            <h3>Saved Colors</h3>
        </div>
    </div>
</div>

<script>
function startFeed() {
    fetch("/start_camera").then(()=> {
        document.getElementById("video").src = "/video_feed";
        pollColor();
    });
}
function stopFeed() {
    fetch("/stop_camera");
    document.getElementById("video").src = "";
}
function saveColor() {
    fetch("/save_color").then(()=>loadHistory());
}
function copyText(id) {
    let text = document.getElementById(id).innerText.split(": ")[1];
    navigator.clipboard.writeText(text);
}
function pollColor() {
    fetch("/color_data")
    .then(res => res.json())
    .then(data => {
        document.getElementById("color-box").style.background = data.hex;
        document.getElementById("hex-code").innerText = "HEX: " + data.hex;
        document.getElementById("rgb-code").innerText = "RGB: " + data.rgb;
    });
    setTimeout(pollColor, 500);
}
function loadHistory() {
    fetch("/get_history")
    .then(res => res.json())
    .then(history => {
        let container = document.getElementById("history");
        container.innerHTML = "<h3>Saved Colors</h3>";
        history.forEach(c => {
            container.innerHTML += `
                <div class='history-item' onclick="navigator.clipboard.writeText('${c.hex}')">
                    <div class='history-color' style='background:${c.hex}'></div>
                    ${c.hex} / ${c.rgb}
                </div>`;
        });
    });
}
</script>
</body>
</html>
"""


# -------- Camera detection -----------
def find_camera():
    for i in range(5):  # Try indexes 0-4
        print(f"🔍 Trying camera index {i}...")
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            print(f"✅ Camera opened at index {i}")
            return cap
        cap.release()
    print("❌ No camera found!")
    return None


def detect_color(frame):
    h, w, _ = frame.shape
    cx, cy = w // 2, h // 2
    r = 50
    mask = np.zeros(frame.shape[:2], dtype="uint8")
    cv2.circle(mask, (cx, cy), r, 255, -1)
    mean = cv2.mean(frame, mask=mask)[:3]
    b, g, r_ = [int(x) for x in mean]
    hex_code = "#{:02x}{:02x}{:02x}".format(r_, g, b)
    return hex_code, f"({r_},{g},{b})"


def gen_frames():
    global camera, latest_color
    while camera_running and camera:
        success, frame = camera.read()
        if not success:
            break
        hex_code, rgb = detect_color(frame)
        latest_color = {"hex": hex_code, "rgb": rgb}
        cv2.putText(frame, f"{hex_code} RGB{rgb}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        h, w, _ = frame.shape
        cv2.circle(frame, (w//2, h//2), 50, (0, 255, 0), 2)
        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


@app.route('/')
def index():
    return render_template_string(html_template)


@app.route('/start_camera')
def start_camera():
    global camera, camera_running
    if not camera_running:
        camera = find_camera()
        if camera:
            camera_running = True
        else:
            return "no_camera", 500
    return "ok"


@app.route('/stop_camera')
def stop_camera():
    global camera, camera_running
    camera_running = False
    if camera:
        camera.release()
        camera = None
    return "ok"


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/color_data')
def color_data():
    return jsonify(latest_color)


@app.route('/save_color')
def save_color():
    saved_colors.append(latest_color.copy())
    return "saved"


@app.route('/get_history')
def get_history():
    return jsonify(saved_colors)


if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000)
