from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='sayfalar')
app.secret_key = 'supersecretkey'
socketio = SocketIO(app, cors_allowed_origins="*")

DB_NAME = 'chat_app.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_NAME, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db



@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        password_confirm = request.form['password_confirm']
        avatar = request.form.get('avatar', 'default_avatar.png')

        if not username:
            return render_template('register.html', error='Kullanıcı adı boş olamaz.')
        if password != password_confirm:
            return render_template('register.html', error='Parolalar eşleşmiyor.')

        db = get_db()
        cursor = db.cursor()
        try:
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, password, avatar) VALUES (?, ?, ?)",
                (username, hashed_password, avatar)
            )
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Kullanıcı adı zaten alınmış.')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            return redirect(url_for('friends'))
        else:
            return render_template('login.html', error='Geçersiz kullanıcı adı veya parola.')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/friends')
@login_required
def friends():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (session['username'],))
    user = cursor.fetchone()
    if not user:
        return redirect(url_for('logout'))
    user_id = user['id']

    cursor.execute("""
        SELECT u.username FROM users u
        JOIN arkadasliklar a ON (
            (a.gonderen_id = ? AND a.alici_id = u.id) OR (a.alici_id = ? AND a.gonderen_id = u.id)
        )
        WHERE a.durum = 'kabul'
    """, (user_id, user_id))
    friends = [row['username'] for row in cursor.fetchall()]

    # Kullanıcının avatarını çek
    cursor.execute("SELECT avatar FROM users WHERE username = ?", (session['username'],))
    user_avatar = cursor.fetchone()
    avatar = user_avatar['avatar'] if user_avatar and 'avatar' in user_avatar else '1.png'  # Varsayılan avatar

    return render_template('friends.html', friends=friends, username=session['username'], avatar=avatar)
@app.route('/chat/<friend>')
@login_required
def chat_room(friend):
    db = get_db()
    cursor = db.cursor()

    # Kendi avatarını al
    cursor.execute("SELECT avatar FROM users WHERE username = ?", (session['username'],))
    user_avatar = cursor.fetchone()
    if not user_avatar or not user_avatar['avatar']:
        user_avatar = {'avatar': '1.png'}  # Varsayılan avatar dosya adı

    # Arkadaşının avatarını al
    cursor.execute("SELECT avatar FROM users WHERE username = ?", (friend,))
    friend_avatar = cursor.fetchone()
    if not friend_avatar or not friend_avatar['avatar']:
        friend_avatar = {'avatar': '1.png'}

    # Burada 'caller_avatar' değişkenini tanımla (örneğin, varsayılan olarak friend_avatar yapabilirsin)
    caller_avatar = friend_avatar['avatar']

    return render_template(
        'chat.html',
        username=session['username'],
        friend=friend,
        avatar=user_avatar['avatar'],
        friend_avatar=friend_avatar['avatar'],
        caller_avatar=caller_avatar  # Bu satırı ekledik
    )
@app.route('/messages')
@login_required
def get_messages():
    current_user = session['username']
    friend = request.args.get('friend')
    if not friend:
        return jsonify({"messages": []})

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
    user1 = cursor.fetchone()
    cursor.execute("SELECT id FROM users WHERE username = ?", (friend,))
    user2 = cursor.fetchone()

    if not user1 or not user2:
        return jsonify({"messages": []})

    user1_id = user1['id']
    user2_id = user2['id']

    cursor.execute("""
        SELECT u.username as sender_name, u.avatar as sender_avatar, m.message, m.timestamp, m.okundu 
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.timestamp ASC
    """, (user1_id, user2_id, user2_id, user1_id))

    rows = cursor.fetchall()
    messages = []
    for r in rows:
        messages.append({
            "sender_name": r["sender_name"],
            "sender_avatar": r["sender_avatar"],
            "message": r["message"],
            "timestamp": r["timestamp"],
            "okundu": bool(r["okundu"])
        })

    return jsonify({"messages": messages})

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Dosya bulunamadı"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Dosya ismi boş"}), 400

    filename = secure_filename(file.filename)

    upload_path = os.path.join(os.path.dirname(__file__), 'static/uploads')
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)

    filepath = os.path.join(upload_path, filename)
    file.save(filepath)

    file_url = url_for('static', filename=f'uploads/{filename}')
    return jsonify({"file_url": file_url})

@app.route('/add_friend', methods=['GET', 'POST'])
@login_required
def add_friend():
    if request.method == 'POST':
        friend_username = request.form.get('friend_username')
        if friend_username == session['username']:
            return render_template('add_friend.html', error='Kendinize arkadaş ekleyemezsiniz.')

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (session['username'],))
        user = cursor.fetchone()
        if not user:
            return redirect(url_for('logout'))
        user_id = user['id']

        cursor.execute("SELECT id FROM users WHERE username = ?", (friend_username,))
        friend = cursor.fetchone()
        if not friend:
            return render_template('add_friend.html', error='Kullanıcı bulunamadı.')

        friend_id = friend['id']

        try:
            cursor.execute("""
                INSERT INTO arkadasliklar (gonderen_id, alici_id, durum)
                VALUES (?, ?, 'beklemede')
            """, (user_id, friend_id))
            db.commit()
            return render_template('add_friend.html', success='Arkadaşlık isteği gönderildi.')
        except sqlite3.IntegrityError:
            return render_template('add_friend.html', error='Zaten istek gönderilmiş veya zaten arkadaşsınız.')

    return render_template('add_friend.html')


@app.route('/friend_requests')
@login_required
def friend_requests():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (session['username'],))
    user = cursor.fetchone()
    if not user:
        return redirect(url_for('logout'))
    user_id = user['id']

    cursor.execute("""
        SELECT u.username FROM users u
        JOIN arkadasliklar a ON a.gonderen_id = u.id
        WHERE a.alici_id = ? AND a.durum = 'beklemede'
    """, (user_id,))

    requests = [row['username'] for row in cursor.fetchall()]
    return render_template('friend_requests.html', requests=requests)

@app.route('/respond_request', methods=['POST'])
@login_required
def respond_request():
    action = request.form.get('action')
    sender_username = request.form.get('username')

    if not action or not sender_username:
        return redirect(url_for('friend_requests'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (session['username'],))
    receiver = cursor.fetchone()
    if not receiver:
        return redirect(url_for('logout'))
    receiver_id = receiver['id']

    cursor.execute("SELECT id FROM users WHERE username = ?", (sender_username,))
    sender = cursor.fetchone()
    if not sender:
        return redirect(url_for('friend_requests'))
    sender_id = sender['id']

    if action == 'accept':
        cursor.execute("""
            UPDATE arkadasliklar SET durum = 'kabul'
            WHERE gonderen_id = ? AND alici_id = ? AND durum = 'beklemede'
        """, (sender_id, receiver_id))
    elif action == 'reject':
        cursor.execute("""
            DELETE FROM arkadasliklar
            WHERE gonderen_id = ? AND alici_id = ? AND durum = 'beklemede'
        """, (sender_id, receiver_id))

    db.commit()
    return redirect(url_for('friend_requests'))

users = {}

@socketio.on('connect')
def handle_connect(auth):
    if not auth or 'username' not in auth:
        print("[CONNECT] Auth bilgisi eksik, bağlantı reddedildi")
        return False
    username = auth['username']
    users[request.sid] = username
    print(f"[CONNECT] SID: {request.sid}, username: {username}")

@socketio.on('disconnect')
def handle_disconnect():
    username = users.pop(request.sid, None)
    print(f"[DISCONNECT] SID: {request.sid}, username: {username}")

@socketio.on('join')
def on_join(data):
    friend = data.get('friend')
    sender = users.get(request.sid)
    if not sender or not friend:
        print(f"[JOIN] Eksik bilgi sender:{sender}, friend:{friend}")
        return
    room = '-'.join(sorted([sender, friend]))
    join_room(room)
    print(f"[JOIN] {sender} joined room {room}")

@socketio.on('leave')
def on_leave(data):
    friend = data.get('friend')
    sender = users.get(request.sid)
    if not sender or not friend:
        print(f"[LEAVE] Eksik bilgi sender:{sender}, friend:{friend}")
        return
    room = '-'.join(sorted([sender, friend]))
    leave_room(room)
    print(f"[LEAVE] {sender} left room {room}")

@socketio.on('message')
def handle_message(data):
    sender = users.get(request.sid)
    text = data.get('text')
    friend = data.get('friend')

    print(f"[MESSAGE] Alındı - Gönderen: {sender}, Alıcı: {friend}, Metin: {text}")

    if not sender or not text or not friend:
        print(f"[MESSAGE] Eksik veri sender:{sender}, friend:{friend}, text:{text}")
        return

    room = '-'.join(sorted([sender, friend]))

    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (sender,))
        sender_row = cursor.fetchone()
        cursor.execute("SELECT id FROM users WHERE username = ?", (friend,))
        receiver_row = cursor.fetchone()

        if not sender_row or not receiver_row:
            print("[MESSAGE] Veritabanında kullanıcı bulunamadı.")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            cursor.execute("""
                INSERT INTO messages (sender_id, receiver_id, message, timestamp, okundu)
                VALUES (?, ?, ?, ?, 0)
            """, (sender_row['id'], receiver_row['id'], text, timestamp))
            db.commit()
            print(f"[MESSAGE] Mesaj kaydedildi: {text}")
        except Exception as e:
            print(f"[MESSAGE] Veritabanı hatası: {e}")
            return

    emit('message', {'user': sender, 'receiver': friend, 'text': text, 'timestamp': timestamp}, room=room, include_self=True)

@socketio.on('typing')
def handle_typing(data):
    friend = data.get('friend')
    sender = users.get(request.sid)
    if not sender or not friend:
        return
    room = '-'.join(sorted([sender, friend]))
    emit('display_typing', {'from': sender}, room=room, include_self=False)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    friend = data.get('friend')
    sender = users.get(request.sid)
    if not sender or not friend:
        return
    room = '-'.join(sorted([sender, friend]))
    emit('hide_typing', sender, room=room, include_self=False)

@socketio.on('messages_read')
def handle_messages_read(data):
    friend = data.get('friend')
    reader = users.get(request.sid)
    if not friend or not reader:
        return

    room = '-'.join(sorted([reader, friend]))

    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE messages SET okundu = 1
            WHERE sender_id = (SELECT id FROM users WHERE username = ?)
            AND receiver_id = (SELECT id FROM users WHERE username = ?)
            AND okundu = 0
        """, (friend, reader))
        db.commit()

    emit('messages_read', {'reader': reader, 'friend': friend}, room=room, include_self=False)

@socketio.on('call_offer')
def handle_call_offer(data):
    sender = users.get(request.sid)
    friend = data.get('friend')
    offer = data.get('offer')
    call_type = data.get('call_type')  # 'voice' veya 'video'
    if not sender or not friend or not offer or not call_type:
        return
    room = '-'.join(sorted([sender, friend]))
    emit('call_offer', {'from': sender, 'offer': offer, 'call_type': call_type}, room=room, include_self=False)

@socketio.on('call_answer')
def handle_call_answer(data):
    sender = users.get(request.sid)
    friend = data.get('friend')
    answer = data.get('answer')
    if not sender or not friend or not answer:
        return
    room = '-'.join(sorted([sender, friend]))
    emit('call_answer', {'from': sender, 'answer': answer}, room=room, include_self=False)

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    sender = users.get(request.sid)
    friend = data.get('friend')
    candidate = data.get('candidate')
    if not sender or not friend or not candidate:
        return
    room = '-'.join(sorted([sender, friend]))
    emit('ice_candidate', {'from': sender, 'candidate': candidate}, room=room, include_self=False)

@socketio.on('call_end')
def handle_call_end(data):
    sender = users.get(request.sid)
    friend = data.get('friend')
    if not sender or not friend:
        return
    room = '-'.join(sorted([sender, friend]))
    emit('call_end', {'from': sender}, room=room, include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)