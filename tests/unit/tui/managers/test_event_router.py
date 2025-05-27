"""Tests for TUI Event Router.

This module contains comprehensive tests for the TUIEventRouter class,
including event filtering, routing, priority queuing, and debugging functionality.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from openhands.events import EventSource
from openhands.events.action import MessageAction, CmdRunAction, ChangeAgentStateAction
from openhands.events.observation import (
    ErrorObservation,
    AgentStateChangedObservation,
    CmdOutputObservation,
    FileEditObservation,
)
from openhands.core.schema import AgentState

from openhands.tui.managers.event_router import (
    TUIEventRouter,
    EventFilter,
    EventPriority,
    EventCategory,
    RoutedEvent,
)


class TestTUIEventRouter:
    """Test cases for TUIEventRouter functionality."""

    @pytest.fixture
    def event_router(self):
        """Create a TUIEventRouter instance for testing."""
        return TUIEventRouter(debug_mode=True)

    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing."""
        return {
            "message": MessageAction(content="Test message"),
            "error": ErrorObservation(content="Test error"),
            "cmd_run": CmdRunAction(command="ls -la"),
            "cmd_output": CmdOutputObservation(content="file1.txt\nfile2.txt", command="ls -la"),
            "agent_state": AgentStateChangedObservation(content="", agent_state=AgentState.RUNNING),
            "file_edit": FileEditObservation(content="", path="/test/file.py"),
        }

    def test_initialization(self, event_router):
        """Test TUIEventRouter initialization."""
        assert event_router.debug_mode is True
        assert len(event_router.routes) == 0
        assert len(event_router.filters) == 0
        assert len(event_router.handlers) == 0
        assert len(event_router.event_queue) == 0
        assert event_router.queue_lock is False

    def test_create_route(self, event_router):
        """Test creating event routes."""
        handler = MagicMock()
        event_filter = EventFilter(min_priority=EventPriority.HIGH)
        
        event_router.create_route(
            "test_route",
            handler,
            event_filter,
            "Test route description"
        )
        
        assert "test_route" in event_router.routes
        assert event_router.routes["test_route"]["handler"] == handler
        assert event_router.routes["test_route"]["filter"] == event_filter
        assert event_router.routes["test_route"]["description"] == "Test route description"
        assert "test_route" in event_router.handlers
        assert "test_route" in event_router.filters

    def test_remove_route(self, event_router):
        """Test removing event routes."""
        handler = MagicMock()
        event_router.create_route("test_route", handler)
        
        # Test successful removal
        assert event_router.remove_route("test_route") is True
        assert "test_route" not in event_router.routes
        assert "test_route" not in event_router.handlers
        
        # Test removing non-existent route
        assert event_router.remove_route("nonexistent") is False

    def test_event_categorization(self, event_router, sample_events):
        """Test event categorization and priority assignment."""
        test_cases = [
            (sample_events["message"], EventCategory.USER_INTERACTION, EventPriority.HIGH),
            (sample_events["error"], EventCategory.ERROR_HANDLING, EventPriority.CRITICAL),
            (sample_events["cmd_run"], EventCategory.SYSTEM_OPERATION, EventPriority.MEDIUM),
            (sample_events["agent_state"], EventCategory.AGENT_COMMUNICATION, EventPriority.HIGH),
            (sample_events["file_edit"], EventCategory.FILE_OPERATION, EventPriority.MEDIUM),
        ]
        
        for event, expected_category, expected_priority in test_cases:
            routed_event = event_router._create_routed_event(event, "test_session")
            assert routed_event.category == expected_category
            assert routed_event.priority == expected_priority
            assert routed_event.session_id == "test_session"

    def test_route_event_no_routes(self, event_router, sample_events):
        """Test routing event when no routes are configured."""
        result = event_router.route_event(sample_events["message"], "test_session")
        
        assert result == []
        assert event_router.stats["events_processed"] == 1
        assert event_router.stats["events_filtered"] == 1
        assert len(event_router.event_history) == 1

    def test_route_event_with_matching_route(self, event_router, sample_events):
        """Test routing event with matching route."""
        handler = MagicMock()
        event_router.create_route("test_route", handler)
        
        result = event_router.route_event(sample_events["message"], "test_session")
        
        assert result == ["test_route"]
        assert event_router.stats["events_processed"] == 1
        assert event_router.stats["events_routed"] == 1
        assert len(event_router.event_queue) == 1

    def test_event_filtering_by_type(self, event_router, sample_events):
        """Test event filtering by event type."""
        handler = MagicMock()
        
        # Create filter that only allows MessageAction
        event_filter = EventFilter(allowed_types={MessageAction})
        event_router.create_route("message_route", handler, event_filter)
        
        # Test allowed event
        result = event_router.route_event(sample_events["message"], "test_session")
        assert result == ["message_route"]
        
        # Test blocked event
        result = event_router.route_event(sample_events["error"], "test_session")
        assert result == []

    def test_event_filtering_by_priority(self, event_router, sample_events):
        """Test event filtering by priority level."""
        handler = MagicMock()
        
        # Create filter that only allows HIGH priority and above
        event_filter = EventFilter(min_priority=EventPriority.HIGH)
        event_router.create_route("high_priority_route", handler, event_filter)
        
        # Test high priority event (should pass)
        result = event_router.route_event(sample_events["message"], "test_session")
        assert result == ["high_priority_route"]
        
        # Test low priority event (should be filtered)
        result = event_router.route_event(sample_events["cmd_output"], "test_session")
        assert result == []

    def test_event_filtering_by_category(self, event_router, sample_events):
        """Test event filtering by category."""
        handler = MagicMock()
        
        # Create filter that only allows ERROR_HANDLING category
        event_filter = EventFilter(allowed_categories={EventCategory.ERROR_HANDLING})
        event_router.create_route("error_route", handler, event_filter)
        
        # Test error event (should pass)
        result = event_router.route_event(sample_events["error"], "test_session")
        assert result == ["error_route"]
        
        # Test non-error event (should be filtered)
        result = event_router.route_event(sample_events["message"], "test_session")
        assert result == []

    def test_event_filtering_by_session(self, event_router, sample_events):
        """Test event filtering by session ID."""
        handler = MagicMock()
        
        # Create filter that only allows specific session
        event_filter = EventFilter(allowed_sessions={"allowed_session"})
        event_router.create_route("session_route", handler, event_filter)
        
        # Test allowed session
        result = event_router.route_event(sample_events["message"], "allowed_session")
        assert result == ["session_route"]
        
        # Test blocked session
        result = event_router.route_event(sample_events["message"], "blocked_session")
        assert result == []

    def test_content_filtering(self, event_router, sample_events):
        """Test custom content filtering."""
        handler = MagicMock()
        
        # Create filter with custom content filter
        def content_filter(event):
            return hasattr(event, 'content') and 'Test' in event.content
        
        event_filter = EventFilter(content_filters=[content_filter])
        event_router.create_route("content_route", handler, event_filter)
        
        # Test event with matching content
        result = event_router.route_event(sample_events["message"], "test_session")
        assert result == ["content_route"]
        
        # Test event without matching content
        different_message = MessageAction(content="Different message")
        result = event_router.route_event(different_message, "test_session")
        assert result == []

    def test_time_window_filtering(self, event_router, sample_events):
        """Test time window filtering."""
        handler = MagicMock()
        
        current_time = time.time()
        # Create filter with time window (last 10 seconds)
        event_filter = EventFilter(
            time_window_start=current_time - 10,
            time_window_end=current_time + 10
        )
        event_router.create_route("time_route", handler, event_filter)
        
        # Test event within time window
        result = event_router.route_event(sample_events["message"], "test_session")
        assert result == ["time_route"]

    def test_process_queue(self, event_router, sample_events):
        """Test processing events from the priority queue."""
        handler = MagicMock()
        event_router.create_route("test_route", handler)
        
        # Add events to queue
        event_router.route_event(sample_events["message"], "test_session")
        event_router.route_event(sample_events["error"], "test_session")
        
        # Process queue
        processed_count = event_router.process_queue(max_events=5)
        
        assert processed_count == 2
        assert handler.call_count == 2
        assert len(event_router.event_queue) == 0

    def test_priority_queue_ordering(self, event_router, sample_events):
        """Test that events are processed in priority order."""
        handler_calls = []
        
        def tracking_handler(routed_event):
            handler_calls.append(type(routed_event.event).__name__)
        
        event_router.create_route("test_route", tracking_handler)
        
        # Add events in non-priority order
        event_router.route_event(sample_events["cmd_output"], "test_session")  # LOW
        event_router.route_event(sample_events["error"], "test_session")       # CRITICAL
        event_router.route_event(sample_events["message"], "test_session")     # HIGH
        
        # Process queue
        event_router.process_queue()
        
        # Verify processing order (CRITICAL, HIGH, LOW)
        assert handler_calls == ["ErrorObservation", "MessageAction", "CmdOutputObservation"]

    def test_queue_lock_mechanism(self, event_router, sample_events):
        """Test queue lock prevents concurrent processing."""
        handler = MagicMock()
        event_router.create_route("test_route", handler)
        event_router.route_event(sample_events["message"], "test_session")
        
        # Simulate queue being locked
        event_router.queue_lock = True
        
        processed_count = event_router.process_queue()
        
        assert processed_count == 0
        assert handler.call_count == 0

    def test_create_filter_helper(self, event_router):
        """Test the create_filter helper method."""
        event_filter = event_router.create_filter(
            "test_filter",
            allowed_types=[MessageAction, ErrorObservation],
            blocked_categories=[EventCategory.DEBUG_INFO],
            min_priority=EventPriority.MEDIUM
        )
        
        assert "test_filter" in event_router.filters
        assert event_filter.allowed_types == {MessageAction, ErrorObservation}
        assert event_filter.blocked_categories == {EventCategory.DEBUG_INFO}
        assert event_filter.min_priority == EventPriority.MEDIUM

    def test_get_queue_status(self, event_router, sample_events):
        """Test getting queue status information."""
        handler = MagicMock()
        event_router.create_route("test_route", handler)
        
        # Add events to queue
        event_router.route_event(sample_events["error"], "test_session")
        event_router.route_event(sample_events["message"], "test_session")
        
        status = event_router.get_queue_status()
        
        assert status["queue_size"] == 2
        assert status["queue_locked"] is False
        assert "CRITICAL" in status["events_by_priority"]
        assert "HIGH" in status["events_by_priority"]

    def test_get_statistics(self, event_router, sample_events):
        """Test getting comprehensive statistics."""
        handler = MagicMock()
        event_router.create_route("test_route", handler, description="Test route")
        
        # Process some events
        event_router.route_event(sample_events["message"], "test_session")
        event_router.route_event(sample_events["error"], "test_session")
        event_router.process_queue()
        
        stats = event_router.get_statistics()
        
        assert "routes" in stats
        assert "test_route" in stats["routes"]
        assert stats["routes"]["test_route"]["description"] == "Test route"
        assert stats["routes"]["test_route"]["events_processed"] == 2
        assert stats["statistics"]["events_processed"] == 2
        assert stats["debug_mode"] is True

    def test_debug_traces(self, event_router, sample_events):
        """Test debug trace functionality."""
        handler = MagicMock()
        event_router.create_route("test_route", handler)
        
        # Process an event to generate debug traces
        event_router.route_event(sample_events["message"], "test_session")
        event_router.process_queue()
        
        traces = event_router.get_debug_traces()
        
        assert len(traces) > 0
        assert any("Routed MessageAction" in trace for trace in traces)
        assert any("Processed MessageAction" in trace for trace in traces)

    def test_clear_statistics(self, event_router, sample_events):
        """Test clearing statistics and debug traces."""
        handler = MagicMock()
        event_router.create_route("test_route", handler)
        
        # Generate some statistics
        event_router.route_event(sample_events["message"], "test_session")
        event_router.process_queue()
        
        # Verify statistics exist
        assert event_router.stats["events_processed"] > 0
        assert len(event_router.event_history) > 0
        assert len(event_router.debug_traces) > 0
        
        # Clear statistics
        event_router.clear_statistics()
        
        # Verify statistics are cleared
        assert event_router.stats["events_processed"] == 0
        assert len(event_router.event_history) == 0
        assert len(event_router.debug_traces) == 0

    def test_error_handling_in_content_filter(self, event_router, sample_events):
        """Test error handling in custom content filters."""
        handler = MagicMock()
        
        # Create filter with faulty content filter
        def faulty_filter(event):
            raise ValueError("Filter error")
        
        event_filter = EventFilter(content_filters=[faulty_filter])
        event_router.create_route("faulty_route", handler, event_filter)
        
        # Event should be filtered due to filter error
        result = event_router.route_event(sample_events["message"], "test_session")
        assert result == []

    def test_error_handling_in_route_processing(self, event_router, sample_events):
        """Test error handling during route processing."""
        def faulty_handler(routed_event):
            raise RuntimeError("Handler error")
        
        event_router.create_route("faulty_route", faulty_handler)
        
        # Route event and process queue
        event_router.route_event(sample_events["message"], "test_session")
        
        # Should not raise exception, but log error
        processed_count = event_router.process_queue()
        assert processed_count == 0  # Handler failed, so no successful processing

    def test_multiple_routes_same_event(self, event_router, sample_events):
        """Test routing same event to multiple routes."""
        handler1 = MagicMock()
        handler2 = MagicMock()
        
        event_router.create_route("route1", handler1)
        event_router.create_route("route2", handler2)
        
        result = event_router.route_event(sample_events["message"], "test_session")
        
        assert len(result) == 2
        assert "route1" in result
        assert "route2" in result
        
        # Process queue - each route gets its own copy of the event
        processed_count = event_router.process_queue()
        
        # Both handlers should be called (2 events processed, one per route)
        assert processed_count == 2
        assert handler1.call_count == 1
        assert handler2.call_count == 1

    def test_routed_event_comparison(self):
        """Test RoutedEvent comparison for priority queue."""
        message_event = MessageAction(content="Test")
        error_event = ErrorObservation(content="Error")
        
        routed_message = RoutedEvent(
            event=message_event,
            session_id="test",
            priority=EventPriority.HIGH,
            category=EventCategory.USER_INTERACTION
        )
        
        routed_error = RoutedEvent(
            event=error_event,
            session_id="test",
            priority=EventPriority.CRITICAL,
            category=EventCategory.ERROR_HANDLING
        )
        
        # Critical priority should be less than high priority (for min-heap)
        assert routed_error < routed_message

    def test_event_source_priority_override(self, event_router):
        """Test that user events get high priority regardless of type."""
        # Create a low-priority event type but with USER source
        cmd_output = CmdOutputObservation(content="output", command="test")
        cmd_output._source = EventSource.USER  # Set the private attribute directly
        
        routed_event = event_router._create_routed_event(cmd_output, "test_session")
        
        # Should get HIGH priority due to USER source
        assert routed_event.priority == EventPriority.HIGH

    def test_blocked_types_filtering(self, event_router, sample_events):
        """Test filtering with blocked event types."""
        handler = MagicMock()
        
        # Create filter that blocks ErrorObservation
        event_filter = EventFilter(blocked_types={ErrorObservation})
        event_router.create_route("no_errors_route", handler, event_filter)
        
        # Test allowed event
        result = event_router.route_event(sample_events["message"], "test_session")
        assert result == ["no_errors_route"]
        
        # Test blocked event
        result = event_router.route_event(sample_events["error"], "test_session")
        assert result == []

    def test_blocked_sessions_filtering(self, event_router, sample_events):
        """Test filtering with blocked sessions."""
        handler = MagicMock()
        
        # Create filter that blocks specific session
        event_filter = EventFilter(blocked_sessions={"blocked_session"})
        event_router.create_route("session_filter_route", handler, event_filter)
        
        # Test allowed session
        result = event_router.route_event(sample_events["message"], "allowed_session")
        assert result == ["session_filter_route"]
        
        # Test blocked session
        result = event_router.route_event(sample_events["message"], "blocked_session")
        assert result == [] 