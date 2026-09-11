import os
import sqlite3
import threading
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger("SoundIQ.search")

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aif", ".aiff", ".wma", ".opus"}


class DatabasePool:
    def __init__(self, db_path, max_connections=4):
        self._db_path = db_path
        self._max = max_connections
        self._pool = []
        self._lock = threading.Lock()

    def get(self):
        with self._lock:
            if self._pool:
                return self._pool.pop()
        return sqlite3.connect(self._db_path, timeout=30)

    def put(self, conn):
        with self._lock:
            if len(self._pool) < self._max:
                self._pool.append(conn)
            else:
                conn.close()

    def close_all(self):
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool.clear()


class SearchEngine:
    def __init__(self, db_path="metadata.db"):
        self.db_path = db_path
        self.device = "cpu"
        self.model_name = "laion/clap-htsat-unfused"
        self.model = None
        self.processor = None
        self.tokenizer = None
        self._pool = DatabasePool(db_path)
        self._init_db()

    def _init_db(self):
        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_id INTEGER,
                    path TEXT UNIQUE,
                    filename TEXT,
                    duration REAL,
                    sample_rate INTEGER,
                    channels INTEGER,
                    size INTEGER,
                    embedding BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(folder_id) REFERENCES folders(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sounds_folder ON sounds(folder_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sounds_filename ON sounds(filename)")
            conn.commit()
        finally:
            self._pool.put(conn)

    def load_models(self):
        if self.model is not None:
            return
        import torch
        from transformers import AutoProcessor, ClapModel, AutoTokenizer

        torch.set_num_threads(os.cpu_count())
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading CLAP models on {self.device}...")
        self.model = ClapModel.from_pretrained(self.model_name).to(self.device)
        self.processor = AutoProcessor.from_pretrained(self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model.eval()
        logger.info("CLAP models loaded successfully.")

    def get_audio_embedding(self, file_path):
        self.load_models()
        import torch
        import librosa

        try:
            y, sr = librosa.load(file_path, sr=48000, mono=True, duration=7.0)
            if len(y) == 0:
                y = np.zeros(48000 * 7, dtype=np.float32)
            inputs = self.processor(audio=[y], return_tensors="pt", sampling_rate=48000)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                audio_features = self.model.get_audio_features(**inputs)
                embedding = audio_features.pooler_output.cpu().numpy()[0]
            return embedding
        except Exception as e:
            logger.error(f"Error embedding {file_path}: {e}")
            return None

    def get_text_embedding(self, text):
        self.load_models()
        import torch

        inputs = self.tokenizer([text], padding=True, return_tensors="pt")
        if "token_type_ids" in inputs:
            del inputs["token_type_ids"]
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
            embedding = text_features.pooler_output.cpu().numpy()[0]
        return embedding

    def add_folder(self, folder_path):
        folder_path = os.path.abspath(folder_path)
        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO folders (path) VALUES (?)", (folder_path,))
            conn.commit()
            cursor.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            return cursor.fetchone()[0]
        finally:
            self._pool.put(conn)

    def remove_folder(self, folder_path):
        folder_path = os.path.abspath(folder_path)
        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            row = cursor.fetchone()
            if row:
                cursor.execute("DELETE FROM sounds WHERE folder_id = ?", (row[0],))
                cursor.execute("DELETE FROM folders WHERE id = ?", (row[0],))
                conn.commit()
        finally:
            self._pool.put(conn)

    def get_all_folders(self):
        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT path FROM folders")
            return [row[0] for row in cursor.fetchall()]
        finally:
            self._pool.put(conn)

    def scan_folder(self, folder_path, progress_callback=None):
        folder_path = os.path.abspath(folder_path)
        folder_id = self.add_folder(folder_path)

        audio_files = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    audio_files.append(os.path.join(root, file))

        total_files = len(audio_files)
        if total_files == 0:
            if progress_callback:
                progress_callback(0, 0, "No audio files found.")
            return

        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT path FROM sounds WHERE folder_id = ?", (folder_id,))
            existing_paths = {row[0] for row in cursor.fetchall()}

            files_to_index = [f for f in audio_files if f not in existing_paths]
            total_to_index = len(files_to_index)

            if total_to_index == 0:
                if progress_callback:
                    progress_callback(total_files, total_files, "All files already indexed.")
                return

            logger.info(f"Found {total_files} audio files ({total_to_index} need indexing).")
            self.load_models()

            batch_data = []
            indexed_count = 0

            for i, file_path in enumerate(files_to_index):
                try:
                    import soundfile as sf_mod
                    try:
                        info = sf_mod.info(file_path)
                        duration = info.duration
                        sr = info.samplerate
                        channels = info.channels
                    except Exception:
                        import librosa
                        duration = librosa.get_duration(path=file_path)
                        sr = 48000
                        channels = 1

                    size = os.path.getsize(file_path)
                    filename = os.path.basename(file_path)
                    emb = self.get_audio_embedding(file_path)

                    if emb is not None:
                        emb_bytes = emb.astype(np.float32).tobytes()
                        batch_data.append((folder_id, file_path, filename, duration, sr, channels, size, emb_bytes))

                    indexed_count += 1
                    if progress_callback:
                        progress_callback(indexed_count, total_to_index, filename)

                    if len(batch_data) >= 10:
                        cursor.executemany("""
                            INSERT OR REPLACE INTO sounds
                            (folder_id, path, filename, duration, sample_rate, channels, size, embedding)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch_data)
                        conn.commit()
                        batch_data.clear()

                except Exception as e:
                    logger.error(f"Error scanning {file_path}: {e}")

            if batch_data:
                cursor.executemany("""
                    INSERT OR REPLACE INTO sounds
                    (folder_id, path, filename, duration, sample_rate, channels, size, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, batch_data)
                conn.commit()

        finally:
            self._pool.put(conn)

    def reindex_folder(self, folder_path, progress_callback=None):
        folder_path = os.path.abspath(folder_path)
        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            row = cursor.fetchone()
            if row:
                cursor.execute("DELETE FROM sounds WHERE folder_id = ?", (row[0],))
                conn.commit()
        finally:
            self._pool.put(conn)
        self.scan_folder(folder_path, progress_callback)

    def get_sounds_in_folder(self, folder_path):
        folder_path = os.path.abspath(folder_path)
        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            row = cursor.fetchone()
            if not row:
                return []
            cursor.execute(
                "SELECT path, filename, duration, sample_rate, channels, size FROM sounds WHERE folder_id = ?",
                (row[0],),
            )
            return cursor.fetchall()
        finally:
            self._pool.put(conn)

    def search_keyword(self, query):
        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            terms = query.split()
            if not terms:
                cursor.execute("SELECT path, filename, duration, sample_rate, channels, size FROM sounds LIMIT 200")
                return cursor.fetchall()

            conditions = []
            params = []
            for term in terms:
                conditions.append("(filename LIKE ? OR path LIKE ?)")
                params.extend([f"%{term}%", f"%{term}%"])

            sql = "SELECT path, filename, duration, sample_rate, channels, size FROM sounds WHERE "
            sql += " AND ".join(conditions)
            sql += " LIMIT 200"
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            self._pool.put(conn)

    def search_ai(self, query, top_k=100):
        if not query.strip():
            return self.search_keyword(query)

        query_emb = self.get_text_embedding(query)

        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT path, filename, duration, sample_rate, channels, size, embedding FROM sounds")
            rows = cursor.fetchall()
        finally:
            self._pool.put(conn)

        if not rows:
            return []

        paths = []
        metadata = []
        embeddings = []

        for path, filename, duration, sr, channels, size, emb_bytes in rows:
            if emb_bytes is None:
                continue
            paths.append(path)
            metadata.append((path, filename, duration, sr, channels, size))
            embeddings.append(np.frombuffer(emb_bytes, dtype=np.float32))

        if not embeddings:
            return []

        emb_matrix = np.vstack(embeddings)
        similarities = emb_matrix @ query_emb

        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            path, filename, duration, sr, channels, size = metadata[idx]
            results.append((path, filename, duration, sr, channels, size, float(similarities[idx])))

        return results

    def get_total_sounds(self):
        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sounds")
            return cursor.fetchone()[0]
        finally:
            self._pool.put(conn)

    def get_total_folders(self):
        conn = self._pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM folders")
            return cursor.fetchone()[0]
        finally:
            self._pool.put(conn)


if __name__ == "__main__":
    print("Testing search engine...")
    se = SearchEngine("test_metadata.db")
    print(f"Total sounds indexed: {se.get_total_sounds()}")
    print(f"Total folders: {se.get_total_folders()}")
    print("Done!")
