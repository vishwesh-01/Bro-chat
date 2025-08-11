from flask import Flask, render_template_string
from flask_socketio import SocketIO, send

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'  # Change for production
socketio = SocketIO(app)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bro's-Chat Room</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
  <style>
    body { 
      font-family: system-ui, -apple-system, Arial, sans-serif; 
      margin: 0; 
      padding: 2rem; 
      display: flex; 
      justify-content: center; 
      align-items: center; 
      background: #ffffff; 
    }
    .container { 
      max-width: 1200px; 
      width: 100%; 
      display: flex; 
      flex-direction: column; 
      gap: 2rem; 
      position: relative;
      box-sizing: border-box;
    }
    .row { 
      display: flex; 
      gap: .5rem; 
      flex-wrap: wrap; 
      margin: .5rem 0; 
    }
    input, textarea, button { 
      padding: .5rem .6rem; 
      border: 2px solid #0f0f0f; 
      border-radius: 6px; 
    }
    textarea {
      width: 100%;           
      min-height: 120px;
      padding: .5rem .6rem;
      border: 2px solid #0f0f0f;
      border-radius: 6px;
      resize: vertical;
      flex: 1 1 auto;          
      min-width: 0;            
      box-sizing: border-box;  
    }
    button {
      background: #000000;            
      color: #ffffff;  
      font-weight: bold;                 
      border: 2px solid #000000;      
      border-radius: 6px;
      padding: .5rem 1rem;
      cursor: pointer;
      box-shadow: 0 2px 5px rgba(0,0,0,0.2);
      transition: transform 0.1s ease, box-shadow 0.1s ease;
    }
    button:hover { 
      transform: scale(1.05); 
      box-shadow: 0 4px 10px rgba(0,0,0,0.3); 
    }
    #messages { 
      list-style: none; 
      padding: 0; 
      margin: 0; 
      display: flex; 
      flex-direction: column; 
      gap: 1rem; 
      max-height: 500px; 
      overflow-y: auto; 
    }
    #messages li { 
      border: 1px solid #e5e5e5; 
      border-radius: 6px; 
      padding: 1rem; 
      background: #fafafa; 
    }
    .meta { 
      font-size: .85rem; 
      color: #666; 
      margin-bottom: .25rem; 
    }
    pre.msg {
      margin: 0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      white-space: pre-wrap;
      overflow: auto;
    }
    h1 {
      font-size: 2rem;
      margin: 0 0 1rem 0;
      padding: 0;
      font-weight: 600;
      text-align: left;
    }
    .input-section {
      display: flex;
      flex-direction: column;
      gap: 1rem;
      padding: 1rem;
      background: #f8f8f8;
      border-radius: 8px;
      box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .username-row {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: .5rem;
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      max-width: 300px;
      box-sizing: border-box;
    }
    #username {
      width: 85%;
      max-width: 85%;
      box-sizing: border-box;
    }
    .message-row {
      display: flex;
      flex-direction: column;
      gap: .5rem;
    }
    .send-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .send-row small {
      font-size: .85rem;
      color: #666;
    }
    .chat-content {
      width: 100%;
      max-width: 600px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
      margin-top: 6rem;
    }
    @media (max-width: 767px) {
      body { padding: 1rem; }
      .container { max-width: 100%; }
      .chat-content { max-width: 100%; margin-top: 7rem; }
      .username-row { 
        position: static; 
        max-width: 100%; 
        width: 100%; 
      }
      #username { max-width: 100%; }
    }
    @media (min-width: 768px) {
      .chat-content { max-width: 600px; }
      .username-row { max-width: 300px; }
    }
    @media (min-width: 1200px) {
      .container { max-width: 1400px; }
      .chat-content { max-width: 800px; }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="username-row">
      <h1>Bro's-Chat Room</h1>
      <input id="username" placeholder="Your name">
    </div>
    <div class="chat-content">
      <ul id="messages"></ul>
      <div class="input-section">
        <div class="message-row">
          <textarea id="myMessage" placeholder="Paste paragraph or multi-line code..."></textarea>
          <div class="send-row">
            <small>Press <strong>Enter</strong> to send • Press <strong>Shift+Enter</strong> for a new line</small>
            <button id="sendBtn">Send</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const socket = io();

    function sendMessage() {
      const name = document.getElementById('username').value.trim();
      const msg  = document.getElementById('myMessage').value; // keep exactly as typed
      if (!name || !msg.trim()) return;
      socket.send({ username: name, message: msg });
      document.getElementById('myMessage').value = '';
    }

    document.getElementById('sendBtn').onclick = sendMessage;

    // Enter sends, Shift+Enter inserts newline
    document.getElementById('myMessage').addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    socket.on('message', function(payload) {
      const li = document.createElement('li');

      const meta = document.createElement('div');
      meta.className = 'meta';
      meta.textContent = payload.username || 'Anonymous';
      li.appendChild(meta);

      const pre = document.createElement('pre');
      pre.className = 'msg';
      // Literal text only — no HTML conversion
      pre.textContent = payload.message || '';
      li.appendChild(pre);

      document.getElementById('messages').appendChild(li);
      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    });
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@socketio.on('message')
def handle_message(data):
    # Data stays untouched: preserve exact formatting
    username = (data or {}).get('username', 'Anonymous')
    msg = (data or {}).get('message', '')
    send({'username': username, 'message': msg}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)