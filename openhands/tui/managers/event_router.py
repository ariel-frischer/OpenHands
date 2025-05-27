"""TUI Event Filtering and Routing System.

This module provides sophisticated event filtering and routing capabilities for the TUI,
building upon the existing TUIEventManager to provide advanced event handling features
including priority queuing, filtering, and debugging capabilities.
"""

import heapq
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from openhands.events import Event, EventSource
from openhands.events.action import (
    Action,
    ChangeAgentStateAction,
    CmdRunAction,
    MessageAction,
)
from openhands.events.observation import (
    AgentStateChangedObservation,
    CmdOutputObservation,
    ErrorObservation,
    FileEditObservation,
    FileReadObservation,
)

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels for routing."""

    CRITICAL = 1  # System errors, agent crashes
    HIGH = 2  # Agent state changes, user messages
    MEDIUM = 3  # Command execution, file operations
    LOW = 4  # Debug info, status updates


class EventCategory(Enum):
    """Event categories for filtering."""

    USER_INTERACTION = "user_interaction"
    AGENT_COMMUNICATION = "agent_communication"
    SYSTEM_OPERATION = "system_operation"
    FILE_OPERATION = "file_operation"
    ERROR_HANDLING = "error_handling"
    DEBUG_INFO = "debug_info"


@dataclass
class EventFilter:
    """Configuration for event filtering."""

    # Event type filtering
    allowed_types: Optional[Set[type]] = None
    blocked_types: Optional[Set[type]] = None

    # Source filtering
    allowed_sources: Optional[Set[EventSource]] = None
    blocked_sources: Optional[Set[EventSource]] = None

    # Category filtering
    allowed_categories: Optional[Set[EventCategory]] = None
    blocked_categories: Optional[Set[EventCategory]] = None

    # Priority filtering
    min_priority: Optional[EventPriority] = None
    max_priority: Optional[EventPriority] = None

    # Session filtering
    allowed_sessions: Optional[Set[str]] = None
    blocked_sessions: Optional[Set[str]] = None

    # Content filtering (lambda functions)
    content_filters: List[Callable[[Event], bool]] = field(default_factory=list)

    # Time-based filtering
    time_window_start: Optional[float] = None
    time_window_end: Optional[float] = None


@dataclass
class RoutedEvent:
    """Event with routing metadata."""

    event: Event
    session_id: str
    priority: EventPriority
    category: EventCategory
    timestamp: float = field(default_factory=time.time)
    route_id: str = ""

    def __lt__(self, other: "RoutedEvent") -> bool:
        """Compare events for priority queue ordering."""
        return self.priority.value < other.priority.value


class TUIEventRouter:
    """Advanced event filtering and routing system for TUI components.

    This class provides sophisticated event handling capabilities including:
    - Event filtering by type, source, category, priority, and custom criteria
    - Priority-based event queuing for optimal processing order
    - Event debugging and tracing for troubleshooting
    - Route management for different TUI components
    - Event statistics and monitoring
    """

    def __init__(self, debug_mode: bool = False):
        """Initialize the TUI Event Router.

        Args:
            debug_mode: Enable detailed event debugging and tracing
        """
        self.debug_mode = debug_mode

        # Event routing configuration
        self.routes: Dict[str, Dict[str, Any]] = {}
        self.filters: Dict[str, EventFilter] = {}
        self.handlers: Dict[str, Callable[[RoutedEvent], None]] = {}

        # Priority queue for event processing
        self.event_queue: List[RoutedEvent] = []
        self.queue_lock = False  # Simple lock for queue operations

        # Event type to category mapping
        self.type_category_map: Dict[type, EventCategory] = {
            MessageAction: EventCategory.USER_INTERACTION,
            ChangeAgentStateAction: EventCategory.AGENT_COMMUNICATION,
            CmdRunAction: EventCategory.SYSTEM_OPERATION,
            FileEditObservation: EventCategory.FILE_OPERATION,
            FileReadObservation: EventCategory.FILE_OPERATION,
            AgentStateChangedObservation: EventCategory.AGENT_COMMUNICATION,
            CmdOutputObservation: EventCategory.SYSTEM_OPERATION,
            ErrorObservation: EventCategory.ERROR_HANDLING,
        }

        # Event type to priority mapping
        self.type_priority_map: Dict[type, EventPriority] = {
            ErrorObservation: EventPriority.CRITICAL,
            AgentStateChangedObservation: EventPriority.HIGH,
            MessageAction: EventPriority.HIGH,
            ChangeAgentStateAction: EventPriority.HIGH,
            CmdRunAction: EventPriority.MEDIUM,
            FileEditObservation: EventPriority.MEDIUM,
            FileReadObservation: EventPriority.MEDIUM,
            CmdOutputObservation: EventPriority.LOW,
        }

        # Event statistics
        self.stats = {
            "events_processed": 0,
            "events_filtered": 0,
            "events_queued": 0,
            "events_routed": 0,
            "events_by_category": defaultdict(int),
            "events_by_priority": defaultdict(int),
            "events_by_session": defaultdict(int),
        }

        # Event history for debugging
        self.event_history: deque = deque(maxlen=1000)
        self.debug_traces: deque = deque(maxlen=500)

        logger.info("TUI Event Router initialized")

    def create_route(
        self,
        route_id: str,
        handler: Callable[[RoutedEvent], None],
        event_filter: Optional[EventFilter] = None,
        description: str = "",
    ) -> None:
        """Create a new event route.

        Args:
            route_id: Unique identifier for the route
            handler: Function to handle events for this route
            event_filter: Filter configuration for this route
            description: Human-readable description of the route
        """
        self.routes[route_id] = {
            "handler": handler,
            "filter": event_filter or EventFilter(),
            "description": description,
            "created_at": time.time(),
            "events_processed": 0,
        }

        self.handlers[route_id] = handler
        if event_filter:
            self.filters[route_id] = event_filter

        logger.info(f"Created event route: {route_id} - {description}")

    def remove_route(self, route_id: str) -> bool:
        """Remove an event route.

        Args:
            route_id: ID of the route to remove

        Returns:
            True if route was removed, False if not found
        """
        if route_id not in self.routes:
            return False

        del self.routes[route_id]
        self.handlers.pop(route_id, None)
        self.filters.pop(route_id, None)

        logger.info(f"Removed event route: {route_id}")
        return True

    def route_event(self, event: Event, session_id: str) -> List[str]:
        """Route an event through the filtering and routing system.

        Args:
            event: The event to route
            session_id: ID of the session that generated the event

        Returns:
            List of route IDs that processed the event
        """
        self.stats["events_processed"] += 1

        # Create routed event with metadata
        routed_event = self._create_routed_event(event, session_id)

        # Add to event history for debugging
        self.event_history.append(routed_event)

        # Find matching routes
        matching_routes = self._find_matching_routes(routed_event)

        if not matching_routes:
            self.stats["events_filtered"] += 1
            if self.debug_mode:
                self._add_debug_trace(
                    f"Event filtered: {type(event).__name__} from {session_id}"
                )
            return []

        # Process event through matching routes
        processed_routes = []
        for route_id in matching_routes:
            try:
                # Create a copy of the routed event for each route
                route_event = RoutedEvent(
                    event=routed_event.event,
                    session_id=routed_event.session_id,
                    priority=routed_event.priority,
                    category=routed_event.category,
                    timestamp=routed_event.timestamp,
                    route_id=route_id,
                )
                self._add_to_queue(route_event)
                processed_routes.append(route_id)

                # Update route statistics
                self.routes[route_id]["events_processed"] += 1

            except Exception as e:
                logger.error(f"Error routing event to {route_id}: {e}")
                if self.debug_mode:
                    self._add_debug_trace(f"Route error: {route_id} - {str(e)}")

        # Update statistics
        self.stats["events_routed"] += len(processed_routes)
        self.stats["events_by_category"][routed_event.category.value] += 1
        self.stats["events_by_priority"][routed_event.priority.name] += 1
        self.stats["events_by_session"][session_id] += 1

        if self.debug_mode:
            self._add_debug_trace(
                f"Routed {type(event).__name__} from {session_id} to {len(processed_routes)} routes"
            )

        return processed_routes

    def process_queue(self, max_events: int = 10) -> int:
        """Process events from the priority queue.

        Args:
            max_events: Maximum number of events to process in this call

        Returns:
            Number of events processed
        """
        if self.queue_lock:
            return 0

        self.queue_lock = True
        processed_count = 0

        try:
            while self.event_queue and processed_count < max_events:
                # Get highest priority event
                routed_event = heapq.heappop(self.event_queue)

                # Get handler for this route
                handler = self.handlers.get(routed_event.route_id)
                if not handler:
                    logger.warning(
                        f"No handler found for route: {routed_event.route_id}"
                    )
                    continue

                try:
                    # Execute handler
                    handler(routed_event)
                    processed_count += 1

                    if self.debug_mode:
                        self._add_debug_trace(
                            f"Processed {type(routed_event.event).__name__} via {routed_event.route_id}"
                        )

                except Exception as e:
                    logger.error(f"Error in event handler {routed_event.route_id}: {e}")
                    if self.debug_mode:
                        self._add_debug_trace(
                            f"Handler error: {routed_event.route_id} - {str(e)}"
                        )

        finally:
            self.queue_lock = False

        return processed_count

    def create_filter(
        self,
        filter_id: str,
        allowed_types: Optional[List[type]] = None,
        blocked_types: Optional[List[type]] = None,
        allowed_categories: Optional[List[EventCategory]] = None,
        blocked_categories: Optional[List[EventCategory]] = None,
        min_priority: Optional[EventPriority] = None,
        content_filter: Optional[Callable[[Event], bool]] = None,
    ) -> EventFilter:
        """Create a new event filter with common configurations.

        Args:
            filter_id: Unique identifier for the filter
            allowed_types: Event types to allow (None = allow all)
            blocked_types: Event types to block
            allowed_categories: Event categories to allow
            blocked_categories: Event categories to block
            min_priority: Minimum priority level to allow
            content_filter: Custom content filtering function

        Returns:
            Configured EventFilter instance
        """
        event_filter = EventFilter(
            allowed_types=set(allowed_types) if allowed_types else None,
            blocked_types=set(blocked_types) if blocked_types else None,
            allowed_categories=set(allowed_categories) if allowed_categories else None,
            blocked_categories=set(blocked_categories) if blocked_categories else None,
            min_priority=min_priority,
            content_filters=[content_filter] if content_filter else [],
        )

        self.filters[filter_id] = event_filter
        logger.info(f"Created event filter: {filter_id}")
        return event_filter

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current status of the event queue.

        Returns:
            Dictionary with queue status information
        """
        priority_counts = defaultdict(int)
        category_counts = defaultdict(int)

        for routed_event in self.event_queue:
            priority_counts[routed_event.priority.name] += 1
            category_counts[routed_event.category.value] += 1

        return {
            "queue_size": len(self.event_queue),
            "queue_locked": self.queue_lock,
            "events_by_priority": dict(priority_counts),
            "events_by_category": dict(category_counts),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive event routing statistics.

        Returns:
            Dictionary with routing statistics
        """
        return {
            "routes": {
                route_id: {
                    "description": route_data["description"],
                    "events_processed": route_data["events_processed"],
                    "created_at": route_data["created_at"],
                }
                for route_id, route_data in self.routes.items()
            },
            "filters": len(self.filters),
            "queue_status": self.get_queue_status(),
            "statistics": dict(self.stats),
            "debug_mode": self.debug_mode,
        }

    def get_debug_traces(self, limit: int = 50) -> List[str]:
        """Get recent debug traces.

        Args:
            limit: Maximum number of traces to return

        Returns:
            List of debug trace messages
        """
        return list(self.debug_traces)[-limit:]

    def clear_statistics(self) -> None:
        """Clear all statistics and debug traces."""
        self.stats = {
            "events_processed": 0,
            "events_filtered": 0,
            "events_queued": 0,
            "events_routed": 0,
            "events_by_category": defaultdict(int),
            "events_by_priority": defaultdict(int),
            "events_by_session": defaultdict(int),
        }
        self.event_history.clear()
        self.debug_traces.clear()

        logger.info("Cleared event router statistics and debug traces")

    def _create_routed_event(self, event: Event, session_id: str) -> RoutedEvent:
        """Create a RoutedEvent with appropriate metadata.

        Args:
            event: The original event
            session_id: ID of the session that generated the event

        Returns:
            RoutedEvent with metadata
        """
        event_type = type(event)

        # Determine category
        category = self.type_category_map.get(event_type, EventCategory.DEBUG_INFO)

        # Determine priority
        priority = self.type_priority_map.get(event_type, EventPriority.LOW)

        # Special priority handling for error events
        if isinstance(event, ErrorObservation):
            priority = EventPriority.CRITICAL
        elif hasattr(event, "source") and event.source == EventSource.USER:
            priority = EventPriority.HIGH

        return RoutedEvent(
            event=event, session_id=session_id, priority=priority, category=category
        )

    def _find_matching_routes(self, routed_event: RoutedEvent) -> List[str]:
        """Find routes that match the given event.

        Args:
            routed_event: The event to match against routes

        Returns:
            List of matching route IDs
        """
        matching_routes = []

        for route_id, route_data in self.routes.items():
            event_filter = route_data["filter"]

            if self._event_matches_filter(routed_event, event_filter):
                matching_routes.append(route_id)

        return matching_routes

    def _event_matches_filter(
        self, routed_event: RoutedEvent, event_filter: EventFilter
    ) -> bool:
        """Check if an event matches the given filter.

        Args:
            routed_event: The event to check
            event_filter: The filter to apply

        Returns:
            True if event matches filter, False otherwise
        """
        event = routed_event.event
        event_type = type(event)

        # Type filtering
        if event_filter.allowed_types and event_type not in event_filter.allowed_types:
            return False
        if event_filter.blocked_types and event_type in event_filter.blocked_types:
            return False

        # Source filtering
        if hasattr(event, "source"):
            if (
                event_filter.allowed_sources
                and event.source not in event_filter.allowed_sources
            ):
                return False
            if (
                event_filter.blocked_sources
                and event.source in event_filter.blocked_sources
            ):
                return False

        # Category filtering
        if (
            event_filter.allowed_categories
            and routed_event.category not in event_filter.allowed_categories
        ):
            return False
        if (
            event_filter.blocked_categories
            and routed_event.category in event_filter.blocked_categories
        ):
            return False

        # Priority filtering
        if (
            event_filter.min_priority
            and routed_event.priority.value > event_filter.min_priority.value
        ):
            return False
        if (
            event_filter.max_priority
            and routed_event.priority.value < event_filter.max_priority.value
        ):
            return False

        # Session filtering
        if (
            event_filter.allowed_sessions
            and routed_event.session_id not in event_filter.allowed_sessions
        ):
            return False
        if (
            event_filter.blocked_sessions
            and routed_event.session_id in event_filter.blocked_sessions
        ):
            return False

        # Time window filtering
        if (
            event_filter.time_window_start
            and routed_event.timestamp < event_filter.time_window_start
        ):
            return False
        if (
            event_filter.time_window_end
            and routed_event.timestamp > event_filter.time_window_end
        ):
            return False

        # Content filtering
        for content_filter in event_filter.content_filters:
            try:
                if not content_filter(event):
                    return False
            except Exception as e:
                logger.warning(f"Error in content filter: {e}")
                return False

        return True

    def _add_to_queue(self, routed_event: RoutedEvent) -> None:
        """Add an event to the priority queue.

        Args:
            routed_event: The event to add to the queue
        """
        heapq.heappush(self.event_queue, routed_event)
        self.stats["events_queued"] += 1

    def _add_debug_trace(self, message: str) -> None:
        """Add a debug trace message.

        Args:
            message: Debug message to add
        """
        if self.debug_mode:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            trace_message = f"[{timestamp}] {message}"
            self.debug_traces.append(trace_message)
