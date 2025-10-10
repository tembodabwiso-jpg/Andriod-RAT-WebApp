# Test Flask App (Camera 5001, VNC 5002)

This simple Socket.IO server lets you test the Android app streams.

- Run one instance for Camera:
  - Port 5001 must match `Config.CAMERA_SOCKET_URL`
- Run another instance for VNC (Screen):
  - Port 5002 must match `Config.VNC_SOCKET_URL`

## Setup

```powershell
# From test-flask-app directory
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
# Camera server
python app.py --port 5001

# In a separate terminal, VNC server
python app.py --port 5002
```

Then open in a browser:
- http://localhost:5001 for camera controls/view
- http://localhost:5002 for VNC controls/view

The page shows buttons to start/stop/switch camera and to start/stop screen stream, plus send basic gestures (tap/swipe/system buttons).
