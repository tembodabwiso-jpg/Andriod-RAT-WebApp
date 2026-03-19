from flask import Blueprint, render_template, jsonify, request, send_file, current_app
import os
import json
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
from ..auth import auth_required
from models.devices import Device
import requests as http_requests
from logzero import logger

file_manager_command = Blueprint('file_manager_command', __name__)

# Dummy data for demonstration
DUMMY_PATHS = [
    {"id": "internal", "name": "Internal Storage", "path": "/storage/emulated/0"},
    {"id": "sdcard", "name": "SD Card", "path": "/storage/sdcard"},
    {"id": "downloads", "name": "Downloads", "path": "/storage/emulated/0/Download"},
    {"id": "dcim", "name": "DCIM", "path": "/storage/emulated/0/DCIM"},
    {"id": "documents", "name": "Documents", "path": "/storage/emulated/0/Documents"}
]

DUMMY_FILES = {
    "/storage/emulated/0": [
        {"name": "Android", "type": "folder", "path": "/storage/emulated/0/Android", "size": "-", "modified": "2023-02-15 14:32:00"},
        {"name": "DCIM", "type": "folder", "path": "/storage/emulated/0/DCIM", "size": "-", "modified": "2023-03-10 09:15:22"},
        {"name": "Download", "type": "folder", "path": "/storage/emulated/0/Download", "size": "-", "modified": "2023-03-12 17:45:33"},
        {"name": "Documents", "type": "folder", "path": "/storage/emulated/0/Documents", "size": "-", "modified": "2023-01-05 11:22:45"},
        {"name": "Movies", "type": "folder", "path": "/storage/emulated/0/Movies", "size": "-", "modified": "2022-12-25 20:10:15"},
        {"name": "Music", "type": "folder", "path": "/storage/emulated/0/Music", "size": "-", "modified": "2023-01-18 08:05:40"},
        {"name": "Pictures", "type": "folder", "path": "/storage/emulated/0/Pictures", "size": "-", "modified": "2023-02-28 16:32:10"}
    ],
    "/storage/emulated/0/Documents": [
        {"name": "Resume.pdf", "type": "file", "path": "/storage/emulated/0/Documents/Resume.pdf", "size": "245 KB", "modified": "2023-01-10 11:22:45"},
        {"name": "Financial_Report.xlsx", "type": "file", "path": "/storage/emulated/0/Documents/Financial_Report.xlsx", "size": "1.2 MB", "modified": "2023-02-15 09:30:12"},
        {"name": "Project_Notes.txt", "type": "file", "path": "/storage/emulated/0/Documents/Project_Notes.txt", "size": "15 KB", "modified": "2023-01-25 14:45:30"},
        {"name": "Work", "type": "folder", "path": "/storage/emulated/0/Documents/Work", "size": "-", "modified": "2023-01-22 16:18:45"}
    ],
    "/storage/emulated/0/Download": [
        {"name": "app-release.apk", "type": "file", "path": "/storage/emulated/0/Download/app-release.apk", "size": "25.4 MB", "modified": "2023-03-05 17:45:33"},
        {"name": "sample_video.mp4", "type": "file", "path": "/storage/emulated/0/Download/sample_video.mp4", "size": "85.2 MB", "modified": "2023-02-20 13:12:05"},
        {"name": "product_manual.pdf", "type": "file", "path": "/storage/emulated/0/Download/product_manual.pdf", "size": "3.5 MB", "modified": "2023-01-15 10:08:22"},
        {"name": "backup.zip", "type": "file", "path": "/storage/emulated/0/Download/backup.zip", "size": "150 MB", "modified": "2023-03-01 19:27:40"}
    ],
    "/storage/emulated/0/DCIM": [
        {"name": "Camera", "type": "folder", "path": "/storage/emulated/0/DCIM/Camera", "size": "-", "modified": "2023-03-10 09:15:22"},
        {"name": "Screenshots", "type": "folder", "path": "/storage/emulated/0/DCIM/Screenshots", "size": "-", "modified": "2023-02-28 14:32:10"}
    ],
    "/storage/emulated/0/DCIM/Camera": [
        {"name": "IMG_20230310_092536.jpg", "type": "file", "path": "/storage/emulated/0/DCIM/Camera/IMG_20230310_092536.jpg", "size": "3.2 MB", "modified": "2023-03-10 09:25:36"},
        {"name": "IMG_20230305_143012.jpg", "type": "file", "path": "/storage/emulated/0/DCIM/Camera/IMG_20230305_143012.jpg", "size": "2.8 MB", "modified": "2023-03-05 14:30:12"},
        {"name": "IMG_20230228_185045.jpg", "type": "file", "path": "/storage/emulated/0/DCIM/Camera/IMG_20230228_185045.jpg", "size": "3.5 MB", "modified": "2023-02-28 18:50:45"},
        {"name": "VID_20230302_113025.mp4", "type": "file", "path": "/storage/emulated/0/DCIM/Camera/VID_20230302_113025.mp4", "size": "35.7 MB", "modified": "2023-03-02 11:30:25"}
    ],
    "/storage/emulated/0/DCIM/Screenshots": [
        {"name": "Screenshot_20230228_142536.jpg", "type": "file", "path": "/storage/emulated/0/DCIM/Screenshots/Screenshot_20230228_142536.jpg", "size": "1.2 MB", "modified": "2023-02-28 14:25:36"},
        {"name": "Screenshot_20230225_093012.jpg", "type": "file", "path": "/storage/emulated/0/DCIM/Screenshots/Screenshot_20230225_093012.jpg", "size": "0.9 MB", "modified": "2023-02-25 09:30:12"}
    ],
    "/storage/sdcard": [
        {"name": "Backups", "type": "folder", "path": "/storage/sdcard/Backups", "size": "-", "modified": "2023-01-15 18:45:30"},
        {"name": "Movies", "type": "folder", "path": "/storage/sdcard/Movies", "size": "-", "modified": "2023-02-10 20:32:15"},
        {"name": "Music", "type": "folder", "path": "/storage/sdcard/Music", "size": "-", "modified": "2023-02-05 11:40:22"}
    ]
}

def get_file_icon(file_type, file_name):
    """Return appropriate icon class based on file type and name."""
    if file_type == "folder":
        return "bi-folder-fill"
    
    extension = file_name.split('.')[-1].lower() if '.' in file_name else ''
    
    if extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
        return "bi-file-image"
    elif extension in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv']:
        return "bi-file-play"
    elif extension in ['mp3', 'wav', 'ogg', 'flac', 'aac']:
        return "bi-file-music"
    elif extension in ['pdf']:
        return "bi-file-pdf"
    elif extension in ['doc', 'docx']:
        return "bi-file-word"
    elif extension in ['xls', 'xlsx']:
        return "bi-file-excel"
    elif extension in ['ppt', 'pptx']:
        return "bi-file-ppt"
    elif extension in ['zip', 'rar', '7z', 'tar', 'gz']:
        return "bi-file-zip"
    elif extension in ['txt', 'log', 'md']:
        return "bi-file-text"
    elif extension in ['apk']:
        return "bi-android2"
    else:
        return "bi-file"

@file_manager_command.route('/device/<device_id>/commands/file-manager')
@auth_required
def file_manager(device_id):
    device = Device.query.get(device_id)
    if not device:
        return "Device not found", 404
    return render_template(
        "pages/commands/file_manager.html",
        device_id=device_id,
        device_ip=device.device_ip,
        storage_locations=DUMMY_PATHS
    )

@file_manager_command.route('/device/<device_id>/commands/file-manager/list', methods=['GET'])
@auth_required
def list_files(device_id):
    path = request.args.get('path', '/storage/emulated/0')

    device = Device.query.get(device_id)
    if device:
        try:
            url = f"http://{device.device_ip}:8080/files/list"
            resp = http_requests.get(url, params={'path': path}, timeout=8)
            if resp.ok:
                data = resp.json()
                files = data.get('files', [])
                for f in files:
                    f['icon'] = get_file_icon(f.get('type', 'file'), f.get('name', ''))
                return jsonify({'success': True, 'path': path, 'files': files})
        except Exception as e:
            logger.debug(f"File manager request failed: {e}")  # Fall through to dummy data

    # Fallback to dummy data when device is unreachable
    files = DUMMY_FILES.get(path, [])
    for f in files:
        f['icon'] = get_file_icon(f['type'], f['name'])
    return jsonify({'success': True, 'path': path, 'files': files})

@file_manager_command.route('/device/<device_id>/commands/file-manager/upload', methods=['POST'])
@auth_required
def upload_file(device_id):
    path = request.form.get('path', '/storage/emulated/0')

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    file_bytes = file.read()
    size = len(file_bytes)
    file.seek(0)

    # Try forwarding to the device
    device = Device.query.get(device_id)
    if device:
        try:
            url = f"http://{device.device_ip}:8080/files/upload"
            resp = http_requests.post(url, files={'file': (filename, file_bytes)},
                                      data={'path': path}, timeout=15)
            if resp.ok:
                return jsonify({'success': True, 'message': 'File uploaded to device'})
        except Exception as e:
            logger.debug(f"File manager request failed: {e}")

    # Fallback: record in dummy data
    if size < 1024:
        size_str = f"{size} B"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"

    new_file = {
        "name": filename,
        "type": "file",
        "path": f"{path}/{filename}",
        "size": size_str,
        "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "icon": get_file_icon("file", filename)
    }
    if path in DUMMY_FILES:
        DUMMY_FILES[path].append(new_file)

    return jsonify({'success': True, 'message': 'File uploaded successfully', 'file': new_file})

@file_manager_command.route('/device/<device_id>/commands/file-manager/download', methods=['GET'])
@auth_required
def download_file(device_id):
    file_path = request.args.get('path')
    
    if not file_path:
        return jsonify({'success': False, 'message': 'No file path provided'}), 400
    
    # In a real implementation, we would retrieve the file from the device
    # For this dummy implementation, we'll create a text file with dummy content
    
    # Get filename from path
    filename = file_path.split('/')[-1]
    
    temp_dir = current_app.config.get('TEMP_FOLDER', 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file_path = os.path.join(temp_dir, filename)
    
    # Create a dummy file with some content based on the file type
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    
    if ext in ['txt', 'log', 'md']:
        with open(temp_file_path, 'w') as f:
            f.write(f"This is a dummy text file for {filename}\n")
            f.write("In a real implementation, this would be the actual file content from the device.")
    else:
        # For binary files, create a small dummy file
        with open(temp_file_path, 'wb') as f:
            f.write(b'Dummy file content for demonstration purposes only.')
    
    return send_file(
        temp_file_path,
        as_attachment=True,
        download_name=filename
    )

@file_manager_command.route('/device/<device_id>/commands/file-manager/create-folder', methods=['POST'])
@auth_required
def create_folder(device_id):
    data = request.get_json()
    path = data.get('path', '/storage/emulated/0')
    folder_name = data.get('folderName', '')
    
    if not folder_name:
        return jsonify({'success': False, 'message': 'No folder name provided'}), 400
    
    # Create a dummy folder entry
    new_folder = {
        "name": folder_name,
        "type": "folder",
        "path": f"{path}/{folder_name}",
        "size": "-",
        "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "icon": "bi-folder-fill"
    }
    
    if path in DUMMY_FILES:
        DUMMY_FILES[path].append(new_folder)
        # Also create an empty file list for this new folder
        DUMMY_FILES[f"{path}/{folder_name}"] = []
    
    return jsonify({
        'success': True,
        'message': 'Folder created successfully',
        'folder': new_folder
    })

@file_manager_command.route('/device/<device_id>/commands/file-manager/delete', methods=['POST'])
@auth_required
def delete_file(device_id):
    data = request.get_json()
    file_path = data.get('path')

    if not file_path:
        return jsonify({'success': False, 'message': 'No file path provided'}), 400

    file_name = file_path.split('/')[-1]

    # Try forwarding to the device
    device = Device.query.get(device_id)
    if device:
        try:
            url = f"http://{device.device_ip}:8080/files/delete"
            resp = http_requests.post(url, json={'path': file_path}, timeout=8)
            if resp.ok:
                return jsonify({'success': True, 'message': f'"{file_name}" deleted successfully'})
        except Exception as e:
            logger.debug(f"File manager request failed: {e}")

    # Fallback: remove from dummy data
    parent_dir = '/'.join(file_path.split('/')[:-1])
    if parent_dir in DUMMY_FILES:
        DUMMY_FILES[parent_dir] = [f for f in DUMMY_FILES[parent_dir] if f['path'] != file_path]

    return jsonify({'success': True, 'message': f'"{file_name}" deleted successfully'})