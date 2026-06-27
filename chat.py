from flask import Flask, render_template_string
from flask_socketio import SocketIO, send, emit, join_room, leave_room
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, max_http_buffer_size=50 * 1024 * 1024)

rooms = {}           # room_code -> {members:{sid:name}, name:str, created_at:float}
public_members = {}  # sid -> name

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bro's-Chat Room</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      font-family: system-ui, -apple-system, Arial, sans-serif;
      margin: 0; padding: 0;
      background: #fff;
      min-height: 100vh;
    }

    /* ════════ APP SHELL ════════ */
    .app-shell {
      display: flex;
      flex-direction: column;
      height: 100vh;
      width: 100%;
    }

    /* ════════ TOP BAR ════════ */
    .top-bar {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      padding: 0.6rem 1.25rem;
      background: #fff;
      box-shadow: 0 1px 0 #e8e8e8;
      position: sticky;
      top: 0;
      z-index: 100;
      flex-shrink: 0;
    }

    /* LEFT: members pill + title */
    .top-bar-left {
      display: flex;
      align-items: center;
      gap: 0.65rem;
      padding-top: 0.2rem;
    }

    /* Members pill — exactly like screenshot: black rounded pill */
    .members-wrap { position: relative; }
    .members-toggle {
      background: #1a1a2e;
      color: #fff;
      border: none;
      border-radius: 20px;
      padding: 0.3rem 0.7rem;
      cursor: pointer;
      font-size: 0.8rem;
      font-weight: 700;
      display: flex; align-items: center; gap: 0.3rem;
      white-space: nowrap;
      transition: opacity 0.15s;
    }
    .members-toggle:hover { opacity: 0.85; }
    .members-toggle .arrow {
      font-size: 0.6rem;
      transition: transform 0.2s;
      display: inline-block;
    }
    .members-toggle.open .arrow { transform: rotate(180deg); }
    .members-dropdown {
      display: none;
      position: absolute;
      top: calc(100% + 6px);
      left: 0;
      background: #fff;
      border: 2px solid #111;
      border-radius: 8px;
      min-width: 180px;
      max-height: 260px;
      overflow-y: auto;
      z-index: 300;
      box-shadow: 0 6px 20px rgba(0,0,0,0.12);
    }
    .members-dropdown.open { display: block; }
    .members-dropdown-header {
      padding: 0.45rem 0.85rem;
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #888;
      border-bottom: 1px solid #eee;
    }
    .member-item {
      padding: 0.45rem 0.85rem;
      font-size: 0.86rem;
      display: flex; align-items: center; gap: 0.45rem;
      border-bottom: 1px solid #f5f5f5;
    }
    .member-item:last-child { border-bottom: none; }
    .member-dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: #22c55e;
      flex-shrink: 0;
    }
    .member-dot.you { background: #6366f1; }

    /* Title */
    h1 {
      font-size: 1.35rem;
      font-weight: 700;
      margin: 0;
      white-space: nowrap;
    }

    /* RIGHT: username + icons/tabs — single row, no column stacking */
    .top-bar-right {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-shrink: 0;
    }
    .top-bar-right-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    /* Username input — thin border, no radius (matches screenshot exactly) */
    #username {
      padding: 0.4rem 0.65rem;
      border: 1.5px solid #ccc;
      border-radius: 6px;
      font-size: 0.88rem;
      width: 140px;
      outline: none;
      transition: border-color 0.15s;
    }
    #username:focus { border-color: #888; }
    #username-priv {
      padding: 0.4rem 0.65rem;
      border: 1.5px solid #ccc;
      border-radius: 6px;
      font-size: 0.88rem;
      width: 140px;
      background: #fff;
      color: #111;
      opacity: 1;
    }

    /* Icon buttons — lock is black, door is tan/orange (matches screenshot) */
    .icon-btn {
      width: 36px; height: 36px;
      border-radius: 8px;
      border: none;
      display: flex; align-items: center; justify-content: center;
      cursor: pointer;
      font-size: 1rem;
      transition: transform 0.1s, opacity 0.1s;
      flex-shrink: 0;
    }
    .icon-btn:hover { transform: scale(1.08); opacity: 0.88; }
    .icon-btn.lock { background: #111; color: #fff; }
    .icon-btn.door { background: #c8a96e; color: #fff; }

    /* Segmented tabs: Public | Private Room — appear when in private room */
    .view-tabs { display: flex;}
    .view-tab {
      padding: 0.35rem 0.9rem;
      font-size: 0.82rem;
      font-weight: 700;
      border: 2px solid #111;
      cursor: pointer;
      background: #fff;
      color: #111;
      transition: background 0.12s, color 0.12s;
    }
    .view-tab:first-child { border-radius: 6px 0 0 6px; }
    .view-tab:last-child  { border-radius: 0 6px 6px 0; border-left: none; }
    .view-tab.active { background: #111; color: #fff; }

    /* Room banner — separate sticky strip BELOW top-bar, never inside it */
    .room-banner {
      display: none;
      position: fixed;
      top: 65px;          
      right: 20px;

      width: auto;
      max-width: 220px;

      padding: 4px 14px;
      border: 1px solid #86efac;
      border-radius: 12px;
      background: #f0fdf4;

      align-items: center;
      gap: 10px;

      font-size: 0.75rem;
      color: #15803d;
      z-index: 999;
    }

    .room-banner.visible { display: flex; }
    .room-code-badge {
      font-weight: 900;
      font-size: 14px;
      font-family: ui-monospace, monospace;
      letter-spacing: 0.4em;
      color: #16a34a;
    }
    .leave-room-btn {
      background: #111;
      color: #fff;
      border: none;
      border-radius: 12px;
      padding: 3px 10px;
      font-size: 0.75rem;
      font-weight: 700;
      cursor: pointer;
      transition: opacity 0.1s;
    }
    .leave-room-btn:hover { opacity: 0.8; }

    /* ════════ VIEWS ════════ */
    .view { display: none; }
    .view.active {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
    }

    /* ════════ CHAT BODY ════════
       Messages centred in ~760px column — matches screenshot exactly */
    .chat-body {
      flex: 1;
      overflow-y: auto;
      padding: 0.4rem 1.25rem; 
      display: flex;
      flex-direction: column;
      align-items: center;   /* horizontally centre the inner column */
    }
    .chat-inner {
      width: 100%;
      max-width: 760px;
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
    }

    /* ════════ MESSAGES ════════ */
    #messages, #priv-messages {
      list-style: none;
      padding: 0; margin: 0;
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
    }
    .msg-item {
      border: 1px solid #e8e8e8;
      border-radius: 8px;
      padding: 0.7rem 1rem;
      background: #fafafa;
      position: relative;
    }
    /* Meta: name · time — leave space for copy btn */
    .meta {
      font-size: 0.8rem;
      color: #888;
      margin-bottom: 0.2rem;
      padding-right: 3.8rem;
    }
    pre.msg {
      margin: 0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: pre-wrap;
      overflow-wrap: break-word;
      font-size: 0.88rem;
      color: #111;
    }

    /* Copy button — faded, appears on hover */
    .copy-btn {
      position: absolute;
      top: 0.5rem; right: 0.55rem;
      background: #e8e8e8;
      color: #555;
      border: none;
      border-radius: 4px;
      padding: 2px 8px;
      font-size: 0.7rem;
      cursor: pointer;
      opacity: 0.5;
      transition: opacity 0.15s, background 0.15s, color 0.15s;
      user-select: none;
    }
    .msg-item:hover .copy-btn { opacity: 1; }
    .copy-btn:hover { background: #111; color: #fff; }
    .copy-btn.copied { background: #22c55e; color: #fff; opacity: 1; }

    /* File messages — private only */
    .file-msg {
      display: flex;
      align-items: center;
      gap: 0.55rem;
      padding: 0.25rem 0;
      flex-wrap: wrap;
    }
    .file-icon { font-size: 1.2rem; flex-shrink: 0; }
    .file-link {
      color: #111;
      font-weight: 600;
      text-decoration: underline;
      font-size: 0.86rem;
      word-break: break-all;
    }
    .dl-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.2rem;
      background: #111;
      color: #fff;
      border: none;
      border-radius: 4px;
      padding: 2px 9px;
      font-size: 0.73rem;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
      flex-shrink: 0;
      transition: opacity 0.1s;
    }
    .dl-btn:hover { opacity: 0.8; }
    .img-preview {
      max-width: 100%;
      max-height: 220px;
      border-radius: 6px;
      border: 1px solid #e8e8e8;
      margin-top: 0.4rem;
      display: block;
      cursor: zoom-in;
    }

    /* System messages */
    .sys-msg {
      text-align: center;
      font-size: 0.75rem;
      color: #aaa;
      padding: 0;
      margin-top: 0;
      margin-bottom: 0.2rem;
    }

    /* ════════ INPUT SECTION ════════
       White page bg, card centered with grey fill + rounded corners */
    .input-section {
      padding: 1rem 1.25rem 1.25rem;
      background: #fff;          /* page is white, card is grey */
      flex-shrink: 0;
      display: flex;
      justify-content: center;
    }
    /* The grey rounded card — matches screenshot exactly */
    .input-inner {
      width: 100%;
      max-width: 760px;
      background: #f2f2f2;
      border-radius: 14px;
      padding: 0.85rem 1rem 0.85rem;
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
    }
    textarea {
      width: 100%;
      min-height: 80px;
      padding: 0.55rem 0.75rem;
      border: 1.5px solid #d8d8d8;
      border-radius: 10px;
      resize: vertical;
      font-size: 0.9rem;
      font-family: inherit;
      background: #fff;
      outline: none;
      transition: border-color 0.15s;
      color: #111;
    }
    textarea:focus { border-color: #999; }
    .send-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
    }
    .send-row small { font-size: 0.78rem; color: #888; }
    .send-row-btns { display: flex; align-items: center; gap: 0.5rem; }

    /* Send button — solid black, matches screenshot */
    .send-btn {
      background: #111;
      color: #fff;
      font-weight: 700;
      border: none;
      border-radius: 6px;
      padding: 0.48rem 1.1rem;
      cursor: pointer;
      font-size: 0.88rem;
      transition: opacity 0.1s, transform 0.1s;
    }
    .send-btn:hover { opacity: 0.85; transform: scale(1.03); }

    /* File label — private room only */
    .file-label {
      background: #fff;
      color: #111;
      font-weight: 700;
      border: 1.5px solid #111;
      border-radius: 6px;
      padding: 0.42rem 0.8rem;
      cursor: pointer;
      font-size: 0.86rem;
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      transition: opacity 0.1s;
    }
    .file-label:hover { opacity: 0.75; }
    #file-input-priv { display: none; }

    /* Upload notice */
    .upload-notice {
      font-size: 0.75rem;
      color: #aaa;
      text-align: right;
      min-height: 1em;
    }

    /* ════════ MODALS ════════ */
    .modal-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.45);
      z-index: 500;
      align-items: center;
      justify-content: center;
    }
    .modal-overlay.open { display: flex; }
    .modal {
      background: #fff;
      border: 2px solid #111;
      border-radius: 10px;
      padding: 1.75rem;
      max-width: 380px;
      width: calc(100% - 2rem);
      display: flex;
      flex-direction: column;
      gap: 1rem;
      box-shadow: 0 10px 40px rgba(0,0,0,0.2);
    }
    .modal h2 { margin: 0; font-size: 1.2rem; font-weight: 700; }
    .modal label {
      font-size: 0.78rem;
      font-weight: 700;
      display: block;
      margin-bottom: 0.25rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #555;
    }
    .modal input {
      width: 100%;
      padding: 0.48rem 0.65rem;
      border: 1.5px solid #ccc;
      border-radius: 6px;
      font-size: 0.92rem;
      outline: none;
    }
    .modal input:focus { border-color: #888; }
    .modal-desc { font-size: 0.83rem; color: #666; margin: 0; }
    .modal-btns { display: flex; gap: 0.5rem; justify-content: flex-end; }
    .modal-cancel {
      background: #fff; color: #111;
      border: 1.5px solid #111; border-radius: 6px;
      padding: 0.4rem 0.9rem; cursor: pointer;
      font-weight: 700; font-size: 0.86rem;
    }
    .modal-confirm {
      background: #111; color: #fff;
      border: 1.5px solid #111; border-radius: 6px;
      padding: 0.4rem 0.9rem; cursor: pointer;
      font-weight: 700; font-size: 0.86rem;
      transition: opacity 0.1s;
    }
    .modal-confirm:hover { opacity: 0.82; }
    .modal-error { color: #dc2626; font-size: 0.8rem; margin: 0; display: none; }
    .modal-error.visible { display: block; }
    .generated-code {
      display: none;
      background: #f0fdf4;
      border: 1.5px solid #86efac;
      border-radius: 6px;
      padding: 0.55rem 0.85rem;
      font-family: ui-monospace, monospace;
      font-size: 1.15rem;
      font-weight: 900;
      letter-spacing: 0.14em;
      text-align: center;
      color: #16a34a;
    }
    .generated-code.visible { display: block; }
    .copy-code-btn {
      background: #111; color: #fff;
      border: none; border-radius: 5px;
      padding: 4px 12px; font-size: 0.76rem;
      cursor: pointer; font-weight: 700;
      align-self: center; transition: opacity 0.1s;
    }
    .copy-code-btn:hover { opacity: 0.8; }

    /* ════════ LIGHTBOX ════════ */
    #lightbox {
      display: none;
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.88);
      z-index: 600;
      align-items: center; justify-content: center;
      cursor: zoom-out;
    }
    #lightbox.open { display: flex; }
    #lightbox-img {
      max-width: 92vw; max-height: 90vh;
      border-radius: 8px; border: 3px solid #fff;
      pointer-events: none;
    }

    /* ════════ RESPONSIVE ════════ */
    @media (max-width: 600px) {
      h1 { font-size: 1rem; }
      #username { width: 90px; }
      .top-bar { padding: 0 0.75rem; }
      .chat-body { padding: 1rem 0.75rem; }
      .input-section { padding: 0.75rem; }
    }
  </style>
</head>
<body>
<div class="app-shell">

  <!-- ════════════════════════ TOP BAR ════════════════════════ -->
  <div class="top-bar">

    <!-- LEFT: members + title -->
    <div class="top-bar-left">
      <div class="members-wrap" id="members-wrap">
        <button class="members-toggle" id="members-toggle" onclick="toggleMembers()">
          👥 <span id="member-count">1</span> <span class="arrow">▼</span>
        </button>
        <div class="members-dropdown" id="members-dropdown">
          <div class="members-dropdown-header">Online Members</div>
          <div id="members-list"></div>
        </div>
      </div>
      <h1 id="chat-title">Bro's-Chat Room</h1>
    </div>

    <!-- RIGHT: single row — swaps between public icons and private tabs -->
    <div class="top-bar-right">
      <div class="top-bar-right-row" id="row-public">
        <input id="username" placeholder="Your name" maxlength="20">
        <button class="icon-btn lock" title="Create private room" onclick="openCreateModal()">🔒</button>
        <button class="icon-btn door" title="Join private room"   onclick="openJoinModal()">🚪</button>
      </div>
      <div class="top-bar-right-row" id="row-private" style="display:none;">
        <input id="username-priv" placeholder="Your name" maxlength="20">
        <div class="view-tabs">
          <button class="view-tab active" id="tab-public"  onclick="switchView('public')">Public</button>
          <button class="view-tab"        id="tab-private" onclick="switchView('private')">Private Room</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Room banner — separate strip below top-bar, never pushes top-bar -->
  <div class="room-banner" id="room-banner">
    Private Room: <span class="room-code-badge" id="banner-code"></span>
    <button class="leave-room-btn" onclick="leaveRoom()">Leave Room</button>
  </div>

  <!-- ════════════════════════ PUBLIC VIEW ════════════════════════ -->
  <div class="view active" id="view-public">
    <div class="chat-body" id="public-body">
      <div class="chat-inner">
        <ul id="messages"></ul>
      </div>
    </div>
    <div class="input-section">
      <div class="input-inner">
        <textarea id="myMessage" placeholder="Paste paragraph or multi-line code..."></textarea>
        <div class="send-row">
          <small>Press <strong>Enter</strong> to send • <strong>Shift+Enter</strong> for new line</small>
          <button class="send-btn" id="sendBtn">Send</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ════════════════════════ PRIVATE VIEW ════════════════════════ -->
  <div class="view" id="view-private">
    <div class="chat-body" id="private-body">
      <div class="chat-inner">
        <ul id="priv-messages"></ul>
      </div>
    </div>
    <div class="input-section">
      <div class="input-inner">
        <textarea id="privMessage" placeholder="Message your private room..."></textarea>
        <div class="send-row">
          <small>Press <strong>Enter</strong> to send • <strong>Shift+Enter</strong> for new line</small>
          <div class="send-row-btns">
            <label class="file-label" for="file-input-priv">📎 File</label>
            <input type="file" id="file-input-priv" accept="*/*" onchange="handleFileUpload(this)">
            <button class="send-btn" id="privSendBtn">Send</button>
          </div>
        </div>
        <div class="upload-notice" id="priv-upload-notice"></div>
      </div>
    </div>
  </div>

</div><!-- /.app-shell -->

<!-- ════════════════════════ CREATE ROOM MODAL ════════════════════════ -->
<div class="modal-overlay" id="modal-create">
  <div class="modal">
    <h2>🔒 Create Private Room</h2>
    <p class="modal-desc">A unique room code will be generated. Share it with friends so they can join.</p>
    <div>
      <label for="create-name">Room Name (optional)</label>
      <input id="create-name" placeholder="e.g. Project Alpha" maxlength="30">
    </div>
    <div class="generated-code" id="generated-code-box"></div>
    <button class="copy-code-btn" id="copy-gen-code-btn" style="display:none;" onclick="copyGeneratedCode()">Copy Code</button>
    <p class="modal-error" id="create-error"></p>
    <div class="modal-btns">
      <button class="modal-cancel" onclick="closeModal('modal-create')">Cancel</button>
      <button class="modal-confirm" onclick="createRoom()">Create Room</button>
    </div>
  </div>
</div>

<!-- ════════════════════════ JOIN ROOM MODAL ════════════════════════ -->
<div class="modal-overlay" id="modal-join">
  <div class="modal">
    <h2>🚪 Join Private Room</h2>
    <p class="modal-desc">Enter the room code shared by your friend to join their private room.</p>
    <div>
      <label for="join-code">Room Code</label>
      <input id="join-code" placeholder="e.g. XKCD42" maxlength="10" style="text-transform:uppercase;">
    </div>
    <p class="modal-error" id="join-error"></p>
    <div class="modal-btns">
      <button class="modal-cancel" onclick="closeModal('modal-join')">Cancel</button>
      <button class="modal-confirm" onclick="joinRoom()">Join Room</button>
    </div>
  </div>
</div>

<!-- ════════════════════════ LIGHTBOX ════════════════════════ -->
<div id="lightbox" onclick="closeLightbox()">
  <img id="lightbox-img" src="" alt="Preview">
</div>

<script>
  // ─── STATE ────────────────────────────────────────
  const socket = io();
  var currentRoom    = null;
  var currentView    = 'public';
  var publicMembers  = {};
  var privateMembers = {};
  var pendingRoomCode = null;

  // ─── HELPERS ──────────────────────────────────────
  function getUsername() {
    return document.getElementById('username').value.trim() || 'Anonymous';
  }
  function syncPrivUsername() {
    // keep the read-only display in sync
    document.getElementById('username-priv').value = getUsername();
  }

  function generateCode() {
    var chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    var code = '';
    for (var i = 0; i < 6; i++) code += chars[Math.floor(Math.random() * chars.length)];
    return code;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function ts() {
    var d = new Date();
    return d.getHours().toString().padStart(2,'0') + ':' + d.getMinutes().toString().padStart(2,'0');
  }

  function scrollBottom(el) { el.scrollTop = el.scrollHeight; }

  function setNotice(id, msg) {
    var el = document.getElementById(id);
    if (el) el.textContent = msg;
  }

  // ─── CLIPBOARD ────────────────────────────────────
  function copyMessage(btn, text) {
    function done() {
      btn.textContent = '✓ Copied';
      btn.classList.add('copied');
      setTimeout(function() { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1800);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(function() { fbCopy(text, done); });
    } else { fbCopy(text, done); }
  }
  function fbCopy(text, cb) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0;';
    document.body.appendChild(ta); ta.focus(); ta.select();
    try { document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta);
    if (cb) cb();
  }
  function copyGeneratedCode() {
    if (!pendingRoomCode) return;
    var btn = document.getElementById('copy-gen-code-btn');
    var mark = function() { btn.textContent='✓ Copied!'; setTimeout(function(){ btn.textContent='Copy Code'; },1800); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(pendingRoomCode).then(mark).catch(function(){ fbCopy(pendingRoomCode,mark); });
    } else { fbCopy(pendingRoomCode,mark); }
  }

  // ─── MESSAGE BUILDERS ─────────────────────────────
  function createMsgLi(username, message) {
    var li  = document.createElement('li');
    li.className = 'msg-item';

    var btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.onclick = function() { copyMessage(this, message); };
    li.appendChild(btn);

    var meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = escapeHtml(username) + ' · ' + ts();
    li.appendChild(meta);

    var pre = document.createElement('pre');
    pre.className = 'msg';
    pre.textContent = message;
    li.appendChild(pre);
    return li;
  }

  function createFileLi(username, fileName, fileData, mimeType) {
    var li = document.createElement('li');
    li.className = 'msg-item';

    var meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = escapeHtml(username) + ' · ' + ts();
    li.appendChild(meta);

    var isImg = mimeType && mimeType.startsWith('image/');
    var icon  = isImg ? '🖼️'
      : (mimeType && mimeType.includes('pdf'))   ? '📄'
      : (mimeType && mimeType.includes('zip'))   ? '🗜️'
      : (mimeType && mimeType.includes('video')) ? '🎥'
      : (mimeType && mimeType.includes('audio')) ? '🎵' : '📁';

    var row = document.createElement('div');
    row.className = 'file-msg';

    var ic = document.createElement('span');
    ic.className = 'file-icon'; ic.textContent = icon;
    row.appendChild(ic);

    var lnk = document.createElement('a');
    lnk.className = 'file-link'; lnk.href = fileData;
    lnk.download = fileName; lnk.textContent = fileName;
    row.appendChild(lnk);

    var dl = document.createElement('a');
    dl.className = 'dl-btn'; dl.href = fileData;
    dl.download = fileName; dl.textContent = '⬇ Download';
    row.appendChild(dl);

    li.appendChild(row);

    if (isImg) {
      var img = document.createElement('img');
      img.className = 'img-preview'; img.src = fileData; img.alt = fileName;
      img.onclick = function() { openLightbox(this.src); };
      li.appendChild(img);
    }
    return li;
  }

  function createSysLi(text) {
    var li = document.createElement('li');
    li.className = 'sys-msg'; li.textContent = text;
    return li;
  }

  function appendPublic(li) {
    document.getElementById('messages').appendChild(li);
    scrollBottom(document.getElementById('public-body'));
  }
  function appendPrivate(li) {
    document.getElementById('priv-messages').appendChild(li);
    scrollBottom(document.getElementById('private-body'));
  }

  // ─── PUBLIC CHAT ──────────────────────────────────
  function sendPublicMessage() {
    var msg = document.getElementById('myMessage').value;
    if (!msg.trim()) return;
    socket.send({ username: getUsername(), message: msg });
    document.getElementById('myMessage').value = '';
  }
  document.getElementById('sendBtn').onclick = sendPublicMessage;
  document.getElementById('myMessage').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendPublicMessage(); }
  });

  socket.on('message', function(p) {
    if (!p) return;
    if (p.type === 'system')  appendPublic(createSysLi(p.message));
    else appendPublic(createMsgLi(p.username || 'Anonymous', p.message || ''));
  });

  // ─── PRIVATE CHAT ─────────────────────────────────
  function sendPrivateMessage() {
    if (!currentRoom) return;
    var msg = document.getElementById('privMessage').value;
    if (!msg.trim()) return;
    socket.emit('private_message', { room: currentRoom, username: getUsername(), message: msg });
    document.getElementById('privMessage').value = '';
  }
  document.getElementById('privSendBtn').onclick = sendPrivateMessage;
  document.getElementById('privMessage').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendPrivateMessage(); }
  });

  socket.on('private_message', function(p) {
    if (!p) return;
    if (p.type === 'system')     appendPrivate(createSysLi(p.message));
    else if (p.type === 'file')  appendPrivate(createFileLi(p.username||'Anonymous', p.fileName, p.fileData, p.mimeType));
    else                         appendPrivate(createMsgLi(p.username||'Anonymous', p.message||''));
  });

  // ─── FILE UPLOAD (private only) ───────────────────
  function handleFileUpload(input) {
    var file = input.files[0];
    if (!file) return;
    if (file.size > 50*1024*1024) { alert('File too large. Max 50 MB.'); input.value=''; return; }
    setNotice('priv-upload-notice', 'Uploading ' + file.name + '…');
    var reader = new FileReader();
    reader.onload = function(e) {
      socket.emit('private_file', {
        room: currentRoom, username: getUsername(),
        fileName: file.name, fileData: e.target.result,
        mimeType: file.type || 'application/octet-stream'
      });
      setNotice('priv-upload-notice', '');
    };
    reader.onerror = function() { setNotice('priv-upload-notice', 'Failed to read file.'); };
    reader.readAsDataURL(file);
    input.value = '';
  }

  socket.on('private_file', function(p) {
    if (!p) return;
    appendPrivate(createFileLi(p.username||'Anonymous', p.fileName, p.fileData, p.mimeType));
  });

  // ─── MEMBERS ──────────────────────────────────────
  function toggleMembers() {
    document.getElementById('members-toggle').classList.toggle('open');
    document.getElementById('members-dropdown').classList.toggle('open');
  }
  document.addEventListener('click', function(e) {
    if (!document.getElementById('members-wrap').contains(e.target)) {
      document.getElementById('members-toggle').classList.remove('open');
      document.getElementById('members-dropdown').classList.remove('open');
    }
  });
  function renderMembers(obj) {
    var myName = getUsername();
    var list   = document.getElementById('members-list');
    var entries = Object.entries(obj || {});
    document.getElementById('member-count').textContent = entries.length;
    list.innerHTML = '';
    entries.forEach(function(e) {
      var name = e[1], isYou = (name === myName);
      var div = document.createElement('div'); div.className = 'member-item';
      var dot = document.createElement('span'); dot.className = 'member-dot'+(isYou?' you':'');
      var lbl = document.createElement('span'); lbl.textContent = name+(isYou?' (you)':'');
      div.appendChild(dot); div.appendChild(lbl); list.appendChild(div);
    });
  }
  socket.on('public_members', function(m) {
    publicMembers = m || {};
    if (currentView === 'public') renderMembers(publicMembers);
  });
  socket.on('private_members', function(m) {
    privateMembers = m || {};
    if (currentView === 'private') renderMembers(privateMembers);
  });

  // ─── VIEW SWITCHING ───────────────────────────────
  function switchView(v) {
    currentView = v;
    document.getElementById('view-public').classList.toggle('active', v==='public');
    document.getElementById('view-private').classList.toggle('active', v==='private');
    document.getElementById('tab-public').classList.toggle('active', v==='public');
    document.getElementById('tab-private').classList.toggle('active', v==='private');
    if (v==='public') {
      document.getElementById('chat-title').textContent = "Bro's-Chat Room";
      renderMembers(publicMembers);
    } else {
      document.getElementById('chat-title').textContent = 'Room ' + currentRoom;
      renderMembers(privateMembers);
    }
  }

  // ─── CREATE ROOM ──────────────────────────────────
  function openCreateModal() {
    pendingRoomCode = generateCode();
    document.getElementById('create-name').value = '';
    document.getElementById('generated-code-box').textContent = pendingRoomCode;
    document.getElementById('generated-code-box').classList.add('visible');
    document.getElementById('copy-gen-code-btn').style.display = 'inline-block';
    document.getElementById('create-error').classList.remove('visible');
    document.getElementById('create-error').textContent = '';
    document.getElementById('modal-create').classList.add('open');
  }
  function closeModal(id) { document.getElementById(id).classList.remove('open'); }

  function createRoom() {
    var name = getUsername();
    if (!name || name === 'Anonymous') { showErr('create-error','Enter your name first.'); return; }
    var roomName = document.getElementById('create-name').value.trim() || ('Room '+pendingRoomCode);
    socket.emit('create_room', { room: pendingRoomCode, username: name, roomName: roomName });
    closeModal('modal-create');
  }
  socket.on('room_created', function(d) { if(d) enterPrivateRoom(d.room, d.roomName); });

  // ─── JOIN ROOM ────────────────────────────────────
  function openJoinModal() {
    document.getElementById('join-code').value = '';
    document.getElementById('join-error').classList.remove('visible');
    document.getElementById('join-error').textContent = '';
    document.getElementById('modal-join').classList.add('open');
    setTimeout(function(){ document.getElementById('join-code').focus(); }, 100);
  }
  function joinRoom() {
    var name = getUsername();
    if (!name || name === 'Anonymous') { showErr('join-error','Enter your name first.'); return; }
    var code = document.getElementById('join-code').value.trim().toUpperCase();
    if (!code) { showErr('join-error','Enter a room code.'); return; }
    socket.emit('join_room', { room: code, username: name });
  }
  document.getElementById('join-code').addEventListener('keydown', function(e) {
    if (e.key==='Enter') joinRoom();
  });
  function showErr(id, msg) {
    var el=document.getElementById(id); el.textContent=msg; el.classList.add('visible');
  }
  socket.on('room_joined', function(d) {
    if (!d) return;
    closeModal('modal-join');
    privateMembers = d.members || {};
    enterPrivateRoom(d.room, d.roomName);
  });
  socket.on('room_error', function(d) {
    showErr('join-error', (d&&d.message)||'Unknown error.');
  });

  // ─── ENTER / LEAVE ROOM ───────────────────────────
  function enterPrivateRoom(code, roomName) {
    currentRoom = code;
    // Show private-mode top-bar row, hide public-mode row
    document.getElementById('row-public').style.display  = 'none';
    document.getElementById('row-private').style.display = 'flex';
    // Mirror username into the read-only display
    syncPrivUsername();
    // Show room banner
    document.getElementById('banner-code').textContent = code;
    document.getElementById('room-banner').classList.add('visible');
    // Clear private messages and switch view
    document.getElementById('priv-messages').innerHTML = '';
    switchView('private');
  }

  function leaveRoom() {
    if (!currentRoom) return;
    socket.emit('leave_room', { room: currentRoom, username: getUsername() });
    currentRoom    = null;
    privateMembers = {};
    // Restore public-mode top-bar row
    document.getElementById('row-public').style.display  = 'flex';
    document.getElementById('row-private').style.display = 'none';
    document.getElementById('room-banner').classList.remove('visible');
    document.getElementById('priv-messages').innerHTML = '';
    switchView('public');
  }

  // ─── LIGHTBOX ─────────────────────────────────────
  function openLightbox(src) {
    document.getElementById('lightbox-img').src = src;
    document.getElementById('lightbox').classList.add('open');
  }
  function closeLightbox() {
    document.getElementById('lightbox').classList.remove('open');
    setTimeout(function(){ document.getElementById('lightbox-img').src=''; }, 200);
  }

  // ─── KEYBOARD SHORTCUTS ───────────────────────────
  document.addEventListener('keydown', function(e) {
    if (e.key==='Escape') { closeModal('modal-create'); closeModal('modal-join'); closeLightbox(); }
  });
  ['modal-create','modal-join'].forEach(function(id) {
    document.getElementById(id).addEventListener('click', function(e) {
      if (e.target===this) closeModal(id);
    });
  });

  // ─── SOCKET LIFECYCLE ─────────────────────────────
  socket.on('connect', function() {
    socket.emit('announce', { username: getUsername() });
  });
  document.getElementById('username').addEventListener('change', function() {
    socket.emit('announce', { username: getUsername() });
    syncPrivUsername();
    if (currentView==='public') renderMembers(publicMembers);
    else renderMembers(privateMembers);
  });
</script>
</body>
</html>
"""

# ─── FLASK ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(HTML)

# ─── PUBLIC ──────────────────────────────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    from flask import request
    public_members[request.sid] = 'Anonymous'
    emit('public_members', public_members, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    from flask import request
    sid = request.sid
    public_members.pop(sid, None)
    emit('public_members', public_members, broadcast=True)
    for code, rd in list(rooms.items()):
        if sid in rd['members']:
            uname = rd['members'].pop(sid, 'Someone')
            if not rd['members']:
                del rooms[code]
            else:
                emit('private_message', {'type':'system','message':f'{uname} left the room.'}, room=code)
                emit('private_members', rd['members'], room=code)
            break

@socketio.on('announce')
def handle_announce(data):
    from flask import request
    name = str((data or {}).get('username','Anonymous'))[:20].strip() or 'Anonymous'
    public_members[request.sid] = name
    emit('public_members', public_members, broadcast=True)

@socketio.on('message')
def handle_message(data):
    username = str((data or {}).get('username','Anonymous'))[:20]
    msg = str((data or {}).get('message',''))
    if not msg.strip(): return
    send({'username': username, 'message': msg}, broadcast=True)

# ─── PRIVATE ROOMS ───────────────────────────────────────────────────────────
@socketio.on('create_room')
def handle_create_room(data):
    from flask import request
    code      = str((data or {}).get('room','')).upper()[:10].strip()
    username  = str((data or {}).get('username','Anonymous'))[:20]
    room_name = str((data or {}).get('roomName',f'Room {code}'))[:40]
    if not code: return
    rooms[code] = {'members':{request.sid:username},'name':room_name,'created_at':time.time()}
    join_room(code)
    emit('room_created', {'room':code,'roomName':room_name})
    emit('private_members', rooms[code]['members'], room=code)
    emit('private_message', {'type':'system','message':f'{username} created the room. Share code: {code}'}, room=code)

@socketio.on('join_room')
def handle_join_room(data):
    from flask import request
    code     = str((data or {}).get('room','')).upper()[:10].strip()
    username = str((data or {}).get('username','Anonymous'))[:20]
    if not code or code not in rooms:
        emit('room_error', {'message':f'Room "{code}" not found. Check the code and try again.'})
        return
    rooms[code]['members'][request.sid] = username
    join_room(code)
    emit('room_joined', {'room':code,'roomName':rooms[code]['name'],'members':rooms[code]['members']})
    emit('private_members', rooms[code]['members'], room=code)
    emit('private_message', {'type':'system','message':f'{username} joined the room.'}, room=code)

@socketio.on('leave_room')
def handle_leave_room(data):
    from flask import request
    code     = str((data or {}).get('room','')).upper()
    username = str((data or {}).get('username','Anonymous'))
    if code not in rooms: return
    rooms[code]['members'].pop(request.sid, None)
    leave_room(code)
    if not rooms[code]['members']:
        del rooms[code]
    else:
        emit('private_message', {'type':'system','message':f'{username} left the room.'}, room=code)
        emit('private_members', rooms[code]['members'], room=code)

@socketio.on('private_message')
def handle_private_message(data):
    code     = str((data or {}).get('room','')).upper()
    username = str((data or {}).get('username','Anonymous'))[:20]
    msg      = str((data or {}).get('message',''))
    if not msg.strip() or code not in rooms: return
    emit('private_message', {'username':username,'message':msg}, room=code)

@socketio.on('private_file')
def handle_private_file(data):
    code      = str((data or {}).get('room','')).upper()
    username  = str((data or {}).get('username','Anonymous'))[:20]
    file_name = str((data or {}).get('fileName','file'))[:200]
    file_data = (data or {}).get('fileData','')
    mime_type = str((data or {}).get('mimeType','application/octet-stream'))
    if not code or code not in rooms: return
    emit('private_file', {'username':username,'fileName':file_name,'fileData':file_data,'mimeType':mime_type}, room=code)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)