#  Bro-Chat 

A real-time chat app built with **Flask** and **Socket.IO** — no database, no sign-up, just open and chat. Supports a public room, invite-only private rooms, file & photo sharing, and a live members list. Everything lives in a single Python file.

---

##  Features

- **Public Chat** — open to everyone who visits the link
- **Private Rooms** — create a room, get a 6-character code, share it with friends
- **File & Photo Sharing** — drag-and-drop or pick any file up to 50 MB (private rooms only)
- **Image Previews** — photos show inline with a click-to-zoom lightbox
- **Download Button** — every shared file has a direct download link
- **Copy Message** — hover any message and hit Copy to grab the text
- **Live Members Panel** — pull-down on the left shows who's online in real time
- **Zero Database** — everything is in memory; restarts clear all rooms and messages

---

##  Requirements

| Requirement | Version |
|---|---|
| Python | 3.8 or higher |
| pip | latest recommended |

---

##  Setup

### 1 — Get the files

Clone the repo or just download `chat.py` and `requirements.txt` into the same folder:

```bash
git clone <your-repo-url>
cd bro-chat
```

### 2 — Create a virtual environment (recommended)

```bash
python -m venv venv
```

Activate it:

```bash
# macOS / Linux
source venv/bin/activate

# Windows (Command Prompt)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## ▶ Running the App

```bash
python chat.py
```

Open your browser and go to:

```
http://localhost:5000
```

To let other people on your **local network** join, share your machine's local IP:

```
http://192.168.x.x:5000
```

> Find your local IP with `ipconfig` (Windows) or `ifconfig` / `ip a` (macOS/Linux)

---

##  Using Private Rooms

**Creating a room:**
1. Enter your name in the top-right field
2. Click the 🔒 **lock icon**
3. A 6-character room code is generated — copy it
4. Click **Create Room**
5. Share the code with whoever you want to invite

**Joining a room:**
1. Enter your name
2. Click the 🚪 **door icon**
3. Paste the room code and click **Join Room**

Once inside, you can switch between **Public** and **Private Room** tabs at any time. Click **Leave Room** to go back to the public chat.

---

## 📎 Sharing Files

File sharing is available in **private rooms only**.

- Click the **📎 File** button next to Send
- Pick any file up to **50 MB**
- Images appear as inline previews — click to zoom
- All files include a **⬇ Download** button

---

##  Configuration

Open `chat.py` and update these two lines before deploying:

```python
# Line 6 — change this to a long random string
app.config['SECRET_KEY'] = 'your-strong-secret-key-here'

# Bottom of file — disable debug mode in production
socketio.run(app, debug=False, host='0.0.0.0', port=5000)
```

---

##  Production Deployment

For a production server, use **Gunicorn** with the **eventlet** worker:

```bash
pip install gunicorn eventlet
gunicorn --worker-class eventlet -w 1 chat:app --bind 0.0.0.0:5000
```

> Use only **1 worker** (`-w 1`) — Socket.IO requires a single process unless you add a message queue like Redis.

For HTTPS and a custom domain, put **Nginx** in front as a reverse proxy.

---

##  Project Structure

```
bro-chat/
├── chat.py        # Entire app — Flask + SocketIO + HTML/CSS/JS
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

---

##  Limitations

| Limitation | Detail |
|---|---|
| No persistence | Messages and rooms vanish on server restart |
| No auth | Anyone with the URL can join the public room |
| Single process | Scaling requires a Redis message queue |
| File size | Capped at 50 MB per file (configurable) |
| HTTP only | Add Nginx + SSL cert for HTTPS |

---