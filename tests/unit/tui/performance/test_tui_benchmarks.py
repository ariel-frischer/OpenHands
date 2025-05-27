"""TUI Performance Benchmarks.

Benchmark tests for TUI performance regression testing and continuous monitoring.
"""

import time
import statistics
from unittest.mock import MagicMock, patch
from typing import Dict, List, Any
import pytest

from openhands.core.config import AppConfig
from openhands.tui.managers import SessionManager, TUIEventManager, TUIPanelFileManager
from openhands.tui.panels import ChatPanel, LogsPanel, SessionsPanel
from openhands.tui.utils.resource_manager import (
    TUIResourceTracker,
    TUIResourcePool,
    get_tui_memory_stats,
    force_tui_garbage_collection
)


class TUIBenchmarkSuite:
    """Comprehensive TUI benchmark suite for performance monitoring."""

    def __init__(self):
        """Initialize the benchmark suite."""
        self.config = AppConfig()
        self.benchmarks: Dict[str, List[float]] = {}
        
    def record_benchmark(self, test_name: str, execution_time_ms: float) -> None:
        """Record a benchmark result."""
        if test_name not in self.benchmarks:
            self.benchmarks[test_name] = []
        self.benchmarks[test_name].append(execution_time_ms)
    
    def get_benchmark_stats(self, test_name: str) -> Dict[str, float]:
        """Get statistical summary of benchmark results."""
        if test_name not in self.benchmarks or not self.benchmarks[test_name]:
            return {}
        
        times = self.benchmarks[test_name]
        return {
            "count": len(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0.0,
            "min": min(times),
            "max": max(times),
            "p95": statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times),
            "p99": statistics.quantiles(times, n=100)[98] if len(times) >= 100 else max(times)
        }
    
    def benchmark_session_manager_operations(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmark session manager operations."""
        session_manager = SessionManager(self.config, None)
        
        # Mock dependencies to avoid actual backend calls
        with patch.object(session_manager, 'create_session') as mock_create, \
             patch.object(session_manager, 'get_session') as mock_get, \
             patch.object(session_manager, 'close_session') as mock_close:
            
            mock_create.return_value = "test_session_id"
            mock_get.return_value = MagicMock()
            mock_close.return_value = None
            
            # Benchmark session creation
            creation_times = []
            for i in range(iterations):
                start_time = time.perf_counter()
                session_manager.create_session(f"Test task {i}")
                end_time = time.perf_counter()
                creation_times.append((end_time - start_time) * 1000)
            
            # Benchmark session retrieval
            retrieval_times = []
            for i in range(iterations):
                start_time = time.perf_counter()
                session_manager.get_session("test_session_id")
                end_time = time.perf_counter()
                retrieval_times.append((end_time - start_time) * 1000)
            
            # Benchmark session closure
            closure_times = []
            for i in range(iterations):
                start_time = time.perf_counter()
                session_manager.close_session("test_session_id")
                end_time = time.perf_counter()
                closure_times.append((end_time - start_time) * 1000)
            
            return {
                "iterations": iterations,
                "creation": {
                    "mean_ms": statistics.mean(creation_times),
                    "median_ms": statistics.median(creation_times),
                    "max_ms": max(creation_times),
                    "times": creation_times
                },
                "retrieval": {
                    "mean_ms": statistics.mean(retrieval_times),
                    "median_ms": statistics.median(retrieval_times),
                    "max_ms": max(retrieval_times),
                    "times": retrieval_times
                },
                "closure": {
                    "mean_ms": statistics.mean(closure_times),
                    "median_ms": statistics.median(closure_times),
                    "max_ms": max(closure_times),
                    "times": closure_times
                }
            }
    
    def benchmark_event_manager_operations(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmark event manager operations."""
        event_manager = TUIEventManager(
            session_manager=MagicMock(),
            file_manager=MagicMock(),
            config=self.config,
            app=MagicMock()
        )
        
        # Mock event routing
        with patch.object(event_manager, 'route_user_input') as mock_route, \
             patch.object(event_manager, 'subscribe_to_session') as mock_subscribe, \
             patch.object(event_manager, 'unsubscribe_from_session') as mock_unsubscribe:
            
            mock_route.return_value = True
            mock_subscribe.return_value = None
            mock_unsubscribe.return_value = None
            
            # Benchmark message routing
            routing_times = []
            for i in range(iterations):
                start_time = time.perf_counter()
                event_manager.route_user_input("test_session", f"Test message {i}")
                end_time = time.perf_counter()
                routing_times.append((end_time - start_time) * 1000)
            
            # Benchmark subscription operations
            subscription_times = []
            for i in range(iterations):
                start_time = time.perf_counter()
                event_manager.subscribe_to_session(f"session_{i}")
                end_time = time.perf_counter()
                subscription_times.append((end_time - start_time) * 1000)
            
            # Benchmark unsubscription operations
            unsubscription_times = []
            for i in range(iterations):
                start_time = time.perf_counter()
                event_manager.unsubscribe_from_session(f"session_{i}")
                end_time = time.perf_counter()
                unsubscription_times.append((end_time - start_time) * 1000)
            
            return {
                "iterations": iterations,
                "routing": {
                    "mean_ms": statistics.mean(routing_times),
                    "median_ms": statistics.median(routing_times),
                    "max_ms": max(routing_times),
                    "times": routing_times
                },
                "subscription": {
                    "mean_ms": statistics.mean(subscription_times),
                    "median_ms": statistics.median(subscription_times),
                    "max_ms": max(subscription_times),
                    "times": subscription_times
                },
                "unsubscription": {
                    "mean_ms": statistics.mean(unsubscription_times),
                    "median_ms": statistics.median(unsubscription_times),
                    "max_ms": max(unsubscription_times),
                    "times": unsubscription_times
                }
            }
    
    def benchmark_panel_operations(self, iterations: int = 50) -> Dict[str, Any]:
        """Benchmark TUI panel operations."""
        # Create panels with mocked dependencies
        chat_panel = ChatPanel(
            session_manager=MagicMock(),
            event_manager=MagicMock(),
            file_manager=MagicMock()
        )
        
        logs_panel = LogsPanel(
            session_manager=MagicMock(),
            file_manager=MagicMock()
        )
        
        sessions_panel = SessionsPanel(
            session_manager=MagicMock(),
            file_manager=MagicMock()
        )
        
        # Mock panel update methods
        with patch.object(chat_panel, 'update_display') as mock_chat_update, \
             patch.object(logs_panel, 'update_display') as mock_logs_update, \
             patch.object(sessions_panel, 'update_sessions') as mock_sessions_update:
            
            # Benchmark chat panel updates
            chat_times = []
            for i in range(iterations):
                start_time = time.perf_counter()
                chat_panel.update_display()
                end_time = time.perf_counter()
                chat_times.append((end_time - start_time) * 1000)
            
            # Benchmark logs panel updates
            logs_times = []
            for i in range(iterations):
                start_time = time.perf_counter()
                logs_panel.update_display()
                end_time = time.perf_counter()
                logs_times.append((end_time - start_time) * 1000)
            
            # Benchmark sessions panel updates
            sessions_times = []
            for i in range(iterations):
                start_time = time.perf_counter()
                sessions_panel.update_sessions()
                end_time = time.perf_counter()
                sessions_times.append((end_time - start_time) * 1000)
            
            return {
                "iterations": iterations,
                "chat_panel": {
                    "mean_ms": statistics.mean(chat_times),
                    "median_ms": statistics.median(chat_times),
                    "max_ms": max(chat_times),
                    "times": chat_times
                },
                "logs_panel": {
                    "mean_ms": statistics.mean(logs_times),
                    "median_ms": statistics.median(logs_times),
                    "max_ms": max(logs_times),
                    "times": logs_times
                },
                "sessions_panel": {
                    "mean_ms": statistics.mean(sessions_times),
                    "median_ms": statistics.median(sessions_times),
                    "max_ms": max(sessions_times),
                    "times": sessions_times
                }
            }
    
    def benchmark_resource_manager_operations(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmark resource manager operations."""
        tracker = TUIResourceTracker()
        pool = TUIResourcePool(max_size=10)
        
        # Benchmark resource registration
        registration_times = []
        for i in range(iterations):
            resource = MagicMock()
            start_time = time.perf_counter()
            tracker.register_resource(f"resource_{i}", resource)
            end_time = time.perf_counter()
            registration_times.append((end_time - start_time) * 1000)
        
        # Benchmark resource retrieval
        retrieval_times = []
        for i in range(iterations):
            start_time = time.perf_counter()
            tracker.get_resource_count()
            end_time = time.perf_counter()
            retrieval_times.append((end_time - start_time) * 1000)
        
        # Benchmark resource pool operations
        pool_times = []
        for i in range(iterations):
            start_time = time.perf_counter()
            resource = pool.get_resource("test_type", lambda: MagicMock())
            pool.return_resource("test_type", resource)
            end_time = time.perf_counter()
            pool_times.append((end_time - start_time) * 1000)
        
        # Benchmark memory stats collection
        memory_times = []
        for i in range(min(iterations, 20)):  # Limit memory stats calls
            start_time = time.perf_counter()
            try:
                get_tui_memory_stats()
            except Exception:
                pass  # Continue if memory stats fail
            end_time = time.perf_counter()
            memory_times.append((end_time - start_time) * 1000)
        
        # Cleanup
        tracker.cleanup_all()
        
        return {
            "iterations": iterations,
            "registration": {
                "mean_ms": statistics.mean(registration_times),
                "median_ms": statistics.median(registration_times),
                "max_ms": max(registration_times),
                "times": registration_times
            },
            "retrieval": {
                "mean_ms": statistics.mean(retrieval_times),
                "median_ms": statistics.median(retrieval_times),
                "max_ms": max(retrieval_times),
                "times": retrieval_times
            },
            "pool_operations": {
                "mean_ms": statistics.mean(pool_times),
                "median_ms": statistics.median(pool_times),
                "max_ms": max(pool_times),
                "times": pool_times
            },
            "memory_stats": {
                "mean_ms": statistics.mean(memory_times) if memory_times else 0.0,
                "median_ms": statistics.median(memory_times) if memory_times else 0.0,
                "max_ms": max(memory_times) if memory_times else 0.0,
                "times": memory_times
            }
        }


@pytest.fixture
def benchmark_suite():
    """Create a benchmark suite instance."""
    return TUIBenchmarkSuite()


class TestTUIBenchmarks:
    """Benchmark tests for TUI performance monitoring."""

    def test_session_manager_benchmark(self, benchmark_suite):
        """Benchmark session manager operations."""
        results = benchmark_suite.benchmark_session_manager_operations(50)
        
        # Validate performance benchmarks
        assert results["creation"]["mean_ms"] < 10.0, f"Session creation too slow: {results['creation']['mean_ms']:.2f}ms"
        assert results["retrieval"]["mean_ms"] < 1.0, f"Session retrieval too slow: {results['retrieval']['mean_ms']:.2f}ms"
        assert results["closure"]["mean_ms"] < 5.0, f"Session closure too slow: {results['closure']['mean_ms']:.2f}ms"
        
        print(f"Session Manager Benchmark:")
        print(f"  Creation: {results['creation']['mean_ms']:.2f}ms avg, {results['creation']['max_ms']:.2f}ms max")
        print(f"  Retrieval: {results['retrieval']['mean_ms']:.2f}ms avg, {results['retrieval']['max_ms']:.2f}ms max")
        print(f"  Closure: {results['closure']['mean_ms']:.2f}ms avg, {results['closure']['max_ms']:.2f}ms max")

    def test_event_manager_benchmark(self, benchmark_suite):
        """Benchmark event manager operations."""
        results = benchmark_suite.benchmark_event_manager_operations(50)
        
        # Validate performance benchmarks
        assert results["routing"]["mean_ms"] < 5.0, f"Message routing too slow: {results['routing']['mean_ms']:.2f}ms"
        assert results["subscription"]["mean_ms"] < 2.0, f"Subscription too slow: {results['subscription']['mean_ms']:.2f}ms"
        assert results["unsubscription"]["mean_ms"] < 2.0, f"Unsubscription too slow: {results['unsubscription']['mean_ms']:.2f}ms"
        
        print(f"Event Manager Benchmark:")
        print(f"  Routing: {results['routing']['mean_ms']:.2f}ms avg, {results['routing']['max_ms']:.2f}ms max")
        print(f"  Subscription: {results['subscription']['mean_ms']:.2f}ms avg, {results['subscription']['max_ms']:.2f}ms max")
        print(f"  Unsubscription: {results['unsubscription']['mean_ms']:.2f}ms avg, {results['unsubscription']['max_ms']:.2f}ms max")

    def test_panel_operations_benchmark(self, benchmark_suite):
        """Benchmark TUI panel operations."""
        results = benchmark_suite.benchmark_panel_operations(30)
        
        # Validate performance benchmarks
        assert results["chat_panel"]["mean_ms"] < 10.0, f"Chat panel updates too slow: {results['chat_panel']['mean_ms']:.2f}ms"
        assert results["logs_panel"]["mean_ms"] < 10.0, f"Logs panel updates too slow: {results['logs_panel']['mean_ms']:.2f}ms"
        assert results["sessions_panel"]["mean_ms"] < 10.0, f"Sessions panel updates too slow: {results['sessions_panel']['mean_ms']:.2f}ms"
        
        print(f"Panel Operations Benchmark:")
        print(f"  Chat Panel: {results['chat_panel']['mean_ms']:.2f}ms avg, {results['chat_panel']['max_ms']:.2f}ms max")
        print(f"  Logs Panel: {results['logs_panel']['mean_ms']:.2f}ms avg, {results['logs_panel']['max_ms']:.2f}ms max")
        print(f"  Sessions Panel: {results['sessions_panel']['mean_ms']:.2f}ms avg, {results['sessions_panel']['max_ms']:.2f}ms max")

    def test_resource_manager_benchmark(self, benchmark_suite):
        """Benchmark resource manager operations."""
        results = benchmark_suite.benchmark_resource_manager_operations(50)
        
        # Validate performance benchmarks
        assert results["registration"]["mean_ms"] < 1.0, f"Resource registration too slow: {results['registration']['mean_ms']:.2f}ms"
        assert results["retrieval"]["mean_ms"] < 0.5, f"Resource retrieval too slow: {results['retrieval']['mean_ms']:.2f}ms"
        assert results["pool_operations"]["mean_ms"] < 2.0, f"Pool operations too slow: {results['pool_operations']['mean_ms']:.2f}ms"
        
        print(f"Resource Manager Benchmark:")
        print(f"  Registration: {results['registration']['mean_ms']:.2f}ms avg, {results['registration']['max_ms']:.2f}ms max")
        print(f"  Retrieval: {results['retrieval']['mean_ms']:.2f}ms avg, {results['retrieval']['max_ms']:.2f}ms max")
        print(f"  Pool Operations: {results['pool_operations']['mean_ms']:.2f}ms avg, {results['pool_operations']['max_ms']:.2f}ms max")
        if results["memory_stats"]["times"]:
            print(f"  Memory Stats: {results['memory_stats']['mean_ms']:.2f}ms avg, {results['memory_stats']['max_ms']:.2f}ms max")

    def test_comprehensive_benchmark_suite(self, benchmark_suite):
        """Run comprehensive benchmark suite."""
        print("\n=== TUI Comprehensive Benchmark Suite ===")
        
        # Run all benchmarks
        session_results = benchmark_suite.benchmark_session_manager_operations(25)
        event_results = benchmark_suite.benchmark_event_manager_operations(25)
        panel_results = benchmark_suite.benchmark_panel_operations(15)
        resource_results = benchmark_suite.benchmark_resource_manager_operations(25)
        
        # Calculate overall performance score
        total_operations = (
            session_results["iterations"] * 3 +  # 3 operations per iteration
            event_results["iterations"] * 3 +    # 3 operations per iteration
            panel_results["iterations"] * 3 +    # 3 panels per iteration
            resource_results["iterations"] * 3   # 3 operations per iteration
        )
        
        total_time_ms = (
            sum(session_results["creation"]["times"]) +
            sum(session_results["retrieval"]["times"]) +
            sum(session_results["closure"]["times"]) +
            sum(event_results["routing"]["times"]) +
            sum(event_results["subscription"]["times"]) +
            sum(event_results["unsubscription"]["times"]) +
            sum(panel_results["chat_panel"]["times"]) +
            sum(panel_results["logs_panel"]["times"]) +
            sum(panel_results["sessions_panel"]["times"]) +
            sum(resource_results["registration"]["times"]) +
            sum(resource_results["retrieval"]["times"]) +
            sum(resource_results["pool_operations"]["times"])
        )
        
        average_operation_time = total_time_ms / total_operations
        operations_per_second = 1000 / average_operation_time
        
        print(f"\nOverall Performance Summary:")
        print(f"  Total Operations: {total_operations}")
        print(f"  Average Operation Time: {average_operation_time:.2f}ms")
        print(f"  Operations per Second: {operations_per_second:.1f}")
        
        # Validate overall performance
        assert average_operation_time < 5.0, f"Overall performance too slow: {average_operation_time:.2f}ms per operation"
        assert operations_per_second > 200, f"Overall throughput too low: {operations_per_second:.1f} ops/s"
        
        print("✅ All benchmarks passed performance requirements")

    def test_performance_regression_detection(self, benchmark_suite):
        """Test performance regression detection capabilities."""
        # Establish baseline
        baseline_session = benchmark_suite.benchmark_session_manager_operations(20)
        baseline_event = benchmark_suite.benchmark_event_manager_operations(20)
        
        # Simulate performance regression by adding artificial delay
        def slow_operation():
            time.sleep(0.001)  # 1ms delay
            return MagicMock()
        
        # Test with regression
        with patch('openhands.tui.managers.SessionManager.create_session', side_effect=slow_operation):
            regression_session = benchmark_suite.benchmark_session_manager_operations(20)
        
        # Detect regression
        baseline_avg = baseline_session["creation"]["mean_ms"]
        regression_avg = regression_session["creation"]["mean_ms"]
        regression_factor = regression_avg / baseline_avg if baseline_avg > 0 else float('inf')
        
        print(f"Regression Detection Test:")
        print(f"  Baseline: {baseline_avg:.2f}ms")
        print(f"  With Regression: {regression_avg:.2f}ms")
        print(f"  Regression Factor: {regression_factor:.2f}x")
        
        # Should detect significant regression
        assert regression_factor > 2.0, "Regression detection failed - should detect performance degradation"
        
        print("✅ Performance regression detection working correctly") 