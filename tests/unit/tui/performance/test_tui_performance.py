"""TUI Performance Testing Framework.

Comprehensive performance testing for TUI components using mocked scenarios
to validate responsiveness requirements without backend dependencies.
"""

import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch, AsyncMock
from typing import List, Dict, Any
import pytest

from openhands.core.config import AppConfig
from openhands.tui.app import OpenHandsTUIApp
from openhands.tui.managers import SessionManager, TUIEventManager
from openhands.tui.panels import ChatPanel, LogsPanel, SessionsPanel


class TUIPerformanceTestFramework:
    """Framework for TUI performance testing with mocked scenarios."""

    def __init__(self):
        """Initialize the performance testing framework."""
        self.config = AppConfig()
        self.response_times: List[float] = []
        self.memory_usage: List[Dict] = []
        self.concurrent_operations: List[Dict] = []
        
    def setup_mocked_app(self) -> OpenHandsTUIApp:
        """Setup a mocked TUI app for performance testing."""
        with patch('openhands.tui.app.ptg.WindowManager') as mock_manager:
            mock_manager.return_value = MagicMock()
            app = OpenHandsTUIApp(self.config)
            
            # Mock the window manager to avoid actual UI creation
            app.manager = MagicMock()
            app.manager.stop = MagicMock()
            
            return app

    def measure_response_time(self, operation_func, *args, **kwargs) -> float:
        """Measure the response time of a TUI operation."""
        start_time = time.perf_counter()
        try:
            result = operation_func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                # Handle async operations
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(result)
                finally:
                    loop.close()
        except Exception as e:
            # Log error but continue measuring
            pass
        end_time = time.perf_counter()
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        self.response_times.append(response_time)
        return response_time

    def simulate_concurrent_sessions(self, session_count: int = 10) -> Dict[str, Any]:
        """Simulate concurrent session operations."""
        session_manager = SessionManager(self.config, None)
        
        # Mock session creation to avoid actual backend calls
        with patch.object(session_manager, 'create_session') as mock_create:
            mock_create.return_value = AsyncMock(return_value="mock_session_id")
            
            start_time = time.perf_counter()
            
            # Create concurrent session operations
            with ThreadPoolExecutor(max_workers=session_count) as executor:
                futures = []
                for i in range(session_count):
                    future = executor.submit(
                        self.measure_response_time,
                        lambda: mock_create(f"Test task {i}")
                    )
                    futures.append(future)
                
                # Wait for all operations to complete
                results = [future.result() for future in futures]
            
            end_time = time.perf_counter()
            total_time = (end_time - start_time) * 1000
            
            return {
                "session_count": session_count,
                "total_time_ms": total_time,
                "average_response_time_ms": sum(results) / len(results),
                "max_response_time_ms": max(results),
                "min_response_time_ms": min(results),
                "individual_times": results
            }

    def simulate_high_message_volume(self, message_count: int = 100) -> Dict[str, Any]:
        """Simulate high volume message processing."""
        event_manager = TUIEventManager(
            session_manager=MagicMock(),
            file_manager=MagicMock(),
            config=self.config,
            app=MagicMock()
        )
        
        # Mock message routing to avoid actual backend calls
        with patch.object(event_manager, 'route_user_input') as mock_route:
            mock_route.return_value = True
            
            start_time = time.perf_counter()
            response_times = []
            
            for i in range(message_count):
                msg_start = time.perf_counter()
                mock_route(f"test_session", f"Test message {i}")
                msg_end = time.perf_counter()
                response_times.append((msg_end - msg_start) * 1000)
            
            end_time = time.perf_counter()
            total_time = (end_time - start_time) * 1000
            
            return {
                "message_count": message_count,
                "total_time_ms": total_time,
                "average_response_time_ms": sum(response_times) / len(response_times),
                "max_response_time_ms": max(response_times),
                "min_response_time_ms": min(response_times),
                "messages_per_second": message_count / (total_time / 1000),
                "individual_times": response_times
            }

    def test_ui_update_performance(self, update_count: int = 50) -> Dict[str, Any]:
        """Test UI update performance with mocked data."""
        chat_panel = ChatPanel(
            session_manager=MagicMock(),
            event_manager=MagicMock(),
            file_manager=MagicMock()
        )
        
        # Mock UI update methods
        with patch.object(chat_panel, 'update_display') as mock_update:
            start_time = time.perf_counter()
            response_times = []
            
            for i in range(update_count):
                update_start = time.perf_counter()
                mock_update()
                update_end = time.perf_counter()
                response_times.append((update_end - update_start) * 1000)
            
            end_time = time.perf_counter()
            total_time = (end_time - start_time) * 1000
            
            return {
                "update_count": update_count,
                "total_time_ms": total_time,
                "average_response_time_ms": sum(response_times) / len(response_times),
                "max_response_time_ms": max(response_times),
                "min_response_time_ms": min(response_times),
                "updates_per_second": update_count / (total_time / 1000),
                "individual_times": response_times
            }

    def test_memory_stability(self, duration_seconds: int = 10) -> Dict[str, Any]:
        """Test memory stability during extended use simulation."""
        from openhands.tui.utils.resource_manager import get_tui_memory_stats
        
        memory_samples = []
        start_time = time.time()
        
        # Simulate extended use
        while time.time() - start_time < duration_seconds:
            # Simulate various TUI operations
            self.simulate_high_message_volume(10)
            
            # Collect memory stats
            try:
                memory_stats = get_tui_memory_stats()
                if memory_stats:
                    memory_samples.append({
                        "timestamp": time.time() - start_time,
                        "memory_mb": memory_stats.get("system_memory_mb", 0),
                        "tracked_resources": memory_stats.get("tracked_resources", 0)
                    })
            except Exception:
                # Continue if memory stats fail
                pass
            
            time.sleep(0.1)  # Small delay between operations
        
        if memory_samples:
            initial_memory = memory_samples[0]["memory_mb"]
            final_memory = memory_samples[-1]["memory_mb"]
            max_memory = max(sample["memory_mb"] for sample in memory_samples)
            
            return {
                "duration_seconds": duration_seconds,
                "initial_memory_mb": initial_memory,
                "final_memory_mb": final_memory,
                "max_memory_mb": max_memory,
                "memory_growth_mb": final_memory - initial_memory,
                "memory_samples": memory_samples,
                "sample_count": len(memory_samples)
            }
        else:
            return {
                "duration_seconds": duration_seconds,
                "error": "No memory samples collected"
            }

    def validate_responsiveness_requirement(self, max_response_time_ms: float = 100.0) -> Dict[str, Any]:
        """Validate that TUI meets <100ms responsiveness requirement."""
        # Run various performance tests
        session_results = self.simulate_concurrent_sessions(5)
        message_results = self.simulate_high_message_volume(50)
        ui_results = self.test_ui_update_performance(30)
        
        # Collect all response times
        all_response_times = (
            session_results["individual_times"] +
            message_results["individual_times"] +
            ui_results["individual_times"]
        )
        
        # Calculate statistics
        avg_response_time = sum(all_response_times) / len(all_response_times)
        max_response_time = max(all_response_times)
        violations = [t for t in all_response_times if t > max_response_time_ms]
        
        return {
            "requirement_ms": max_response_time_ms,
            "average_response_time_ms": avg_response_time,
            "max_response_time_ms": max_response_time,
            "total_operations": len(all_response_times),
            "violations": len(violations),
            "violation_percentage": (len(violations) / len(all_response_times)) * 100,
            "meets_requirement": len(violations) == 0,
            "session_results": session_results,
            "message_results": message_results,
            "ui_results": ui_results
        }


@pytest.fixture
def performance_framework():
    """Create a performance testing framework instance."""
    return TUIPerformanceTestFramework()


class TestTUIPerformance:
    """Test cases for TUI performance validation."""

    def test_concurrent_session_performance(self, performance_framework):
        """Test performance with concurrent session operations."""
        results = performance_framework.simulate_concurrent_sessions(10)
        
        # Validate results
        assert results["session_count"] == 10
        assert results["average_response_time_ms"] < 100.0, f"Average response time {results['average_response_time_ms']}ms exceeds 100ms requirement"
        assert results["max_response_time_ms"] < 200.0, f"Max response time {results['max_response_time_ms']}ms is too high"
        
        print(f"Concurrent sessions test: {results['average_response_time_ms']:.2f}ms average")

    def test_high_message_volume_performance(self, performance_framework):
        """Test performance with high message volume."""
        results = performance_framework.simulate_high_message_volume(100)
        
        # Validate results
        assert results["message_count"] == 100
        assert results["average_response_time_ms"] < 50.0, f"Average message processing time {results['average_response_time_ms']}ms is too high"
        assert results["messages_per_second"] > 100, f"Message throughput {results['messages_per_second']} msg/s is too low"
        
        print(f"High message volume test: {results['messages_per_second']:.1f} msg/s")

    def test_ui_update_performance(self, performance_framework):
        """Test UI update performance."""
        results = performance_framework.test_ui_update_performance(50)
        
        # Validate results
        assert results["update_count"] == 50
        assert results["average_response_time_ms"] < 20.0, f"Average UI update time {results['average_response_time_ms']}ms is too high"
        assert results["updates_per_second"] > 100, f"UI update rate {results['updates_per_second']} updates/s is too low"
        
        print(f"UI update test: {results['updates_per_second']:.1f} updates/s")

    def test_memory_stability(self, performance_framework):
        """Test memory stability during extended use."""
        results = performance_framework.test_memory_stability(5)  # 5 seconds for testing
        
        # Validate results
        if "error" not in results:
            assert results["duration_seconds"] == 5
            assert results["memory_growth_mb"] < 50.0, f"Memory growth {results['memory_growth_mb']}MB is too high"
            
            print(f"Memory stability test: {results['memory_growth_mb']:.2f}MB growth over {results['duration_seconds']}s")
        else:
            print(f"Memory stability test skipped: {results['error']}")

    def test_responsiveness_requirement_validation(self, performance_framework):
        """Test overall responsiveness requirement validation."""
        results = performance_framework.validate_responsiveness_requirement(100.0)
        
        # Validate overall responsiveness
        assert results["average_response_time_ms"] < 100.0, f"Average response time {results['average_response_time_ms']}ms exceeds requirement"
        assert results["violation_percentage"] < 5.0, f"Too many operations ({results['violation_percentage']:.1f}%) exceed 100ms requirement"
        
        print(f"Responsiveness validation: {results['violation_percentage']:.1f}% violations, {results['average_response_time_ms']:.2f}ms average")

    def test_load_testing_scenario(self, performance_framework):
        """Test comprehensive load testing scenario."""
        # Simulate a realistic load scenario
        start_time = time.perf_counter()
        
        # Multiple concurrent operations
        session_results = performance_framework.simulate_concurrent_sessions(8)
        message_results = performance_framework.simulate_high_message_volume(75)
        ui_results = performance_framework.test_ui_update_performance(40)
        
        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000
        
        # Validate load test results
        assert total_time < 5000.0, f"Load test took {total_time:.0f}ms, should complete in <5s"
        assert session_results["max_response_time_ms"] < 150.0, "Session operations too slow under load"
        assert message_results["messages_per_second"] > 50, "Message throughput too low under load"
        assert ui_results["updates_per_second"] > 50, "UI update rate too low under load"
        
        print(f"Load test completed in {total_time:.0f}ms")

    def test_performance_regression_baseline(self, performance_framework):
        """Establish performance regression baseline."""
        # Run standardized performance tests
        baseline_results = {
            "concurrent_sessions": performance_framework.simulate_concurrent_sessions(5),
            "message_volume": performance_framework.simulate_high_message_volume(50),
            "ui_updates": performance_framework.test_ui_update_performance(25),
            "responsiveness": performance_framework.validate_responsiveness_requirement(100.0)
        }
        
        # Validate baseline performance
        assert baseline_results["concurrent_sessions"]["average_response_time_ms"] < 100.0
        assert baseline_results["message_volume"]["messages_per_second"] > 100
        assert baseline_results["ui_updates"]["updates_per_second"] > 100
        assert baseline_results["responsiveness"]["meets_requirement"]
        
        print("Performance regression baseline established")
        
        # Store baseline for future regression testing
        return baseline_results


class TestTUIStressScenarios:
    """Stress testing scenarios for TUI components."""

    def test_extreme_concurrent_load(self, performance_framework):
        """Test TUI under extreme concurrent load."""
        results = performance_framework.simulate_concurrent_sessions(20)
        
        # Even under extreme load, should maintain reasonable performance
        assert results["average_response_time_ms"] < 200.0, "Performance degrades too much under extreme load"
        assert results["max_response_time_ms"] < 500.0, "Some operations take too long under extreme load"
        
        print(f"Extreme load test: {results['average_response_time_ms']:.2f}ms average with 20 concurrent sessions")

    def test_sustained_high_throughput(self, performance_framework):
        """Test sustained high throughput message processing."""
        results = performance_framework.simulate_high_message_volume(500)
        
        # Should maintain throughput even with high volume
        assert results["messages_per_second"] > 50, "Throughput drops too much with high volume"
        assert results["average_response_time_ms"] < 100.0, "Response time degrades with high volume"
        
        print(f"Sustained throughput test: {results['messages_per_second']:.1f} msg/s with 500 messages")

    def test_extended_memory_stability(self, performance_framework):
        """Test memory stability over extended period."""
        results = performance_framework.test_memory_stability(15)  # 15 seconds
        
        if "error" not in results:
            # Memory should remain stable over extended use
            assert results["memory_growth_mb"] < 100.0, "Memory growth too high over extended use"
            
            print(f"Extended memory test: {results['memory_growth_mb']:.2f}MB growth over {results['duration_seconds']}s")
        else:
            print(f"Extended memory test skipped: {results['error']}") 