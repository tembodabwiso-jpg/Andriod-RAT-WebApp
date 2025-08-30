import sys
import os
import threading
import socket
import struct
import cv2
import numpy as np
import time
import logging
from flask import Blueprint, render_template, Response, jsonify, current_app
import base64
from threading import Lock

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('CameraStreamAPI')

# Create blueprint
camera_stream_bp = Blueprint('camera_stream', __name__)

# Global variables for frame sharing
current_frame = None
frame_lock = Lock()
last_frame_time = 0
client_connected = False
camera_server_thread = None
keep_running = True

def get_client_ip():
    """Return the IP address of the client"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to a public IP (doesn't actually send packets)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.error(f"Error getting IP address: {e}")
        return "127.0.0.1"

def receive_frames():
    global current_frame, client_connected, last_frame_time, keep_running
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    server_socket.settimeout(80)  # 80 second timeout
    
    try:
        # Bind to all interfaces on port 5000
        server_socket.bind(('0.0.0.0', 5000))
        server_socket.listen(1)
        logger.info("Camera Server listening on port 5000")
        
        while keep_running:
            logger.info("Waiting for camera connection...")
            try:
                client_socket, addr = server_socket.accept()
                client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                client_socket.settimeout(15)  # 15 seconds for client operations
                logger.info(f"Connected to camera device at {addr}")
                client_connected = True
                
                # Process the camera stream
                handle_client(client_socket, addr)
            except socket.timeout:
                logger.warning("Timeout waiting for connection")
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")
                logger.exception("Full traceback:")
            finally:
                client_connected = False
                try:
                    client_socket.close()
                except:
                    pass
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.exception("Full traceback:")
    finally:
        server_socket.close()
        logger.info("Camera server stopped")

def handle_client(client_socket, addr):
    global current_frame, last_frame_time, client_connected
    
    try:
        # Increase socket buffer size
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
        
        # Set TCP keep alive
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        logger.info(f"Starting frame reception from {addr}")
        
        # Connection state tracking
        consecutive_timeouts = 0
        max_timeouts = 5
        
        # Buffer for incoming data
        buffer = bytearray()
        
        while keep_running:
            try:
                # Check for extended period with no data
                current_time = time.time()
                if current_time - last_frame_time > 10 and last_frame_time > 0:
                    logger.warning(f"No frames received from {addr} for 10 seconds, checking connection...")
                    consecutive_timeouts += 1
                    if consecutive_timeouts >= max_timeouts:
                        logger.warning(f"Too many consecutive timeouts, closing connection with {addr}")
                        break
                    # Continue to next iteration instead of blocking on receive
                    time.sleep(1)
                    continue
                
                # Read size field (4 bytes)
                if len(buffer) < 4:
                    chunk = client_socket.recv(4 - len(buffer))
                    if not chunk:
                        logger.warning("Connection closed while reading size field")
                        break
                    buffer.extend(chunk)
                    continue
                
                # Parse frame size
                frame_size = struct.unpack('>I', buffer[:4])[0]
                
                # Check for keep-alive packet (size 0)
                if frame_size == 0:
                    logger.debug("Received keep-alive packet")
                    buffer = bytearray()  # Clear buffer
                    continue
                
                # Check for reasonable frame size
                if frame_size > 1000000:  # Max 1MB
                    logger.warning(f"Invalid frame size: {frame_size} bytes, resetting connection")
                    buffer = bytearray()  # Reset buffer
                    continue
                
                # Read the frame data
                while len(buffer) < frame_size + 4:
                    remaining = frame_size + 4 - len(buffer)
                    chunk = client_socket.recv(min(remaining, 8192))  # Read in 8KB chunks
                    if not chunk:
                        logger.warning("Connection closed while reading frame data")
                        break
                    buffer.extend(chunk)
                
                # If we have a complete frame
                if len(buffer) >= frame_size + 4:
                    # Extract the frame data
                    frame_data = buffer[4:frame_size + 4]
                    
                    # Process the frame
                    process_frame(frame_data)
                    
                    # Update timestamp
                    last_frame_time = time.time()
                    
                    # Reset consecutive timeouts
                    consecutive_timeouts = 0
                    
                    # Remove processed data from buffer
                    buffer = buffer[frame_size + 4:]
            
            except socket.timeout:
                logger.warning("Socket timeout while reading data")
                consecutive_timeouts += 1
                if consecutive_timeouts >= max_timeouts:
                    logger.warning(f"Too many consecutive timeouts ({consecutive_timeouts}), closing connection")
                    break
            except Exception as e:
                logger.error(f"Error processing stream: {e}")
                logger.exception("Full traceback:")
                break
    
    except Exception as e:
        logger.error(f"Error in client handler: {e}")
        logger.exception("Full traceback:")
    finally:
        try:
            client_socket.close()
        except:
            pass

def process_frame(frame_data):
    """Process received frame data"""
    global current_frame
    
    try:
        # Decode JPEG frame
        img_array = np.frombuffer(frame_data, dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if frame is not None:
            # Add timestamp to the frame
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Update the global frame with thread safety
            with frame_lock:
                current_frame = frame
        else:
            logger.warning(f"Failed to decode frame of size {len(frame_data)} bytes")
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        logger.exception("Full traceback:")

def generate_frames():
    """Generate frames for the MJPEG stream"""
    global current_frame
    
    # Create a black frame with text as initial frame
    height, width = 480, 640
    img = np.zeros((height, width, 3), np.uint8)
    cv2.putText(img, "Waiting for camera connection...", (50, height//2), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    while True:
        # If we have a frame, encode and yield it
        frame_to_yield = None
        with frame_lock:
            if current_frame is not None:
                frame_to_yield = current_frame.copy()
            else:
                # If no frame available, use the waiting message
                frame_to_yield = img.copy()
                # Add connection status
                status = "Connected" if client_connected else "Disconnected"
                cv2.putText(frame_to_yield, f"Status: {status}", (50, height//2 + 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                # Add timestamp
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(frame_to_yield, timestamp, (50, height//2 + 80), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Encode the frame
        ret, buffer = cv2.imencode('.jpg', frame_to_yield)
        if not ret:
            logger.error("Failed to encode frame")
            continue
            
        # Yield the frame in MJPEG stream format
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Sleep to control frame rate (10 FPS)
        time.sleep(0.1)

def get_frame_as_base64():
    """Get the current frame as a base64 encoded string"""
    global current_frame
    
    with frame_lock:
        if current_frame is not None:
            # Encode the frame
            ret, buffer = cv2.imencode('.jpg', current_frame)
            if not ret:
                return None
            
            # Convert to base64
            frame_bytes = buffer.tobytes()
            base64_frame = base64.b64encode(frame_bytes).decode('utf-8')
            return base64_frame
        else:
            return None

# Routes
@camera_stream_bp.route('/camera')
def camera_page():
    """Render the camera streaming page"""
    client_ip = get_client_ip()
    return render_template('camera.html', server_ip=client_ip)

@camera_stream_bp.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@camera_stream_bp.route('/camera/status')
def camera_status():
    """Return the status of the camera connection"""
    global client_connected, last_frame_time
    
    current_time = time.time()
    frame_age = current_time - last_frame_time if last_frame_time > 0 else -1
    
    status = {
        "connected": client_connected,
        "last_frame_time": last_frame_time,
        "frame_age_seconds": frame_age,
        "has_current_frame": current_frame is not None
    }
    
    return jsonify(status)

@camera_stream_bp.route('/camera/snapshot')
def camera_snapshot():
    """Return the current frame as a base64 encoded image"""
    frame_base64 = get_frame_as_base64()
    
    if frame_base64:
        return jsonify({
            "success": True,
            "frame": frame_base64
        })
    else:
        return jsonify({
            "success": False,
            "error": "No frame available"
        })

def start_camera_server():
    """Start the camera server thread"""
    global camera_server_thread, keep_running
    
    if camera_server_thread is None or not camera_server_thread.is_alive():
        keep_running = True
        camera_server_thread = threading.Thread(target=receive_frames)
        camera_server_thread.daemon = True
        camera_server_thread.start()
        logger.info("Camera server thread started")
        return True
    else:
        logger.warning("Camera server already running")
        return False

def stop_camera_server():
    """Stop the camera server thread"""
    global camera_server_thread, keep_running
    
    keep_running = False
    if camera_server_thread and camera_server_thread.is_alive():
        logger.info("Waiting for camera server thread to stop...")
        camera_server_thread.join(timeout=5)
        logger.info("Camera server thread stopped")
        return True
    else:
        logger.warning("Camera server not running")
        return False

# Start the camera server when this module is imported
start_camera_server()