"""
Performance utilities for the YouTube Shorts Manager
Provides caching, debouncing, and optimization helpers
"""
import time
import threading
from functools import wraps
from typing import Dict, Any, Callable
import streamlit as st
import asyncio
from concurrent.futures import ThreadPoolExecutor
import weakref

class MemoryCache:
    """Thread-safe in-memory cache with TTL support."""
    
    def __init__(self, default_ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Any:
        """Get value from cache if not expired."""
        with self.lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            if time.time() > entry['expires']:
                del self.cache[key]
                return None
            
            return entry['value']
    
    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in cache with TTL."""
        with self.lock:
            ttl = ttl or self.default_ttl
            self.cache[key] = {
                'value': value,
                'expires': time.time() + ttl
            }
    
    def delete(self, key: str) -> None:
        """Delete key from cache."""
        with self.lock:
            self.cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        with self.lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self.cache.items() 
                if now > entry['expires']
            ]
            
            for key in expired_keys:
                del self.cache[key]
            
            return len(expired_keys)


class Debouncer:
    """Debounce function calls to prevent excessive API calls."""
    
    def __init__(self, wait_time: float = 0.5):
        self.wait_time = wait_time
        self.timers: Dict[str, threading.Timer] = {}
        self.lock = threading.Lock()
    
    def debounce(self, key: str, func: Callable, *args, **kwargs) -> None:
        """Debounce a function call by key."""
        with self.lock:
            # Cancel existing timer for this key
            if key in self.timers:
                self.timers[key].cancel()
            
            # Create new timer
            timer = threading.Timer(
                self.wait_time,
                lambda: self._execute(key, func, *args, **kwargs)
            )
            timer.start()
            self.timers[key] = timer
    
    def _execute(self, key: str, func: Callable, *args, **kwargs) -> None:
        """Execute the debounced function."""
        try:
            func(*args, **kwargs)
        finally:
            with self.lock:
                self.timers.pop(key, None)


class BatchProcessor:
    """Batch multiple operations together for efficiency."""
    
    def __init__(self, batch_size: int = 10, flush_interval: float = 2.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batches: Dict[str, list] = {}
        self.processors: Dict[str, Callable] = {}
        self.timers: Dict[str, threading.Timer] = {}
        self.lock = threading.Lock()
    
    def add_to_batch(self, batch_key: str, item: Any, processor: Callable = None) -> None:
        """Add item to batch for processing."""
        with self.lock:
            if batch_key not in self.batches:
                self.batches[batch_key] = []
            
            self.batches[batch_key].append(item)
            
            if processor:
                self.processors[batch_key] = processor
            
            # Process if batch is full
            if len(self.batches[batch_key]) >= self.batch_size:
                self._process_batch(batch_key)
            else:
                # Set timer to flush batch
                self._schedule_flush(batch_key)
    
    def _schedule_flush(self, batch_key: str) -> None:
        """Schedule batch flush after interval."""
        if batch_key in self.timers:
            self.timers[batch_key].cancel()
        
        timer = threading.Timer(
            self.flush_interval,
            lambda: self._process_batch(batch_key)
        )
        timer.start()
        self.timers[batch_key] = timer
    
    def _process_batch(self, batch_key: str) -> None:
        """Process a batch of items."""
        with self.lock:
            if batch_key not in self.batches or not self.batches[batch_key]:
                return
            
            items = self.batches[batch_key].copy()
            self.batches[batch_key].clear()
            
            # Cancel timer
            if batch_key in self.timers:
                self.timers[batch_key].cancel()
                del self.timers[batch_key]
        
        # Process outside of lock
        if batch_key in self.processors:
            try:
                self.processors[batch_key](items)
            except Exception as e:
                print(f"Batch processing error for {batch_key}: {e}")
    
    def flush_all(self) -> None:
        """Flush all pending batches."""
        batch_keys = list(self.batches.keys())
        for key in batch_keys:
            self._process_batch(key)


def cache_with_ttl(ttl: int = 300, cache_key_func: Callable = None):
    """Decorator for caching function results with TTL."""
    def decorator(func):
        if not hasattr(func, '_cache'):
            func._cache = MemoryCache(ttl)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_func:
                key = cache_key_func(*args, **kwargs)
            else:
                key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try cache first
            cached_result = func._cache.get(key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            func._cache.set(key, result, ttl)
            return result
        
        # Add cache management methods
        wrapper.clear_cache = func._cache.clear
        wrapper.delete_cache = func._cache.delete
        return wrapper
    
    return decorator


def async_execute(func: Callable, *args, **kwargs) -> Any:
    """Execute function asynchronously and return a future."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        future = executor.submit(func, *args, **kwargs)
        return future


class LazyLoader:
    """Lazy loading utility for heavy operations."""
    
    def __init__(self):
        self.loaded_components: Dict[str, Any] = {}
        self.loaders: Dict[str, Callable] = {}
    
    def register(self, key: str, loader_func: Callable) -> None:
        """Register a lazy loader for a component."""
        self.loaders[key] = loader_func
    
    def load(self, key: str, force_reload: bool = False) -> Any:
        """Load component lazily."""
        if not force_reload and key in self.loaded_components:
            return self.loaded_components[key]
        
        if key not in self.loaders:
            raise ValueError(f"No loader registered for key: {key}")
        
        # Load component
        component = self.loaders[key]()
        self.loaded_components[key] = component
        return component
    
    def unload(self, key: str) -> None:
        """Unload a component to free memory."""
        self.loaded_components.pop(key, None)
    
    def clear_all(self) -> None:
        """Clear all loaded components."""
        self.loaded_components.clear()


def streamlit_cache_cleanup():
    """Clean up Streamlit caches to prevent memory leaks."""
    try:
        st.cache_data.clear()
        st.cache_resource.clear()
    except Exception:
        pass


def optimize_streamlit_config():
    """Apply Streamlit performance optimizations."""
    # Set configuration for better performance
    st.set_option('theme.base', 'light')
    
    # Configure session state cleanup
    max_session_keys = 50
    if len(st.session_state.keys()) > max_session_keys:
        # Remove old session keys
        keys_to_remove = list(st.session_state.keys())[:-max_session_keys]
        for key in keys_to_remove:
            if not key.startswith('authenticated') and not key.startswith('user'):
                try:
                    del st.session_state[key]
                except:
                    pass


def performance_monitor(func):
    """Decorator to monitor function performance."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # Log slow operations
            if duration > 1.0:  # Log operations taking more than 1 second
                print(f"SLOW OPERATION: {func.__name__} took {duration:.2f}s")
    
    return wrapper


class ResourceManager:
    """Manage application resources and prevent memory leaks."""
    
    def __init__(self):
        self.resources: Dict[str, Any] = {}
        self.cleanup_callbacks: Dict[str, Callable] = {}
    
    def register(self, key: str, resource: Any, cleanup_callback: Callable = None) -> None:
        """Register a resource with optional cleanup callback."""
        self.resources[key] = resource
        if cleanup_callback:
            self.cleanup_callbacks[key] = cleanup_callback
    
    def get(self, key: str) -> Any:
        """Get a registered resource."""
        return self.resources.get(key)
    
    def cleanup(self, key: str) -> None:
        """Clean up a specific resource."""
        if key in self.cleanup_callbacks:
            try:
                self.cleanup_callbacks[key]()
            except Exception as e:
                print(f"Cleanup error for {key}: {e}")
            del self.cleanup_callbacks[key]
        
        self.resources.pop(key, None)
    
    def cleanup_all(self) -> None:
        """Clean up all resources."""
        for key in list(self.resources.keys()):
            self.cleanup(key)


# Global instances
memory_cache = MemoryCache()
debouncer = Debouncer()
batch_processor = BatchProcessor()
lazy_loader = LazyLoader()
resource_manager = ResourceManager()


def initialize_performance_optimizations():
    """Initialize all performance optimizations."""
    optimize_streamlit_config()
    
    # Register cleanup for session end
    import atexit
    atexit.register(resource_manager.cleanup_all)
    atexit.register(streamlit_cache_cleanup)


# Example usage functions
@cache_with_ttl(ttl=600)  # Cache for 10 minutes
def expensive_calculation(data):
    """Example of cached expensive calculation."""
    time.sleep(0.1)  # Simulate expensive operation
    return sum(data)


@performance_monitor
def monitored_function():
    """Example of monitored function."""
    time.sleep(0.5)  # Simulate work
    return "completed"


if __name__ == "__main__":
    # Example usage
    initialize_performance_optimizations()
    
    # Test caching
    result1 = expensive_calculation([1, 2, 3, 4, 5])
    result2 = expensive_calculation([1, 2, 3, 4, 5])  # Should be cached
    
    print(f"Results: {result1}, {result2}")
    
    # Test performance monitoring
    monitored_function()