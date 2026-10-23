import sqlite3
import threading
from typing import List, Dict, Any, Optional
from config import DATABASE_PATH, OWNER_ID


class Database:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Foydalanuvchilar jadvali
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        full_name TEXT,
                        username TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Adminlar jadvali
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS admins (
                        user_id INTEGER PRIMARY KEY,
                        added_by INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Majburiy obuna kanallari (oddiy va zayavka)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS channels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        is_request INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Zayavka (join request) yuborgan foydalanuvchilar
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS join_requests (
                        user_id INTEGER,
                        chat_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, chat_id)
                    )
                """)

                # Sozlamalar jadvali (masalan: yuklab berilgan fayl matni / reklama)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                conn.commit()

    # --- FOYDALANUVCHILAR ---
    def add_user(self, user_id: int, full_name: str, username: Optional[str]) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (user_id, full_name, username)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        full_name=excluded.full_name,
                        username=excluded.username
                """, (user_id, full_name, username))
                conn.commit()
                return True

    def get_user_count(self) -> int:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                return cursor.fetchone()[0]

    def get_today_users(self) -> int:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
                return cursor.fetchone()[0]

    def get_all_user_ids(self) -> List[int]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users")
                return [row[0] for row in cursor.fetchall()]

    # --- ADMINLAR ---
    def is_admin(self, user_id: int) -> bool:
        if user_id == OWNER_ID:
            return True
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
                return cursor.fetchone() is not None

    def add_admin(self, user_id: int, added_by: int) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO admins (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
                conn.commit()
                return True

    def remove_admin(self, user_id: int) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
                conn.commit()
                return True

    def get_admins(self) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, added_by, created_at FROM admins ORDER BY created_at DESC")
                return [dict(row) for row in cursor.fetchall()]

    # --- MAJBUR Y OBUNA KANALLARI ---
    def get_channels(self) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM channels ORDER BY id ASC")
                return [dict(row) for row in cursor.fetchall()]

    def add_channel(self, chat_id: str, title: str, url: str, is_request: int = 0) -> int:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO channels (chat_id, title, url, is_request)
                    VALUES (?, ?, ?, ?)
                """, (chat_id, title, url, is_request))
                conn.commit()
                return cursor.lastrowid

    def delete_channel(self, channel_id: int) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
                conn.commit()
                return True

    def get_channel_by_id(self, channel_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
                row = cursor.fetchone()
                return dict(row) if row else None

    # --- ZAYAVKA (JOIN REQUEST) ---
    def record_join_request(self, user_id: int, chat_id: str):
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO join_requests (user_id, chat_id)
                    VALUES (?, ?)
                """, (user_id, str(chat_id)))
                conn.commit()

    def has_join_request(self, user_id: int, chat_id: str) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM join_requests
                    WHERE user_id = ? AND chat_id = ?
                """, (user_id, str(chat_id)))
                return cursor.fetchone() is not None

    # --- SOZLAMALAR (MATN / CAPTION) ---
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else default

    def set_setting(self, key: str, value: str):
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """, (key, value))
                conn.commit()

    def delete_setting(self, key: str):
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
                conn.commit()


# Yagona ma'lumotlar bazasi obyekti
db = Database()
