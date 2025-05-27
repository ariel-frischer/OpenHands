"""TUI Resource Cleanup and Memory Management.

Provides proper resource cleanup and memory management for TUI components,
interfacing with existing OpenHands resource management utilities.
"""

import asyncio
import gc
import threading
import time
import weakref
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union

from openhands.core.logger import openhands_logger as logger
from openhands.runtime.utils.system_stats import get_system_stats


class TUIResourceTracker:
    """Tracks TUI resources for proper cleanup and memory management."""

    def __init__(self):
        """Initialize the resource tracker."""
        self._resources: Dict[str, Any] = {}
        self._weak_refs: Set[weakref.ref] = set()
        self._cleanup_callbacks: Dict[str, List[callable]] = {}
        self._lock = threading.RLock()
        self._memory_history: List[Dict] = []
        self._max_history = 100
        self._last_gc_time = time.time()
        self._gc_interval = 30.0  # Run GC every 30 seconds

    def register_resource(
        self,
        resource_id: str,
        resource: Any,
        cleanup_callback: Optional[callable] = None,
    ) -> None:
        """Register a resource for tracking and cleanup.

        Args:
            resource_id: Unique identifier for the resource
            resource: The resource object to track
            cleanup_callback: Optional cleanup function to call when resource is removed
        """
        with self._lock:
            self._resources[resource_id] = resource

            # Create weak reference for automatic cleanup detection
            def cleanup_ref(ref):
                self._weak_refs.discard(ref)
                if resource_id in self._resources:
                    logger.debug(f"Resource {resource_id} was garbage collected")
                    self.unregister_resource(resource_id)

            weak_ref = weakref.ref(resource, cleanup_ref)
            self._weak_refs.add(weak_ref)

            if cleanup_callback:
                if resource_id not in self._cleanup_callbacks:
                    self._cleanup_callbacks[resource_id] = []
                self._cleanup_callbacks[resource_id].append(cleanup_callback)

            logger.debug(f"Registered resource: {resource_id}")

    def unregister_resource(self, resource_id: str) -> None:
        """Unregister and cleanup a resource.

        Args:
            resource_id: Identifier of the resource to unregister
        """
        with self._lock:
            if resource_id in self._resources:
                resource = self._resources.pop(resource_id)

                # Execute cleanup callbacks
                if resource_id in self._cleanup_callbacks:
                    for callback in self._cleanup_callbacks[resource_id]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                # Schedule async cleanup
                                asyncio.create_task(callback(resource))
                            else:
                                callback(resource)
                        except Exception as e:
                            logger.error(
                                f"Error in cleanup callback for {resource_id}: {e}"
                            )

                    del self._cleanup_callbacks[resource_id]

                logger.debug(f"Unregistered resource: {resource_id}")

    def get_resource_count(self) -> int:
        """Get the number of tracked resources.

        Returns:
            Number of currently tracked resources
        """
        with self._lock:
            return len(self._resources)

    def get_resource_ids(self) -> List[str]:
        """Get list of all tracked resource IDs.

        Returns:
            List of resource identifiers
        """
        with self._lock:
            return list(self._resources.keys())

    def cleanup_all(self) -> None:
        """Clean up all tracked resources."""
        with self._lock:
            resource_ids = list(self._resources.keys())
            for resource_id in resource_ids:
                self.unregister_resource(resource_id)

            # Clear weak references
            self._weak_refs.clear()

            logger.info(f"Cleaned up {len(resource_ids)} resources")

    def update_memory_stats(self) -> Dict:
        """Update and return current memory statistics.

        Returns:
            Dictionary containing memory statistics
        """
        try:
            # Get system stats using existing OpenHands utility
            system_stats = get_system_stats()

            # Calculate TUI-specific metrics
            memory_stats = {
                "timestamp": datetime.now(),
                "system_memory_mb": system_stats["memory"]["rss"] / (1024 * 1024),
                "system_memory_percent": system_stats["memory"]["percent"],
                "tracked_resources": self.get_resource_count(),
                "weak_refs": len(self._weak_refs),
                "cpu_percent": system_stats["cpu_percent"],
                "disk_percent": system_stats["disk"]["percent"],
                "io_read_mb": system_stats["io"]["read_bytes"] / (1024 * 1024),
                "io_write_mb": system_stats["io"]["write_bytes"] / (1024 * 1024),
            }

            # Add to history
            self._memory_history.append(memory_stats)

            # Limit history size
            if len(self._memory_history) > self._max_history:
                self._memory_history.pop(0)

            # Trigger garbage collection if needed
            current_time = time.time()
            if current_time - self._last_gc_time > self._gc_interval:
                self._trigger_gc()
                self._last_gc_time = current_time

            return memory_stats

        except Exception as e:
            logger.error(f"Error updating memory stats: {e}")
            return {}

    def get_memory_history(self, duration_minutes: int = 5) -> List[Dict]:
        """Get memory history for a specified duration.

        Args:
            duration_minutes: Duration in minutes to retrieve history

        Returns:
            List of memory statistics dictionaries
        """
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        return [
            stats for stats in self._memory_history if stats["timestamp"] >= cutoff_time
        ]

    def get_memory_summary(self) -> Dict:
        """Get a summary of memory usage.

        Returns:
            Dictionary containing memory usage summary
        """
        if not self._memory_history:
            return {}

        recent_stats = self.get_memory_history(5)  # Last 5 minutes
        if not recent_stats:
            recent_stats = [self._memory_history[-1]]

        avg_memory = sum(s["system_memory_mb"] for s in recent_stats) / len(
            recent_stats
        )
        avg_cpu = sum(s["cpu_percent"] for s in recent_stats) / len(recent_stats)
        max_resources = max(s["tracked_resources"] for s in recent_stats)

        return {
            "average_memory_mb": avg_memory,
            "average_cpu_percent": avg_cpu,
            "max_tracked_resources": max_resources,
            "current_tracked_resources": self.get_resource_count(),
            "memory_samples": len(recent_stats),
            "last_update": self._memory_history[-1]["timestamp"]
            if self._memory_history
            else None,
        }

    def _trigger_gc(self) -> None:
        """Trigger garbage collection and log results."""
        try:
            before_count = len(gc.get_objects())
            collected = gc.collect()
            after_count = len(gc.get_objects())

            logger.debug(
                f"Garbage collection: collected {collected} objects, "
                f"objects before: {before_count}, after: {after_count}"
            )

        except Exception as e:
            logger.error(f"Error during garbage collection: {e}")


# Global resource tracker instance
_resource_tracker = TUIResourceTracker()


class TUIResourceManager:
    """Context manager for TUI resource management."""

    def __init__(
        self,
        resource_id: str,
        resource: Any,
        cleanup_callback: Optional[callable] = None,
    ):
        """Initialize the resource manager.

        Args:
            resource_id: Unique identifier for the resource
            resource: The resource object to manage
            cleanup_callback: Optional cleanup function
        """
        self.resource_id = resource_id
        self.resource = resource
        self.cleanup_callback = cleanup_callback

    def __enter__(self):
        """Enter the context manager."""
        _resource_tracker.register_resource(
            self.resource_id, self.resource, self.cleanup_callback
        )
        return self.resource

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        _resource_tracker.unregister_resource(self.resource_id)


class AsyncTUIResourceManager:
    """Async context manager for TUI resource management."""

    def __init__(
        self,
        resource_id: str,
        resource: Any,
        cleanup_callback: Optional[callable] = None,
    ):
        """Initialize the async resource manager.

        Args:
            resource_id: Unique identifier for the resource
            resource: The resource object to manage
            cleanup_callback: Optional cleanup function (can be async)
        """
        self.resource_id = resource_id
        self.resource = resource
        self.cleanup_callback = cleanup_callback

    async def __aenter__(self):
        """Enter the async context manager."""
        _resource_tracker.register_resource(
            self.resource_id, self.resource, self.cleanup_callback
        )
        return self.resource

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        _resource_tracker.unregister_resource(self.resource_id)


class TUIResourcePool:
    """Pool for reusing TUI resources to reduce memory allocation."""

    def __init__(self, max_size: int = 50):
        """Initialize the resource pool.

        Args:
            max_size: Maximum number of resources to pool
        """
        self.max_size = max_size
        self._pools: Dict[str, List[Any]] = {}
        self._lock = threading.RLock()

    def get_resource(self, resource_type: str, factory: callable) -> Any:
        """Get a resource from the pool or create a new one.

        Args:
            resource_type: Type identifier for the resource
            factory: Function to create new resource if pool is empty

        Returns:
            Resource instance
        """
        with self._lock:
            if resource_type in self._pools and self._pools[resource_type]:
                resource = self._pools[resource_type].pop()
                logger.debug(f"Reused pooled resource: {resource_type}")
                return resource
            else:
                resource = factory()
                logger.debug(f"Created new resource: {resource_type}")
                return resource

    def return_resource(self, resource_type: str, resource: Any) -> None:
        """Return a resource to the pool.

        Args:
            resource_type: Type identifier for the resource
            resource: Resource instance to return
        """
        with self._lock:
            if resource_type not in self._pools:
                self._pools[resource_type] = []

            if len(self._pools[resource_type]) < self.max_size:
                # Reset resource state if it has a reset method
                if hasattr(resource, "reset"):
                    try:
                        resource.reset()
                    except Exception as e:
                        logger.error(f"Error resetting resource {resource_type}: {e}")
                        return  # Don't pool if reset failed

                self._pools[resource_type].append(resource)
                logger.debug(f"Returned resource to pool: {resource_type}")
            else:
                logger.debug(f"Pool full, discarding resource: {resource_type}")

    def clear_pool(self, resource_type: Optional[str] = None) -> None:
        """Clear the resource pool.

        Args:
            resource_type: Specific resource type to clear, or None for all
        """
        with self._lock:
            if resource_type:
                if resource_type in self._pools:
                    count = len(self._pools[resource_type])
                    del self._pools[resource_type]
                    logger.info(f"Cleared {count} resources from pool: {resource_type}")
            else:
                total_count = sum(len(pool) for pool in self._pools.values())
                self._pools.clear()
                logger.info(f"Cleared all {total_count} resources from pools")

    def get_pool_stats(self) -> Dict[str, int]:
        """Get statistics about the resource pools.

        Returns:
            Dictionary mapping resource types to pool sizes
        """
        with self._lock:
            return {
                resource_type: len(pool) for resource_type, pool in self._pools.items()
            }


# Global resource pool instance
_resource_pool = TUIResourcePool()


# Context managers for easy resource management
@contextmanager
def managed_resource(
    resource_id: str, resource: Any, cleanup_callback: Optional[callable] = None
):
    """Context manager for managing a TUI resource.

    Args:
        resource_id: Unique identifier for the resource
        resource: The resource object to manage
        cleanup_callback: Optional cleanup function

    Yields:
        The managed resource
    """
    with TUIResourceManager(resource_id, resource, cleanup_callback) as managed:
        yield managed


@asynccontextmanager
async def async_managed_resource(
    resource_id: str, resource: Any, cleanup_callback: Optional[callable] = None
):
    """Async context manager for managing a TUI resource.

    Args:
        resource_id: Unique identifier for the resource
        resource: The resource object to manage
        cleanup_callback: Optional cleanup function (can be async)

    Yields:
        The managed resource
    """
    async with AsyncTUIResourceManager(
        resource_id, resource, cleanup_callback
    ) as managed:
        yield managed


@contextmanager
def pooled_resource(resource_type: str, factory: callable):
    """Context manager for using a pooled resource.

    Args:
        resource_type: Type identifier for the resource
        factory: Function to create new resource if pool is empty

    Yields:
        The pooled resource
    """
    resource = _resource_pool.get_resource(resource_type, factory)
    try:
        yield resource
    finally:
        _resource_pool.return_resource(resource_type, resource)


# Public API functions
def register_tui_resource(
    resource_id: str, resource: Any, cleanup_callback: Optional[callable] = None
) -> None:
    """Register a TUI resource for tracking.

    Args:
        resource_id: Unique identifier for the resource
        resource: The resource object to track
        cleanup_callback: Optional cleanup function
    """
    _resource_tracker.register_resource(resource_id, resource, cleanup_callback)


def unregister_tui_resource(resource_id: str) -> None:
    """Unregister a TUI resource.

    Args:
        resource_id: Identifier of the resource to unregister
    """
    _resource_tracker.unregister_resource(resource_id)


def cleanup_all_tui_resources() -> None:
    """Clean up all tracked TUI resources."""
    _resource_tracker.cleanup_all()
    _resource_pool.clear_pool()


def get_tui_memory_stats() -> Dict:
    """Get current TUI memory statistics.

    Returns:
        Dictionary containing memory statistics
    """
    return _resource_tracker.update_memory_stats()


def get_tui_memory_summary() -> Dict:
    """Get TUI memory usage summary.

    Returns:
        Dictionary containing memory usage summary
    """
    return _resource_tracker.get_memory_summary()


def get_tui_resource_stats() -> Dict:
    """Get TUI resource statistics.

    Returns:
        Dictionary containing resource statistics
    """
    return {
        "tracked_resources": _resource_tracker.get_resource_count(),
        "resource_ids": _resource_tracker.get_resource_ids(),
        "pool_stats": _resource_pool.get_pool_stats(),
        "memory_summary": get_tui_memory_summary(),
    }


def force_tui_garbage_collection() -> Dict:
    """Force garbage collection and return statistics.

    Returns:
        Dictionary containing garbage collection statistics
    """
    before_count = len(gc.get_objects())
    before_memory = get_tui_memory_stats().get("system_memory_mb", 0)

    collected = gc.collect()

    after_count = len(gc.get_objects())
    after_memory = get_tui_memory_stats().get("system_memory_mb", 0)

    return {
        "objects_before": before_count,
        "objects_after": after_count,
        "objects_collected": collected,
        "memory_before_mb": before_memory,
        "memory_after_mb": after_memory,
        "memory_freed_mb": before_memory - after_memory,
    }


class TUICleanupMixin:
    """Mixin class for TUI components that need resource cleanup."""

    def __init__(self, *args, **kwargs):
        """Initialize the cleanup mixin."""
        super().__init__(*args, **kwargs)
        self._resource_id = f"{self.__class__.__name__}_{id(self)}"
        self._cleanup_callbacks: List[callable] = []

        # Register self for cleanup tracking
        register_tui_resource(self._resource_id, self, self._cleanup_self)

    def add_cleanup_callback(self, callback: callable) -> None:
        """Add a cleanup callback.

        Args:
            callback: Function to call during cleanup
        """
        self._cleanup_callbacks.append(callback)

    def _cleanup_self(self, resource) -> None:
        """Internal cleanup method."""
        try:
            # Call all registered cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback())
                    else:
                        callback()
                except Exception as e:
                    logger.error(f"Error in cleanup callback: {e}")

            # Call cleanup method if it exists
            if hasattr(self, "cleanup"):
                self.cleanup()

        except Exception as e:
            logger.error(f"Error during TUI component cleanup: {e}")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            unregister_tui_resource(self._resource_id)
        except Exception:
            pass  # Ignore errors during destruction
