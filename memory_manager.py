from .memory_store import MemoryStore
import re
from datetime import datetime, timedelta

class MemoryManager:
    def __init__(self):
        self.memory_store = MemoryStore()
        self.importance_threshold = 0.5
        self.consolidation_interval = timedelta(hours=1)
        self.last_consolidation = datetime.now()

    def process_message(self, message, context=""):
        importance = self._calculate_importance(message)
        
        # Always store messages with their calculated importance
        self.memory_store.add_memory(
            content=message,
            importance=importance,
            memory_type="conversation",
            context=context
        )
        
        # Consolidate memories if needed
        if datetime.now() - self.last_consolidation > self.consolidation_interval:
            self.consolidate_memories()
            self.last_consolidation = datetime.now()

    def _calculate_importance(self, message):
        importance = 0.0
        
        # Keywords indicating importance
        important_keywords = [
            'remember', 'important', 'crucial', 'key', 'vital', 
            'essential', 'never forget', 'always', 'must', 'note',
            'critical', 'significant', 'priority', 'urgent'
        ]
        
        # Calculate base importance
        for keyword in important_keywords:
            if keyword.lower() in message.lower():
                importance += 0.2

        # Length factor
        importance += min(len(message.split()) / 100, 0.3)

        # Content-based importance
        if re.search(r'\d+', message):  # Numbers
            importance += 0.15
        if re.search(r'[A-Z][a-z]+ [A-Z][a-z]+', message):  # Proper names
            importance += 0.2
        if re.search(r'https?://\S+', message):  # URLs
            importance += 0.15
        if re.search(r'\b[A-Z]{2,}\b', message):  # Acronyms
            importance += 0.1
        if '?' in message:  # Questions
            importance += 0.15
        if '!' in message:  # Emphasis
            importance += 0.1

        # Emotional content
        emotional_words = ['love', 'hate', 'angry', 'happy', 'sad', 'excited', 'worried', 'concerned']
        for word in emotional_words:
            if word in message.lower():
                importance += 0.1

        return min(importance, 1.0)

    def get_relevant_memories(self, context, limit=5):
        return self.memory_store.search_similar_memories(context, threshold=0.6, limit=limit)

    def consolidate_memories(self, threshold=0.85):
        memories = self.memory_store.get_memories(limit=None)
        consolidated = []
        
        for i, memory in enumerate(memories):
            if memory in consolidated:
                continue
                
            similar_memories = self.memory_store.search_similar_memories(
                memory['content'],
                threshold=threshold,
                limit=None
            )
            
            if len(similar_memories) > 1:
                # Combine similar memories
                combined_importance = max(m[0]['importance'] for m in similar_memories)
                self.memory_store.update_memory(
                    memory['id'],
                    importance=combined_importance
                )
                
                # Delete other similar memories
                for sim_mem, _ in similar_memories[1:]:
                    self.memory_store.delete_memory(sim_mem['id'])
            
            consolidated.append(memory)

    def manage_memory(self, action, **kwargs):
        if action == "add":
            return self.memory_store.add_memory(
                kwargs['content'],
                kwargs.get('importance', 1.0),
                kwargs.get('memory_type', 'manual'),
                kwargs.get('context', '')
            )
        elif action == "delete":
            return self.memory_store.delete_memory(kwargs['memory_id'])
        elif action == "update":
            return self.memory_store.update_memory(
                kwargs['memory_id'],
                content=kwargs.get('content'),
                importance=kwargs.get('importance'),
                memory_type=kwargs.get('memory_type')
            )
        elif action == "list":
            return self.memory_store.get_memories(
                limit=kwargs.get('limit', 100),
                memory_type=kwargs.get('memory_type')
            )
        elif action == "search":
            return self.memory_store.search_similar_memories(
                kwargs['query'],
                threshold=kwargs.get('threshold', 0.7),
                limit=kwargs.get('limit', 5)
            )
        elif action == "consolidate":
            return self.consolidate_memories(
                threshold=kwargs.get('threshold', 0.85)
            )
        elif action == "stats":
            return self.memory_store.get_memory_stats()
