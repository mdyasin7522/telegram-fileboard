import aiosqlite
import uuid
from datetime import datetime

DB_NAME = "fileboard.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                file_name TEXT,
                file_type TEXT,
                max_downloads INTEGER DEFAULT -1,
                download_count INTEGER DEFAULT 0,
                expires_at TEXT DEFAULT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()

async def save_file(file_id, file_name, file_type, max_downloads=-1, expires_at=None):
    uid = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO files (id, file_id, file_name, file_type, max_downloads, download_count, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
        """, (uid, file_id, file_name, file_type, max_downloads, expires_at, now))
        await db.commit()
    return uid

async def get_file(uid):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM files WHERE id = ?", (uid,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0], "file_id": row[1], "file_name": row[2],
                    "file_type": row[3], "max_downloads": row[4],
                    "download_count": row[5], "expires_at": row[6], "created_at": row[7]
                }
    return None

async def increment_download(uid):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE files SET download_count = download_count + 1 WHERE id = ?", (uid,))
        await db.commit()

async def delete_file(uid):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM files WHERE id = ?", (uid,))
        await db.commit()

async def list_files():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, file_name, max_downloads, download_count, expires_at FROM files ORDER BY created_at DESC") as cursor:
            return await cursor.fetchall()
