import base64
import time
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string
import socketio

# Two Socket.IO servers for camera (5001) and VNC (5002)
# We'll run this file with the port you want; see CLI usage below.

sio = socketio.Server(
    async_mode='gevent', cors_allowed_origins='*', ping_interval=25, ping_timeout=60)
app = Flask(__name__)
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

INDEX_HTML = """
<!doctype html>
<title>Test Control Panel</title>
<style>
body { font-family: system-ui, sans-serif; margin: 2rem; }
button { margin: 0.25rem; padding: 0.5rem 0.75rem; }
img { max-width: 45vw; border: 1px solid #ccc; margin: 0.5rem 0; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
pre { background: #111; color: #eee; padding: 0.5rem; }
</style>
<h1>Test Control Panel</h1>
<p>This single app can serve either the Camera socket (5001) or the VNC socket (5002). Use the correct port.</p>

<div class="grid">
  <div>
    <h2>Camera</h2>
    <button onclick="emit('start_camera')">Start Camera</button>
    <button onclick="emit('stop_camera')">Stop Camera</button>
    <button onclick="emit('switch_camera')">Switch Camera</button>
    <div>
      <img id="camera" />
    </div>
  </div>
  <div>
    <h2>VNC</h2>
    <button onclick="emit('start_stream')">Start Stream</button>
    <button onclick="emit('stop_stream')">Stop Stream</button>
    <div>
      <img id="screen" />
    </div>
    <h3>Gestures</h3>
    <button onclick="tap()">Tap center</button>
    <button onclick="swipe()">Swipe right</button>
    <button onclick="back()">Sys Back</button>
    <button onclick="home()">Sys Home</button>
    <button onclick="recents()">Sys Recents</button>
  </div>
</div>

<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script>
  const port = location.port;
  const socket = io(`${location.protocol}//${location.hostname}:${port}`, {transports:['websocket']});

  function emit(ev, data) { socket.emit(ev, data); }

  socket.on('connect', () => console.log('connected'));
  socket.on('disconnect', () => console.log('disconnected'));

  socket.on('camera_update', (data) => {
    const img = document.getElementById('camera');
    if (data && data.image) img.src = `data:image/jpeg;base64,${data.image}`;
  });

  socket.on('screen_update', (data) => {
    const img = document.getElementById('screen');
    if (data && data.image) img.src = `data:image/jpeg;base64,${data.image}`;
  });

  function tap(){
    emit('perform_tap', {x: 540, y: 960});
  }
  function swipe(){
    emit('perform_touch_move', {sx: 200, sy: 960, ex: 900, ey: 960});
  }
  function back(){ emit('perform_gesture', {type: 'back'}); }
  function home(){ emit('perform_gesture', {type: 'home'}); }
  function recents(){ emit('perform_gesture', {type: 'recents'}); }
</script>
"""


@app.route('/')
def index():
    return render_template_string(INDEX_HTML)


@app.route('/ping')
def ping():
    return jsonify(ok=True, ts=datetime.utcnow().isoformat())

# Relay helpers for debugging via REST


@app.post('/emit')
def emit_event():
    p = request.json or {}
    ev = p.get('event')
    data = p.get('data')
    if not ev:
        return jsonify(ok=False, error='missing event'), 400
    sio.emit(ev, data)
    return jsonify(ok=True)

# Socket event prints (server side) for visibility


@sio.event
def connect(sid, environ):
    print('socket connected', sid)


@sio.event
def disconnect(sid):
    print('socket disconnected', sid)

# Just acknowledge commands (the Android app reacts to these)


@sio.on('start_camera')
def start_camera(sid, data=None, *args, **kwargs):
    try:
        print('start_camera from', sid, 'data=', data)
        # Acknowledge to the client
        sio.emit('start_camera_ack', {'ok': True, 'ts': time.time()}, to=sid)
    except Exception as e:
        print('start_camera handler error', e)


@sio.on('stop_camera')
def stop_camera(sid, data=None, *args, **kwargs):
    try:
        print('stop_camera from', sid, 'data=', data)
        sio.emit('stop_camera_ack', {'ok': True, 'ts': time.time()}, to=sid)
    except Exception as e:
        print('stop_camera handler error', e)


@sio.on('switch_camera')
def switch_camera(sid, data=None, *args, **kwargs):
    try:
        print('switch_camera from', sid, 'data=', data)
        sio.emit('switch_camera_ack', {'ok': True, 'ts': time.time()}, to=sid)
    except Exception as e:
        print('switch_camera handler error', e)


@sio.on('start_stream')
def start_stream(sid, data=None, *args, **kwargs):
    try:
        print('start_stream from', sid, 'data=', data)
        sio.emit('start_stream_ack', {'ok': True, 'ts': time.time()}, to=sid)
    except Exception as e:
        print('start_stream handler error', e)


@sio.on('stop_stream')
def stop_stream(sid, data=None, *args, **kwargs):
    try:
        print('stop_stream from', sid, 'data=', data)
        sio.emit('stop_stream_ack', {'ok': True, 'ts': time.time()}, to=sid)
    except Exception as e:
        print('stop_stream handler error', e)


# Relay media frames from Android clients to web UI clients
@sio.on('screen_data')
def handle_screen_data(sid, data=None, *args, **kwargs):
    try:
        img_len = 0
        if data and isinstance(data, dict) and 'image' in data and data['image']:
            img_len = len(data['image'])
        print(f'screen_data from {sid} image_len={img_len}')
        # Broadcast to all connected web UI clients as 'screen_update' (server.py compatibility)
        sio.emit('screen_update', {
            'image': data.get('image') if isinstance(data, dict) else None,
            'width': data.get('width') if isinstance(data, dict) else 0,
            'height': data.get('height') if isinstance(data, dict) else 0
        })
    except Exception as e:
        print('screen_data handler error', e)


@sio.on('camera_data')
def handle_camera_data(sid, data=None, *args, **kwargs):
    try:
        img_len = 0
        if data and isinstance(data, dict) and 'image' in data and data['image']:
            img_len = len(data['image'])
        print(f'camera_data from {sid} image_len={img_len}')
        sio.emit('camera_update', {
            'image': data.get('image') if isinstance(data, dict) else None,
            'width': data.get('width') if isinstance(data, dict) else 0,
            'height': data.get('height') if isinstance(data, dict) else 0
        })
    except Exception as e:
        print('camera_data handler error', e)

# The Android app will emit camera_data and screen_data back, which the web UI displays.


if __name__ == '__main__':
    import argparse
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    parser = argparse.ArgumentParser(
        description='Test Flask Socket.IO server for camera or VNC')
    parser.add_argument('--port', type=int, default=5001,
                        help='Port to listen on (5001 for camera, 5002 for VNC)')
    args = parser.parse_args()

    print(f"Starting test server on :{args.port}")
    server = pywsgi.WSGIServer(
        ('0.0.0.0', args.port), app, handler_class=WebSocketHandler)
    server.serve_forever()
