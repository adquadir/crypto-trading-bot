from dataclasses import dataclass
from typing import Dict, Optional, Any
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Represents a single cache entry with value and timestamp."""
    value: Any
    timestamp: float

class CacheManager:
    """Manages caching of market data with TTL support."""
    
    def __init__(self, default_ttl: int = 5):
        """Initialize the cache manager with a default TTL in seconds."""
        self.cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.logger = logging.getLogger(__name__)
    
    def get(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """Get a value from the cache if it exists and is not expired."""
        if key not in self.cache:
            return None
            
        entry = self.cache[key]
        current_time = time.time()
        
        # Check if entry is expired
        if current_time - entry.timestamp > (ttl or self.default_ttl):
            del self.cache[key]
            return None
            
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache with optional TTL override."""
        self.cache[key] = CacheEntry(
            value=value,
            timestamp=time.time()
        )
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        self.cache.clear()
    
    def remove(self, key: str) -> None:
        """Remove a specific entry from the cache."""
        if key in self.cache:
            del self.cache[key]
    
    def get_all(self) -> Dict[str, Any]:
        """Get all non-expired entries from the cache."""
        current_time = time.time()
        return {
            key: entry.value
            for key, entry in self.cache.items()
            if current_time - entry.timestamp <= self.default_ttl
        } 