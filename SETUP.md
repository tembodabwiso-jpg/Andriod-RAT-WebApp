# Android MDM WebApp — Setup Guide

## 1. Prerequisites

- Python 3.10+
- Android Studio (for building the Android client)
- A Firebase project (free tier works)

---

## 2. Backend Setup

```bash
# Clone and enter the project
cd Andriod-MDM-WebApp

# Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment file and edit it
copy .env.example .env     # Windows
# cp .env.example .env      # Linux/Mac
```

Edit `.env` and set:
- `SECRET_KEY` — any long random string
- `JWT_SECRET` — another random string (different from SECRET_KEY)
- `SQLALCHEMY_DATABASE_URI` — default SQLite is fine for dev (`sqlite:///app.db`)

### Initialize the Database

```bash
python init_db.py
```

This creates all tables. For subsequent model changes, use:
```bash
python init_db.py init      # one-time: create migrations folder
python init_db.py migrate   # generate migration after model changes
python init_db.py upgrade   # apply migrations
```

### Start All Servers

```bash
python run.py
```

This starts:
| Server           | Port | URL                    |
|-----------------|------|------------------------|
| User Dashboard  | 5000 | http://localhost:5000  |
| Admin Panel     | 5002 | http://localhost:5002  |
| API Server      | 8000 | http://localhost:8000  |
| Streaming       | 5001 | http://localhost:5001  |

---

## 3. Firebase Setup (for Push Notifications)

Firebase Cloud Messaging (FCM) enables instant command delivery to devices even when they're on mobile data or behind NAT. **This is optional** — without it, the system falls back to HTTP polling (every 30 seconds) and direct HTTP when devices are on the same network.

### Step 1: Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **Add project**
3. Name it (e.g., "MDM System")
4. Disable Google Analytics (not needed) or enable it — your choice
5. Click **Create project**

### Step 2: Add an Android App

1. In your Firebase project, click the **Android icon** to add an Android app
2. Package name: `com.mdm.client`
3. App nickname: "MDM Client"
4. Click **Register app**
5. Download `google-services.json`
6. Place it at: `android-client/app/google-services.json`

### Step 3: Get Server Credentials

1. In Firebase Console → **Project Settings** → **Service Accounts** tab
2. Click **Generate new private key**
3. Download the JSON file
4. Rename it to `firebase-credentials.json` and place it in the project root
5. In your `.env`, set:
   ```
   FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
   ```

### Step 4: Enable Cloud Messaging

1. In Firebase Console → **Cloud Messaging** (left sidebar under Build)
2. If prompted, enable the Cloud Messaging API
3. That's it — FCM is now active

### Verification

After starting the backend, check the console for:
```
Firebase Admin SDK initialized successfully
```

If you see `Firebase credentials not found, FCM disabled`, double-check your `FIREBASE_CREDENTIALS_PATH`.

---

## 4. Android Client Setup

See [`android-client/README.md`](android-client/README.md) for full build instructions, permissions, stealth mode, architecture, and supported commands.

---

## 5. Docker Setup (Alternative)

```bash
docker-compose up --build
```

This starts all servers in a single container with SQLite. For production, update `docker-compose.yml` to use MySQL/PostgreSQL.

---

## 6. Connecting Your First Device

1. Start the backend: `python run.py`
2. Install the Android app on your device
3. Enter your server's IP in the app setup screen
4. The app will auto-register with the API server
5. Open `http://localhost:5000/dashboard` — your device should appear
6. Click **View** on the device to access the command center

---

## 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| Device not appearing on dashboard | Check that the phone and server are on the same network. Verify the IP address in the app settings. |
| Commands not reaching device | Check if FCM is configured. Without FCM, commands are polled every 30 seconds. |
| "Firebase credentials not found" | Set `FIREBASE_CREDENTIALS_PATH` in `.env` to point to your downloaded service account JSON. |
| Android build fails with google-services error | Place `google-services.json` in `android-client/app/` or comment out the plugin if not using Firebase. |
| Database errors on startup | Run `python init_db.py` to create tables. |
| Port already in use | Another process is using that port. Kill it or change the port in the respective `app.py`. |
