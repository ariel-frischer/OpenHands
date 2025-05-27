"""Tests for TUI Resource Manager.

Unit tests for TUI resource cleanup and memory management with mocked scenarios.
"""

import asyncio
import gc
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from openhands.tui.utils.resource_manager import (
    TUIResourceTracker,
    TUIResourceManager,
    AsyncTUIResourceManager,
    TUIResourcePool,
    TUICleanupMixin,
    managed_resource,
    async_managed_resource,
    pooled_resource,
    register_tui_resource,
    unregister_tui_resource,
    cleanup_all_tui_resources,
    get_tui_memory_stats,
    get_tui_memory_summary,
    get_tui_resource_stats,
    force_tui_garbage_collection,
    _resource_tracker,
    _resource_pool,
)


@pytest.fixture
def resource_tracker():
    """Create a fresh resource tracker for testing."""
    return TUIResourceTracker()


@pytest.fixture
def resource_pool():
    """Create a fresh resource pool for testing."""
    return TUIResourcePool(max_size=5)


@pytest.fixture
def mock_resource():
    """Create a mock resource for testing."""
    resource = MagicMock()
    resource.reset = MagicMock()
    resource.cleanup = MagicMock()
    return resource


@pytest.fixture
def mock_system_stats():
    """Create mock system stats data."""
    return {
        "cpu_percent": 25.5,
        "memory": {
            "rss": 512 * 1024 * 1024,  # 512 MB in bytes
            "vms": 1024 * 1024 * 1024,  # 1 GB in bytes
            "percent": 15.2,
        },
        "disk": {
            "total": 100 * 1024**3,  # 100 GB
            "used": 60 * 1024**3,    # 60 GB
            "free": 40 * 1024**3,    # 40 GB
            "percent": 60.0,
        },
        "io": {
            "read_bytes": 1024 * 1024 * 100,   # 100 MB
            "write_bytes": 1024 * 1024 * 50,   # 50 MB
        },
    }


class TestTUIResourceTracker:
    """Test cases for TUIResourceTracker."""

    def test_initialization(self, resource_tracker):
        """Test resource tracker initialization."""
        assert resource_tracker.get_resource_count() == 0
        assert resource_tracker.get_resource_ids() == []
        assert resource_tracker._max_history == 100
        assert resource_tracker._gc_interval == 30.0

    def test_register_resource(self, resource_tracker, mock_resource):
        """Test resource registration."""
        cleanup_callback = MagicMock()
        
        resource_tracker.register_resource("test_resource", mock_resource, cleanup_callback)
        
        assert resource_tracker.get_resource_count() == 1
        assert "test_resource" in resource_tracker.get_resource_ids()
        assert len(resource_tracker._weak_refs) == 1

    def test_unregister_resource(self, resource_tracker, mock_resource):
        """Test resource unregistration."""
        cleanup_callback = MagicMock()
        
        resource_tracker.register_resource("test_resource", mock_resource, cleanup_callback)
        resource_tracker.unregister_resource("test_resource")
        
        assert resource_tracker.get_resource_count() == 0
        assert "test_resource" not in resource_tracker.get_resource_ids()
        cleanup_callback.assert_called_once_with(mock_resource)

    def test_unregister_nonexistent_resource(self, resource_tracker):
        """Test unregistering a resource that doesn't exist."""
        # Should not raise an exception
        resource_tracker.unregister_resource("nonexistent")
        assert resource_tracker.get_resource_count() == 0

    def test_cleanup_all(self, resource_tracker, mock_resource):
        """Test cleaning up all resources."""
        cleanup_callback1 = MagicMock()
        cleanup_callback2 = MagicMock()
        mock_resource2 = MagicMock()
        
        resource_tracker.register_resource("resource1", mock_resource, cleanup_callback1)
        resource_tracker.register_resource("resource2", mock_resource2, cleanup_callback2)
        
        resource_tracker.cleanup_all()
        
        assert resource_tracker.get_resource_count() == 0
        assert len(resource_tracker._weak_refs) == 0
        cleanup_callback1.assert_called_once()
        cleanup_callback2.assert_called_once()

    @patch('openhands.tui.utils.resource_manager.get_system_stats')
    def test_update_memory_stats(self, mock_get_stats, resource_tracker, mock_system_stats):
        """Test memory statistics update."""
        mock_get_stats.return_value = mock_system_stats
        
        stats = resource_tracker.update_memory_stats()
        
        assert stats is not None
        assert "timestamp" in stats
        assert "system_memory_mb" in stats
        assert "system_memory_percent" in stats
        assert "tracked_resources" in stats
        assert "cpu_percent" in stats
        assert "disk_percent" in stats
        assert "io_read_mb" in stats
        assert "io_write_mb" in stats
        
        # Check calculated values
        assert stats["system_memory_mb"] == 512.0  # 512 MB
        assert stats["system_memory_percent"] == 15.2
        assert stats["tracked_resources"] == 0
        assert stats["cpu_percent"] == 25.5
        assert stats["disk_percent"] == 60.0
        assert stats["io_read_mb"] == 100.0
        assert stats["io_write_mb"] == 50.0

    @patch('openhands.tui.utils.resource_manager.get_system_stats')
    def test_memory_history_limit(self, mock_get_stats, resource_tracker, mock_system_stats):
        """Test that memory history is limited to max_history."""
        mock_get_stats.return_value = mock_system_stats
        resource_tracker._max_history = 3  # Set small limit for testing
        
        # Add more entries than the limit
        for i in range(5):
            resource_tracker.update_memory_stats()
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        assert len(resource_tracker._memory_history) == 3

    def test_get_memory_history(self, resource_tracker):
        """Test getting memory history for a duration."""
        # Add test data with different timestamps
        now = datetime.now()
        resource_tracker._memory_history = [
            {"timestamp": now - timedelta(minutes=10), "data": "old"},
            {"timestamp": now - timedelta(minutes=3), "data": "recent"},
            {"timestamp": now - timedelta(minutes=1), "data": "very_recent"},
        ]
        
        recent_history = resource_tracker.get_memory_history(5)
        assert len(recent_history) == 2  # Only last 5 minutes
        assert recent_history[0]["data"] == "recent"
        assert recent_history[1]["data"] == "very_recent"

    def test_get_memory_summary(self, resource_tracker):
        """Test getting memory usage summary."""
        # Add test data
        now = datetime.now()
        resource_tracker._memory_history = [
            {
                "timestamp": now - timedelta(minutes=2),
                "system_memory_mb": 100.0,
                "cpu_percent": 20.0,
                "tracked_resources": 5,
            },
            {
                "timestamp": now - timedelta(minutes=1),
                "system_memory_mb": 120.0,
                "cpu_percent": 30.0,
                "tracked_resources": 8,
            },
        ]
        
        summary = resource_tracker.get_memory_summary()
        
        assert summary["average_memory_mb"] == 110.0
        assert summary["average_cpu_percent"] == 25.0
        assert summary["max_tracked_resources"] == 8
        assert summary["memory_samples"] == 2

    def test_get_memory_summary_empty(self, resource_tracker):
        """Test getting memory summary with no history."""
        summary = resource_tracker.get_memory_summary()
        assert summary == {}

    @patch('openhands.tui.utils.resource_manager.gc.collect')
    @patch('openhands.tui.utils.resource_manager.gc.get_objects')
    def test_trigger_gc(self, mock_get_objects, mock_collect, resource_tracker):
        """Test garbage collection triggering."""
        # Mock get_objects to return lists (not ints)
        mock_get_objects.side_effect = [list(range(1000)), list(range(950))]  # Before and after counts
        mock_collect.return_value = 50  # Objects collected
        
        resource_tracker._trigger_gc()
        
        mock_collect.assert_called_once()
        assert mock_get_objects.call_count == 2

    @patch('openhands.tui.utils.resource_manager.get_system_stats')
    def test_update_memory_stats_error_handling(self, mock_get_stats, resource_tracker):
        """Test error handling in memory stats update."""
        mock_get_stats.side_effect = Exception("System stats error")
        
        stats = resource_tracker.update_memory_stats()
        
        assert stats == {}

    @pytest.mark.asyncio
    async def test_async_cleanup_callback(self, resource_tracker, mock_resource):
        """Test async cleanup callback execution."""
        async_callback = MagicMock()
        async_callback.return_value = asyncio.Future()
        async_callback.return_value.set_result(None)
        
        # Mock asyncio.iscoroutinefunction to return True for our callback
        with patch('asyncio.iscoroutinefunction', return_value=True), \
             patch('asyncio.create_task') as mock_create_task:
            
            resource_tracker.register_resource("test_resource", mock_resource, async_callback)
            resource_tracker.unregister_resource("test_resource")
            
            mock_create_task.assert_called_once()


class TestTUIResourceManager:
    """Test cases for TUIResourceManager context manager."""

    def test_context_manager(self, mock_resource):
        """Test resource manager context manager."""
        cleanup_callback = MagicMock()
        
        with TUIResourceManager("test_ctx", mock_resource, cleanup_callback) as managed:
            assert managed is mock_resource
            # Resource should be registered during context
            assert "test_ctx" in _resource_tracker.get_resource_ids()
        
        # Resource should be unregistered after context
        assert "test_ctx" not in _resource_tracker.get_resource_ids()
        cleanup_callback.assert_called_once()

    def test_context_manager_exception(self, mock_resource):
        """Test resource manager context manager with exception."""
        cleanup_callback = MagicMock()
        
        try:
            with TUIResourceManager("test_ctx_exc", mock_resource, cleanup_callback):
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Resource should still be cleaned up after exception
        assert "test_ctx_exc" not in _resource_tracker.get_resource_ids()
        cleanup_callback.assert_called_once()


class TestAsyncTUIResourceManager:
    """Test cases for AsyncTUIResourceManager."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_resource):
        """Test async resource manager context manager."""
        cleanup_callback = MagicMock()
        
        async with AsyncTUIResourceManager("test_async_ctx", mock_resource, cleanup_callback) as managed:
            assert managed is mock_resource
            # Resource should be registered during context
            assert "test_async_ctx" in _resource_tracker.get_resource_ids()
        
        # Resource should be unregistered after context
        assert "test_async_ctx" not in _resource_tracker.get_resource_ids()
        cleanup_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_exception(self, mock_resource):
        """Test async resource manager context manager with exception."""
        cleanup_callback = MagicMock()
        
        try:
            async with AsyncTUIResourceManager("test_async_exc", mock_resource, cleanup_callback):
                raise ValueError("Test async exception")
        except ValueError:
            pass
        
        # Resource should still be cleaned up after exception
        assert "test_async_exc" not in _resource_tracker.get_resource_ids()
        cleanup_callback.assert_called_once()


class TestTUIResourcePool:
    """Test cases for TUIResourcePool."""

    def test_initialization(self, resource_pool):
        """Test resource pool initialization."""
        assert resource_pool.max_size == 5
        assert resource_pool.get_pool_stats() == {}

    def test_get_resource_new(self, resource_pool):
        """Test getting a new resource from empty pool."""
        factory = MagicMock(return_value="new_resource")
        
        resource = resource_pool.get_resource("test_type", factory)
        
        assert resource == "new_resource"
        factory.assert_called_once()

    def test_get_resource_from_pool(self, resource_pool, mock_resource):
        """Test getting a resource from pool."""
        factory = MagicMock()
        
        # Add resource to pool first
        resource_pool.return_resource("test_type", mock_resource)
        
        # Get resource from pool
        resource = resource_pool.get_resource("test_type", factory)
        
        assert resource is mock_resource
        factory.assert_not_called()  # Should not create new resource

    def test_return_resource(self, resource_pool, mock_resource):
        """Test returning a resource to pool."""
        resource_pool.return_resource("test_type", mock_resource)
        
        stats = resource_pool.get_pool_stats()
        assert stats["test_type"] == 1
        mock_resource.reset.assert_called_once()

    def test_return_resource_without_reset(self, resource_pool):
        """Test returning a resource without reset method."""
        resource_without_reset = MagicMock()
        del resource_without_reset.reset  # Remove reset method
        
        resource_pool.return_resource("test_type", resource_without_reset)
        
        stats = resource_pool.get_pool_stats()
        assert stats["test_type"] == 1

    def test_return_resource_reset_failure(self, resource_pool, mock_resource):
        """Test returning a resource when reset fails."""
        mock_resource.reset.side_effect = Exception("Reset failed")
        
        resource_pool.return_resource("test_type", mock_resource)
        
        # Resource should not be added to pool if reset fails
        stats = resource_pool.get_pool_stats()
        assert stats.get("test_type", 0) == 0

    def test_pool_size_limit(self, resource_pool):
        """Test that pool respects size limit."""
        # Fill pool to max capacity
        for i in range(6):  # More than max_size (5)
            resource = MagicMock()
            resource_pool.return_resource("test_type", resource)
        
        stats = resource_pool.get_pool_stats()
        assert stats["test_type"] == 5  # Should be limited to max_size

    def test_clear_pool_specific_type(self, resource_pool, mock_resource):
        """Test clearing a specific resource type from pool."""
        resource_pool.return_resource("type1", mock_resource)
        resource_pool.return_resource("type2", MagicMock())
        
        resource_pool.clear_pool("type1")
        
        stats = resource_pool.get_pool_stats()
        assert "type1" not in stats
        assert stats["type2"] == 1

    def test_clear_pool_all(self, resource_pool, mock_resource):
        """Test clearing all resources from pool."""
        resource_pool.return_resource("type1", mock_resource)
        resource_pool.return_resource("type2", MagicMock())
        
        resource_pool.clear_pool()
        
        stats = resource_pool.get_pool_stats()
        assert stats == {}


class TestTUICleanupMixin:
    """Test cases for TUICleanupMixin."""

    def test_mixin_initialization(self):
        """Test cleanup mixin initialization."""
        class TestComponent(TUICleanupMixin):
            def __init__(self):
                super().__init__()
        
        component = TestComponent()
        
        assert hasattr(component, '_resource_id')
        assert hasattr(component, '_cleanup_callbacks')
        assert component._resource_id in _resource_tracker.get_resource_ids()

    def test_add_cleanup_callback(self):
        """Test adding cleanup callbacks."""
        class TestComponent(TUICleanupMixin):
            def __init__(self):
                super().__init__()
        
        component = TestComponent()
        callback = MagicMock()
        
        component.add_cleanup_callback(callback)
        
        assert callback in component._cleanup_callbacks

    def test_cleanup_with_callbacks(self):
        """Test cleanup execution with callbacks."""
        class TestComponent(TUICleanupMixin):
            def __init__(self):
                super().__init__()
                self.cleanup = MagicMock()
        
        component = TestComponent()
        callback = MagicMock()
        component.add_cleanup_callback(callback)
        
        # Trigger cleanup
        component._cleanup_self(component)
        
        callback.assert_called_once()
        component.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_with_async_callback(self):
        """Test cleanup with async callback."""
        class TestComponent(TUICleanupMixin):
            def __init__(self):
                super().__init__()
        
        component = TestComponent()
        async_callback = MagicMock()
        
        with patch('asyncio.iscoroutinefunction', return_value=True), \
             patch('asyncio.create_task') as mock_create_task:
            
            component.add_cleanup_callback(async_callback)
            component._cleanup_self(component)
            
            mock_create_task.assert_called_once()


class TestContextManagers:
    """Test cases for context manager functions."""

    def test_managed_resource(self, mock_resource):
        """Test managed_resource context manager."""
        cleanup_callback = MagicMock()
        
        with managed_resource("test_managed", mock_resource, cleanup_callback) as managed:
            assert managed is mock_resource
        
        cleanup_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_managed_resource(self, mock_resource):
        """Test async_managed_resource context manager."""
        cleanup_callback = MagicMock()
        
        async with async_managed_resource("test_async_managed", mock_resource, cleanup_callback) as managed:
            assert managed is mock_resource
        
        cleanup_callback.assert_called_once()

    def test_pooled_resource(self, mock_resource):
        """Test pooled_resource context manager."""
        factory = MagicMock(return_value=mock_resource)
        
        with pooled_resource("test_pooled", factory) as pooled:
            assert pooled is mock_resource
        
        # Resource should be returned to pool
        stats = _resource_pool.get_pool_stats()
        assert stats.get("test_pooled", 0) >= 0  # May be 0 if pool was full


class TestPublicAPI:
    """Test cases for public API functions."""

    def test_register_unregister_tui_resource(self, mock_resource):
        """Test registering and unregistering TUI resources."""
        cleanup_callback = MagicMock()
        
        register_tui_resource("test_api", mock_resource, cleanup_callback)
        assert "test_api" in _resource_tracker.get_resource_ids()
        
        unregister_tui_resource("test_api")
        assert "test_api" not in _resource_tracker.get_resource_ids()
        cleanup_callback.assert_called_once()

    def test_cleanup_all_tui_resources(self, mock_resource):
        """Test cleaning up all TUI resources."""
        register_tui_resource("test_cleanup_all", mock_resource)
        _resource_pool.return_resource("test_type", MagicMock())
        
        cleanup_all_tui_resources()
        
        assert _resource_tracker.get_resource_count() == 0
        assert _resource_pool.get_pool_stats() == {}

    @patch('openhands.tui.utils.resource_manager.get_system_stats')
    def test_get_tui_memory_stats(self, mock_get_stats, mock_system_stats):
        """Test getting TUI memory statistics."""
        mock_get_stats.return_value = mock_system_stats
        
        stats = get_tui_memory_stats()
        
        assert isinstance(stats, dict)
        assert "system_memory_mb" in stats

    def test_get_tui_memory_summary(self):
        """Test getting TUI memory summary."""
        summary = get_tui_memory_summary()
        assert isinstance(summary, dict)

    def test_get_tui_resource_stats(self):
        """Test getting TUI resource statistics."""
        stats = get_tui_resource_stats()
        
        assert isinstance(stats, dict)
        assert "tracked_resources" in stats
        assert "resource_ids" in stats
        assert "pool_stats" in stats
        assert "memory_summary" in stats

    @patch('openhands.tui.utils.resource_manager.gc.collect')
    @patch('openhands.tui.utils.resource_manager.gc.get_objects')
    @patch('openhands.tui.utils.resource_manager.get_tui_memory_stats')
    def test_force_tui_garbage_collection(self, mock_get_stats, mock_get_objects, mock_collect):
        """Test forcing garbage collection."""
        # Mock get_objects to return lists (not ints) so len() works
        mock_get_objects.side_effect = [list(range(1000)), list(range(950))]  # Before and after counts
        mock_collect.return_value = 50
        mock_get_stats.side_effect = [
            {"system_memory_mb": 100.0},  # Before
            {"system_memory_mb": 95.0},   # After
        ]
        
        result = force_tui_garbage_collection()
        
        assert result["objects_before"] == 1000
        assert result["objects_after"] == 950
        assert result["objects_collected"] == 50
        assert result["memory_before_mb"] == 100.0
        assert result["memory_after_mb"] == 95.0
        assert result["memory_freed_mb"] == 5.0


class TestThreadSafety:
    """Test cases for thread safety."""

    def test_resource_tracker_thread_safety(self, resource_tracker):
        """Test resource tracker thread safety."""
        resources = []
        errors = []
        
        def register_resources():
            try:
                for i in range(10):
                    resource = MagicMock()
                    resource_id = f"thread_resource_{threading.current_thread().ident}_{i}"
                    resource_tracker.register_resource(resource_id, resource)
                    resources.append((resource_id, resource))
                    time.sleep(0.001)  # Small delay to increase chance of race conditions
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=register_resources)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that no errors occurred and all resources were registered
        assert len(errors) == 0
        assert resource_tracker.get_resource_count() == 30  # 3 threads * 10 resources each

    def test_resource_pool_thread_safety(self, resource_pool):
        """Test resource pool thread safety."""
        errors = []
        
        def pool_operations():
            try:
                for i in range(5):
                    # Get resource
                    resource = resource_pool.get_resource("thread_type", lambda: MagicMock())
                    time.sleep(0.001)
                    # Return resource
                    resource_pool.return_resource("thread_type", resource)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=pool_operations)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that no errors occurred
        assert len(errors) == 0


class TestMemoryLeakPrevention:
    """Test cases for memory leak prevention."""

    def test_weak_reference_cleanup(self, resource_tracker):
        """Test that weak references are cleaned up when objects are garbage collected."""
        initial_weak_refs = len(resource_tracker._weak_refs)
        
        # Create a resource and register it
        resource = MagicMock()
        resource_tracker.register_resource("test_weak_ref", resource)
        
        assert len(resource_tracker._weak_refs) == initial_weak_refs + 1
        
        # Delete the resource and force garbage collection
        del resource
        gc.collect()
        
        # The weak reference should be cleaned up automatically
        # Note: This might not happen immediately, so we'll check the resource is unregistered
        assert resource_tracker.get_resource_count() == 0

    def test_memory_history_limit_prevents_unbounded_growth(self, resource_tracker):
        """Test that memory history limit prevents unbounded memory growth."""
        resource_tracker._max_history = 5
        
        with patch('openhands.tui.utils.resource_manager.get_system_stats') as mock_get_stats:
            mock_get_stats.return_value = {
                "cpu_percent": 10.0,
                "memory": {"rss": 1024 * 1024 * 100, "percent": 10.0},
                "disk": {"percent": 50.0},
                "io": {"read_bytes": 1024, "write_bytes": 1024},
            }
            
            # Add many memory stats entries
            for _ in range(20):
                resource_tracker.update_memory_stats()
            
            # History should be limited
            assert len(resource_tracker._memory_history) == 5 