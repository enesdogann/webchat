
import sqlite3

DB_NAME = 'chat_app.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            okundu INTEGER DEFAULT 0,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (receiver_id) REFERENCES users(id)
        )
    ''')

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS arkadasliklar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gonderen_id INTEGER NOT NULL,
            alici_id INTEGER NOT NULL,
            durum TEXT DEFAULT 'beklemede',
            FOREIGN KEY (gonderen_id) REFERENCES users(id),
            FOREIGN KEY (alici_id) REFERENCES users(id)
        )
    """)

    # Arkadaşlıklar için çift kayıt engelleyen index
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_arkadaslik ON arkadasliklar(gonderen_id, alici_id)
    """)

    # Avatar sütunu yoksa ekle
    cursor.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'avatar' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT '1.png'")

    cursor.execute("UPDATE users SET avatar = '1.png' WHERE avatar IS NULL OR avatar = ''")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()