import sys
import os
import threading
import socket
import struct
import cv2
import numpy as np
import time
import logging
from flask import Blueprint, render_template, Response, jsonify, request, current_app
import base64
from threading import Lock
from ..auth import auth_required
from models.devices import Device
import requests

# Configure logging
# logging.basicConfig(
#     level=logging.DEBUG,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
logger = logging.getLogger('CameraStreamCommand')

# Create blueprint
stream_camera_bp = Blueprint('stream_camera_command', __name__)

# Global variables for frame sharing
current_frame = None
frame_lock = Lock()
last_frame_time = 0
client_connected = False
camera_server_thread = None
keep_running = True
stream_control = {}  # Dictionary to track stream status for each device

# Change socket port from 5000 to 5005
SOCKET_PORT = 5001

def get_client_ip():
    """Return the most appropriate IP address for external connections"""
    try:
        # Create a list of potential IPs with priority
        candidate_ips = []
        
        try:
            # Try to connect to a public server to determine which interface is used for external traffic
            # This helps identify the correct external-facing interface
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5) # Quick timeout to avoid hanging
            # Connect to a public DNS (doesn't actually send packets)
            s.connect(("8.8.8.8", 53))
            primary_ip = s.getsockname()[0]
            s.close()
            
            # Give highest priority to the interface with external connectivity
            candidate_ips.append((0, primary_ip))  # Highest priority
            logger.info(f"Primary external IP: {primary_ip}")
        except Exception as e:
            logger.warning(f"Could not determine external interface: {e}")
        
        # Get all available interfaces as backup options
        try:
            import netifaces
            interfaces = netifaces.interfaces()
            for i, interface in enumerate(interfaces):
                try:
                    # Skip loopback interfaces
                    if interface.startswith(('lo', 'loop')):
                        continue
                        
                    addresses = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addresses:
                        for address in addresses[netifaces.AF_INET]:
                            ip_addr = address['addr']
                            # Skip localhost/loopback addresses
                            if ip_addr.startswith('127.'):
                                continue
                            candidate_ips.append((1, ip_addr))  # Lower priority than direct external
                            logger.info(f"Found additional IP on {interface}: {ip_addr}")
                except Exception as ie:
                    logger.warning(f"Error checking interface {interface}: {ie}")
        except ImportError:
            logger.warning("netifaces package not available, using limited IP detection")
        
        # If no external IPs found, fall back to simple hostname resolution
        if not candidate_ips:
            hostname = socket.gethostname()
            try:
                ip = socket.gethostbyname(hostname)
                if not ip.startswith('127.'):
                    candidate_ips.append((2, ip))
                    logger.info(f"Using hostname-resolved IP: {ip}")
            except Exception as e:
                logger.warning(f"Error resolving hostname IP: {e}")
        
        # Final fallback to localhost
        if not candidate_ips:
            candidate_ips.append((3, "127.0.0.1"))
            logger.warning("No external IP found, using localhost")
        
        # Sort by priority (lowest number first)
        candidate_ips.sort()
        selected_ip = candidate_ips[0][1]
        
        logger.info(f"Selected IP address for camera streaming: {selected_ip}")
        return selected_ip
    except Exception as e:
        logger.error(f"Error getting IP address: {e}")
        logger.exception("Full traceback:")
        return "127.0.0.1"  # Final safety fallback

def receive_frames(device_id):
    global current_frame, client_connected, last_frame_time, keep_running
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Set socket options for better reliability
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of address/port
    server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle's algorithm
    
    # Increase buffer sizes for better performance
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)  # 256KB receive buffer
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)  # 256KB send buffer
    
    # Set reasonable timeout for operations
    server_socket.settimeout(60)  # 60 second timeout for server operations
    
    try:
        # Bind to all interfaces on specified port
        logger.info(f"Binding camera server socket to 0.0.0.0:{SOCKET_PORT}")
        server_socket.bind(('0.0.0.0', SOCKET_PORT))
        server_socket.listen(1)  # Only accept one connection at a time
        
        # Log local endpoint info for debugging
        local_addr = server_socket.getsockname()
        logger.info(f"Camera Server for device {device_id} listening on {local_addr[0]}:{local_addr[1]}")
        
        # Print server IP information for debugging
        def get_all_ips():
            ips = []
            try:
                # Get all network interfaces
                import netifaces
                interfaces = netifaces.interfaces()
                for interface in interfaces:
                    # Get IP addresses for this interface
                    try:
                        addresses = netifaces.ifaddresses(interface)
                        # Check for IPv4 addresses
                        if netifaces.AF_INET in addresses:
                            for address in addresses[netifaces.AF_INET]:
                                ips.append((interface, address['addr']))
                    except Exception as e:
                        logger.error(f"Error getting addresses for interface {interface}: {e}")
            except ImportError:
                # Fallback if netifaces isn't available
                import socket
                hostname = socket.gethostname()
                ips.append(('hostname', socket.gethostbyname(hostname)))
            except Exception as e:
                logger.error(f"Error getting network interfaces: {e}")
            
            return ips
        
        # Log all available IP addresses for debugging
        try:
            ip_addresses = get_all_ips()
            for interface, ip in ip_addresses:
                logger.info(f"Available interface: {interface} - {ip}")
        except Exception as e:
            logger.error(f"Error getting IP addresses: {e}")
        
        while keep_running and stream_control.get(device_id, {}).get('active', False):
            logger.info(f"Waiting for camera connection from device {device_id}...")
            try:
                client_socket, addr = server_socket.accept()
                logger.info(f"Connected to camera device at {addr}")
                
                # Set client socket options for better performance
                client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
                
                # Set client socket timeout
                client_socket.settimeout(15)  # 15 seconds for client operations
                
                client_connected = True
                stream_control[device_id]['connected'] = True
                
                # Process the camera stream
                handle_client(client_socket, addr)
            except socket.timeout:
                logger.warning("Timeout waiting for connection")
            except socket.error as e:
                logger.error(f"Socket error accepting connection: {e}")
                # Add a short delay before retrying to avoid tight loop
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")
                logger.exception("Full traceback:")
                # Add a short delay before retrying
                time.sleep(1)
            finally:
                client_connected = False
                if device_id in stream_control:
                    stream_control[device_id]['connected'] = False
                try:
                    client_socket.close()
                except:
                    pass
    except socket.error as e:
        logger.error(f"Socket error: {e}")
        logger.exception("Full traceback:")
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.exception("Full traceback:")
    finally:
        try:
            server_socket.close()
        except:
            pass
        logger.info(f"Camera server for device {device_id} stopped")

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

def generate_frames(device_id):
    """Generate frames for the MJPEG stream"""
    global current_frame
    
    # Create a black frame with text as initial frame
    height, width = 480, 640
    img = np.zeros((height, width, 3), np.uint8)
    
    # Make it dark theme styled
    img[:] = (33, 37, 41)  # Dark background
    
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
                status_color = (0, 255, 0) if client_connected else (0, 0, 255)
                cv2.putText(frame_to_yield, f"Status: {status}", (50, height//2 + 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
                # Add timestamp
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(frame_to_yield, timestamp, (50, height//2 + 80), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 2)
                
                # Add device info
                device_name = stream_control.get(device_id, {}).get('device_name', 'Unknown Device')
                cv2.putText(frame_to_yield, f"Device: {device_name}", (50, height//2 + 120), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 2)
        
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

def start_camera_server(device_id):
    """Start the camera server thread"""
    global camera_server_thread, keep_running
    
    # Check if the port is already in use
    test_socket = None
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.settimeout(1)
        test_socket.bind(('0.0.0.0', SOCKET_PORT))
        test_socket.listen(1)
        # Port is available
        test_socket.close()
        test_socket = None
    except socket.error as e:
        logger.error(f"Cannot start camera server - port {SOCKET_PORT} is already in use: {e}")
        if test_socket:
            test_socket.close()
        return False
    
    # Initialize or update device in stream control
    if device_id not in stream_control:
        device = Device.query.get(device_id)
        stream_control[device_id] = {
            'active': True,
            'connected': False,
            'thread': None,
            'device_name': device.name if device else 'Unknown Device'
        }
    else:
        stream_control[device_id]['active'] = True
    
    if stream_control[device_id]['thread'] is None or not stream_control[device_id]['thread'].is_alive():
        keep_running = True
        thread = threading.Thread(target=receive_frames, args=(device_id,))
        thread.daemon = True
        thread.start()
        stream_control[device_id]['thread'] = thread
        logger.info(f"Camera server thread started for device {device_id}")
        return True
    else:
        logger.warning(f"Camera server already running for device {device_id}")
        return False

def stop_camera_server(device_id):
    """Stop the camera server thread"""
    global keep_running
    
    if device_id in stream_control:
        stream_control[device_id]['active'] = False
        thread = stream_control[device_id].get('thread')
        
        if thread and thread.is_alive():
            # Let the thread exit naturally
            logger.info(f"Waiting for camera server thread to stop for device {device_id}...")
            # Don't actually join as it might block
            return True
        else:
            logger.warning(f"Camera server not running for device {device_id}")
    
    return False

def test_connection(ip, port, timeout=3):
    """Test if the server can be connected to from the specified IP and port"""
    logger.info(f"Testing connection to {ip}:{port}")
    test_socket = None
    try:
        # Create a socket and set options
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(timeout)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        # Try to connect to the server
        result = test_socket.connect_ex((ip, port))
        if result == 0:
            logger.info(f"Successfully connected to {ip}:{port}")
            return True
        else:
            logger.warning(f"Failed to connect to {ip}:{port}, error code: {result}")
            return False
    except Exception as e:
        logger.error(f"Error testing connection to {ip}:{port}: {e}")
        return False
    finally:
        if test_socket:
            try:
                test_socket.close()
            except:
                pass

# Routes
@stream_camera_bp.route('/device/<device_id>/commands/stream-camera')
@auth_required
def stream_camera_page(device_id):
    """Render the camera streaming command page"""
    client_ip = None
    
    # Initialize device control if needed
    if device_id not in stream_control:
        device = Device.query.get(device_id)
        client_ip = device.device_ip
        stream_control[device_id] = {
            'active': False,
            'connected': False,
            'thread': None,
            'device_name': 'Mobile Device'
        }
    
    # Check if any other device is streaming
    other_active = any(v['active'] for k, v in stream_control.items() if k != device_id)
    
    return render_template('pages/commands/stream_camera.html', 
                           device_id=device_id,
                           server_ip=client_ip,
                           server_port=SOCKET_PORT,
                           stream_active=stream_control[device_id]['active'],
                           other_active=other_active)

@stream_camera_bp.route('/device/<device_id>/apis/video_feed')
@auth_required
def video_feed(device_id):
    """Video streaming route"""
    return Response(generate_frames(device_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@stream_camera_bp.route('/device/<device_id>/apis/status')
@auth_required
def camera_status(device_id):
    """Return the status of the camera connection"""
    global last_frame_time
    
    if device_id not in stream_control:
        return jsonify({
            "success": False,
            "active": False,
            "connected": False,
            "error": "Device not initialized"
        })
    
    current_time = time.time()
    frame_age = current_time - last_frame_time if last_frame_time > 0 else -1
    
    status = {
        "success": True,
        "active": stream_control[device_id]['active'],
        "connected": stream_control[device_id]['connected'],
        "last_frame_time": last_frame_time,
        "frame_age_seconds": frame_age,
        "has_current_frame": current_frame is not None
    }
    
    return jsonify(status)

@stream_camera_bp.route('/device/<device_id>/apis/snapshot')
@auth_required
def camera_snapshot(device_id):
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

@stream_camera_bp.route('/device/<device_id>/apis/start', methods=['POST'])
@auth_required
def start_stream(device_id):
    """Start camera stream for a device"""
    
    # Check if already active
    if device_id in stream_control and stream_control[device_id]['active']:
        return jsonify({
            "success": False,
            "message": "Stream is already active for this device"
        })
    print(stream_control) 
    # Check if another device is streaming
    if any(v['active'] for k, v in stream_control.items() if k != device_id):
        return jsonify({
            "success": False,
            "message": "Another device is already streaming. Stop that stream first."
        })
    
    # Get device information
    device = Device.query.get(device_id)
    if not device:
        return jsonify({
            "success": False,
            "message": "Device not found"
        })
    
    server_ip = get_client_ip()
    device_ip = device.device_ip
    
    # Check if server port is available before starting
    test_socket = None
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.settimeout(1)
        test_socket.bind(('0.0.0.0', SOCKET_PORT))
        test_socket.listen(1)
        # Port is available
        test_socket.close()
    except socket.error as e:
        logger.error(f"Cannot start camera server - port {SOCKET_PORT} is already in use: {e}")
        return jsonify({
            "success": False,
            "message": f"Server at {server_ip}:{SOCKET_PORT} is not available"
        })
    finally:
        if test_socket:
            try:
                test_socket.close()
            except:
                pass
    
    # Start the local server to receive the stream first
    result = start_camera_server(device_id)
    if not result:
        return jsonify({
            "success": False,
            "message": "Failed to start camera stream server"
        })
    
    # Only send command to start camera stream on the Android device if server started successfully
    try:
        # Call the startCameraStream endpoint on the Android device
        url = f"http://{device_ip}:8080/startCameraStream"
        params = {"serverIP": server_ip, "port": SOCKET_PORT}
        logger.info(f"Sending start camera stream request to {url} with params {params}")
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("status") == "success":
                logger.info(f"Successfully started camera stream on device {device_id}")
            else:
                logger.error(f"Failed to start camera stream: {response_data.get('message')}")
                # Stop the server since device stream failed
                stop_camera_server(device_id)
                return jsonify({
                    "success": False,
                    "message": f"Device error: {response_data.get('message', 'Unknown error')}"
                })
        else:
            logger.error(f"Failed to start camera stream, status code: {response.status_code}")
            # Stop the server since device stream failed
            stop_camera_server(device_id)
            return jsonify({
                "success": False,
                "message": f"Failed to start camera on device: HTTP {response.status_code}"
            })
    except Exception as e:
        logger.error(f"Error starting camera stream on device: {str(e)}")
        # Stop the server since device stream failed
        stop_camera_server(device_id)
        return jsonify({
            "success": False,
            "message": f"Error communicating with device: {str(e)}"
        })
    
    return jsonify({
        "success": True,
        "message": "Camera stream started",
        "server_ip": server_ip,
        "server_port": SOCKET_PORT
    })

@stream_camera_bp.route('/device/<device_id>/apis/stop', methods=['POST'])
@auth_required
def stop_stream(device_id):
    """Stop camera stream for a device"""
    
    if device_id not in stream_control or not stream_control[device_id]['active']:
        return jsonify({
            "success": False,
            "message": "No active stream for this device"
        })
    
    # Get device information
    device = Device.query.get(device_id)
    if not device:
        return jsonify({
            "success": False,
            "message": "Device not found"
        })
    
    device_ip = device.device_ip
    
    # Send command to stop camera stream on the Android device
    try:
        # Call the stopCameraStream endpoint on the Android device
        url = f"http://{device_ip}:8080/stopCameraStream"
        logger.info(f"Sending stop camera stream request to {url}")
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("status") == "success":
                logger.info(f"Successfully stopped camera stream on device {device_id}")
            else:
                logger.error(f"Failed to stop camera stream: {response_data.get('message')}")
                # Still continue to stop the local server
        else:
            logger.error(f"Failed to stop camera stream, status code: {response.status_code}")
            # Still continue to stop the local server
    except Exception as e:
        logger.error(f"Error stopping camera stream on device: {str(e)}")
        # Still continue to stop the local server
    
    # Stop the local server
    result = stop_camera_server(device_id)
    
    return jsonify({
        "success": True,
        "message": "Camera stream stopped"
    })

@stream_camera_bp.route('/device/<device_id>/apis/checkServerAvailable', methods=['GET'])
@auth_required
def check_server_available(device_id):
    """Check if the streaming server is available"""
    server_ip = get_client_ip()
    port = SOCKET_PORT
    
    # Initialize server socket to test binding
    test_socket = None
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.settimeout(1)
        
        # Try to bind to the port
        test_socket.bind(('0.0.0.0', port))
        test_socket.listen(1)
        
        logger.info(f"Port {port} is available for binding")
        available = True
    except socket.error as e:
        logger.error(f"Port {port} is not available for binding: {e}")
        available = False
    finally:
        if test_socket:
            test_socket.close()
    
    return jsonify({
        "success": True,
        "serverAvailable": available,
        "serverIP": server_ip,
        "port": port,
        "message": f"Server at {server_ip}:{port} is {'available' if available else 'not available'}"
    })

@stream_camera_bp.route('/device/<device_id>/apis/checkServerReady', methods=['GET'])
@auth_required
def check_server_conn_ready(device_id):
    """Enhanced check to verify the streaming server is fully ready to accept connections"""
    server_ip = get_client_ip()
    port = SOCKET_PORT

    # Verify we can bind to the port and that it's accessible from the network
    test_socket = None
    connection_ready = False
    
    try:
        # Step 1: Test if we can bind to the port at all
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.settimeout(1)
        
        try:
            test_socket.bind(('0.0.0.0', port))
            test_socket.listen(1)
            logger.info(f"Port {port} is available for binding")
            
            # Step 2: Check if bound port is reachable from all interfaces
            # For this we need to create a simple request handler that sends back a response
            def handle_connection_test():
                try:
                    conn, addr = test_socket.accept()
                    logger.info(f"Test connection received from {addr}")
                    # Send a simple response
                    conn.send(b"READY")
                    conn.close()
                except Exception as e:
                    logger.error(f"Error handling test connection: {e}")
            
            # Start a thread to handle a single test connection
            import threading
            test_thread = threading.Thread(target=handle_connection_test)
            test_thread.daemon = True
            test_thread.start()
            
            # Give time for the thread to start
            time.sleep(0.2)
            
            # Now try to connect back to ourselves from loopback
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(1)
                client_socket.connect(('127.0.0.1', port))
                
                # Check if we get the expected response
                response = client_socket.recv(5)
                if response == b"READY":
                    logger.info(f"Server at 127.0.0.1:{port} is responding correctly")
                    connection_ready = True
                else:
                    logger.warning(f"Server at 127.0.0.1:{port} responded with unexpected data")
                
                client_socket.close()
            except Exception as e:
                logger.error(f"Failed to connect to loopback test server: {e}")
            
            # Wait for the test thread to finish
            test_thread.join(timeout=1)
            
        except socket.error as e:
            logger.error(f"Port {port} is not available for binding: {e}")
    finally:
        if test_socket:
            test_socket.close()
    
    # Return detailed status
    return jsonify({
        "success": True,
        "serverReady": connection_ready,
        "serverIP": server_ip,
        "port": port,
        "interfaces": {
            "loopback_test": connection_ready,
        },
        "message": f"Server at {server_ip}:{port} is {'ready' if connection_ready else 'not ready'} for streaming connections"
    })
