import os
import sqlite3
import numpy as np
from pathlib import Path

class SearchEngine:
    def __init__(self, db_path="metadata.db"):
        self.db_path = db_path
        self.device = "cpu"
        self.model_name = "laion/clap-htsat-unfused"
        
        # Lazy loaded models
        self.model = None
        self.processor = None
        self.tokenizer = None
        
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create folders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE
            )
        """)
        
        # Create sounds table
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
        
        conn.commit()
        conn.close()

    def load_models(self):
        """Lazy load CLAP models."""
        if self.model is not None:
            return
        
        import torch
        from transformers import AutoProcessor, ClapModel, AutoTokenizer
        
        torch.set_num_threads(os.cpu_count())
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading CLAP models on {self.device}...")
        self.model = ClapModel.from_pretrained(self.model_name).to(self.device)
        self.processor = AutoProcessor.from_pretrained(self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model.eval()
        print("CLAP models loaded successfully.")

    def get_audio_embedding(self, file_path):
        """Load audio file, resample to 48kHz, and compute CLAP embedding."""
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
            print(f"Error embedding {file_path}: {e}")
            return None

    def get_text_embedding(self, text):
        """Compute CLAP embedding for text query."""
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
        """Register folder in database if not exists and return its ID."""
        folder_path = os.path.abspath(folder_path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO folders (path) VALUES (?)", (folder_path,))
            conn.commit()
            cursor.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            folder_id = cursor.fetchone()[0]
            return folder_id
        finally:
            conn.close()

    def remove_folder(self, folder_path):
        """Remove folder and its children sounds from database."""
        folder_path = os.path.abspath(folder_path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            row = cursor.fetchone()
            if row:
                folder_id = row[0]
                cursor.execute("DELETE FROM sounds WHERE folder_id = ?", (folder_id,))
                cursor.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
                conn.commit()
        finally:
            conn.close()

    def get_all_folders(self):
        """Get list of all indexed folders."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT path FROM folders")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def scan_folder(self, folder_path, progress_callback=None):
        """Scan folder for audio files, extract metadata and embeddings, save to database."""
        folder_path = os.path.abspath(folder_path)
        folder_id = self.add_folder(folder_path)
        
        supported_exts = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aif", ".aiff"}
        audio_files = []
        
        for root, _, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in supported_exts:
                    audio_files.append(os.path.join(root, file))
                    
        total_files = len(audio_files)
        if total_files == 0:
            if progress_callback:
                progress_callback(0, 0, "No audio files found.")
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check files that are already indexed to skip them
        cursor.execute("SELECT path FROM sounds WHERE folder_id = ?", (folder_id,))
        existing_paths = {row[0] for row in cursor.fetchall()}
        
        files_to_index = [f for f in audio_files if f not in existing_paths]
        total_to_index = len(files_to_index)
        
        if total_to_index == 0:
            if progress_callback:
                progress_callback(total_files, total_files, "All files already indexed.")
            conn.close()
            return
            
        print(f"Found {total_files} audio files ({total_to_index} need indexing).")
        
        # Pre-load CLAP models for indexing
        self.load_models()
        
        indexed_count = 0
        for i, file_path in enumerate(files_to_index):
            try:
                # 1. Metadata extraction
                # Duration, sample rate, channels, size
                # Use librosa or soundfile to get fast info
                # soundfile info is fast because it doesn't read the whole audio data
                import soundfile as sf
                try:
                    info = sf.info(file_path)
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
                
                # 2. Compute AI embedding
                emb = self.get_audio_embedding(file_path)
                
                if emb is not None:
                    emb_bytes = emb.astype(np.float32).tobytes()
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO sounds 
                        (folder_id, path, filename, duration, sample_rate, channels, size, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (folder_id, file_path, filename, duration, sr, channels, size, emb_bytes))
                    
                    # Commit in chunks to prevent database lock issues
                    if i % 10 == 0:
                        conn.commit()
                        
                indexed_count += 1
                if progress_callback:
                    progress_callback(indexed_count, total_to_index, filename)
            except Exception as e:
                print(f"Error scanning {file_path}: {e}")
                
        conn.commit()
        conn.close()

    def get_sounds_in_folder(self, folder_path):
        """Get all sounds inside a specific folder."""
        folder_path = os.path.abspath(folder_path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Find folder ID
            cursor.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            row = cursor.fetchone()
            if not row:
                return []
            folder_id = row[0]
            cursor.execute("SELECT path, filename, duration, sample_rate, channels, size FROM sounds WHERE folder_id = ?", (folder_id,))
            return cursor.fetchall()
        finally:
            conn.close()

    def search_keyword(self, query):
        """Search database by matching filename or path."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Split search terms
        terms = query.split()
        if not terms:
            cursor.execute("SELECT path, filename, duration, sample_rate, channels, size FROM sounds LIMIT 200")
            rows = cursor.fetchall()
            conn.close()
            return rows
            
        sql = "SELECT path, filename, duration, sample_rate, channels, size FROM sounds WHERE "
        conditions = []
        params = []
        for term in terms:
            conditions.append("(filename LIKE ? OR path LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])
        sql += " AND ".join(conditions)
        sql += " LIMIT 200"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def search_ai(self, query, top_k=100):
        """Perform AI search by encoding query and finding highest cosine similarity."""
        if not query.strip():
            return self.search_keyword(query)
            
        # Get query embedding
        query_emb = self.get_text_embedding(query)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Load all sounds and their embeddings
        cursor.execute("SELECT path, filename, duration, sample_rate, channels, size, embedding FROM sounds")
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for path, filename, duration, sr, channels, size, emb_bytes in rows:
            if emb_bytes is None:
                continue
            emb = np.frombuffer(emb_bytes, dtype=np.float32)
            # Both embeddings are already normalized (L2 norm = 1)
            # Dot product is equal to cosine similarity
            similarity = np.dot(query_emb, emb)
            results.append((path, filename, duration, sr, channels, size, float(similarity)))
            
        # Sort by similarity descending
        results.sort(key=lambda x: x[6], reverse=True)
        
        # Return columns matching search_keyword (without similarity score, or with)
        # We can return top_k
        return results[:top_k]

if __name__ == "__main__":
    # Test execution
    print("Testing search engine...")
    se = SearchEngine("test_metadata.db")
    print("Pre-loading models...")
    se.load_models()
    print("Done!")
