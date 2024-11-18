import sqlite3
from datetime import datetime
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os

class MemoryStore:
    def __init__(self, db_path=None):
        if db_path is None:
            # Store in the current directory
            db_path = 'memories.db'
        
        self.db_path = db_path
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    importance FLOAT NOT NULL,
                    timestamp TEXT NOT NULL,
                    embedding TEXT,
                    metadata TEXT,
                    type TEXT,
                    context TEXT,
                    last_accessed TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON memories(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")

    def _encode_text(self, text):
        try:
            embedding = self.encoder.encode(text)
            return json.dumps(embedding.tolist())
        except Exception as e:
            print(f"Encoding note: {e}")
            return json.dumps([])

    def _decode_embedding(self, embedding_str):
        try:
            return np.array(json.loads(embedding_str))
        except Exception as e:
            print(f"Decoding note: {e}")
            return np.array([])

    def add_memory(self, content, importance=1.0, memory_type="conversation", context="", metadata=None):
        embedding = self._encode_text(content)
        current_time = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO memories 
                   (content, importance, timestamp, embedding, metadata, type, context, last_accessed) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (content, importance, current_time, embedding,
                 json.dumps(metadata or {}), memory_type, context, current_time)
            )

    def get_memories(self, limit=100, memory_type=None):
        query = "SELECT * FROM memories"
        params = []
        
        if memory_type:
            query += " WHERE type = ?"
            params.append(memory_type)
        
        query += " ORDER BY importance DESC, timestamp DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def search_similar_memories(self, query, threshold=0.7, limit=5):
        query_embedding = self._encode_text(query)
        memories = self.get_memories(limit=None)
        similarities = []
        
        query_vector = self._decode_embedding(query_embedding)
        if len(query_vector) == 0:
            return []
        
        for memory in memories:
            memory_vector = self._decode_embedding(memory['embedding'])
            if len(memory_vector) > 0:
                similarity = cosine_similarity([query_vector], [memory_vector])[0][0]
                if similarity >= threshold:
                    similarities.append((memory, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:limit] if limit else similarities

    def update_memory(self, memory_id, content=None, importance=None, memory_type=None):
        updates = []
        params = []
        
        if content is not None:
            updates.append("content = ?, embedding = ?")
            params.extend([content, self._encode_text(content)])
        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)
        if memory_type is not None:
            updates.append("type = ?")
            params.append(memory_type)
        
        if updates:
            updates.append("last_accessed = ?")
            params.append(datetime.now().isoformat())
            params.append(memory_id)
            
            query = f"UPDATE memories SET {', '.join(updates)} WHERE id = ?"
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(query, params)

    def delete_memory(self, memory_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def get_memory_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_memories,
                    AVG(importance) as avg_importance,
                    COUNT(DISTINCT type) as memory_types
                FROM memories
            """)
            stats = dict(zip(['total_memories', 'avg_importance', 'memory_types'], cursor.fetchone()))
            stats['avg_importance'] = stats['avg_importance'] or 0.0
            return stats
