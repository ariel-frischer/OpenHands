"""Session Manager.

Manages multiple concurrent OpenHands sessions for the TUI.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Union

from openhands.controller import AgentController
from openhands.controller.agent import Agent
from openhands.core.config import AppConfig
from openhands.core.logger import openhands_logger as logger
from openhands.core.schema import AgentState
from openhands.core.setup import (
    create_agent,
    create_controller,
    create_memory,
    create_runtime,
    generate_sid,
    initialize_repository_for_runtime,
)
from openhands.events import EventStream
from openhands.memory.memory import Memory
from openhands.microagent.microagent import BaseMicroagent
from openhands.runtime.base import Runtime
from openhands.storage.settings.file_settings_store import FileSettingsStore


@dataclass
class SessionContext:
    """Context for a single OpenHands session."""
    
    sid: str
    config: AppConfig
    runtime: Runtime
    controller: AgentController
    event_stream: EventStream
    memory: Memory
    agent_state: AgentState
    created_at: datetime
    last_activity: datetime
    task_description: str = ""
    agent: Optional[Agent] = None
    repo_directory: Optional[str] = None
    reload_microagents: bool = False
    # TUI-specific enhancements
    error_count: int = 0
    last_error: Optional[str] = None
    is_connected: bool = False
    startup_time: Optional[float] = None
    message_count: int = 0


class SessionManager:
    """Manages multiple concurrent OpenHands sessions."""
    
    def __init__(self, config: AppConfig, settings_store: Optional[FileSettingsStore]):
        """Initialize the session manager.
        
        Args:
            config: Application configuration
            settings_store: Settings store for session persistence
        """
        self.config = config
        self.settings_store = settings_store
        self.sessions: Dict[str, SessionContext] = {}
        self.active_session_id: Optional[str] = None
        self._cleanup_tasks: Dict[str, asyncio.Task] = {}
    
    async def create_session(self, task: str = "", name: str = "") -> str:
        """Create a new OpenHands session.
        
        Args:
            task: Initial task description for the session
            name: Optional name for the session (used in ID generation)
            
        Returns:
            Session ID of the created session
            
        Raises:
            Exception: If session creation fails
        """
        try:
            # Generate session ID
            sid = generate_sid(self.config, name if name else None)
            
            logger.info(f"Creating new session: {sid}")
            logger.debug(f"Session creation started for task: {task}")
            
            # Create agent (lightweight operation)
            logger.debug(f"Creating agent for session {sid}")
            agent = create_agent(self.config)
            
            # Create runtime but DON'T connect yet (defer heavy Docker operations)
            logger.debug(f"Creating runtime for session {sid}")
            runtime = create_runtime(
                self.config,
                sid=sid,
                headless_mode=True,
                agent=agent,
            )
            
            # Create controller without connecting runtime
            logger.debug(f"Creating controller for session {sid}")
            controller, initial_state = create_controller(agent, runtime, self.config)
            
            # Get event stream (lightweight)
            logger.debug(f"Getting event stream for session {sid}")
            event_stream = runtime.event_stream
            
            # Initialize repository if needed (lightweight - just path setup)
            repo_directory = None
            if self.config.sandbox.selected_repo:
                # Don't actually initialize the repo yet, just store the path
                repo_directory = self.config.sandbox.selected_repo.split('/')[-1]
            
            # Create memory without runtime connection (lightweight)
            # Note: Memory creation doesn't require runtime connection for basic setup
            memory = create_memory(
                runtime=runtime,
                event_stream=event_stream,
                sid=sid,
                selected_repository=self.config.sandbox.selected_repo,
                repo_directory=repo_directory,
                conversation_instructions=None,
            )
            
            # Create session context
            now = datetime.now()
            session_context = SessionContext(
                sid=sid,
                config=self.config,
                runtime=runtime,
                controller=controller,
                event_stream=event_stream,
                memory=memory,
                agent_state=AgentState.LOADING,
                created_at=now,
                last_activity=now,
                task_description=task,
                agent=agent,
                repo_directory=repo_directory,
                reload_microagents=False,
            )
            
            # Store session
            self.sessions[sid] = session_context
            
            # Set as active if it's the first session
            if self.active_session_id is None:
                self.active_session_id = sid
            
            logger.info(f"Session {sid} created successfully (deferred initialization)")
            
            # Automatically start the session if event manager is available
            if hasattr(self, 'event_manager') and self.event_manager:
                logger.info(f"Automatically starting session {sid} and setting up event subscription")
                try:
                    # Subscribe to events first
                    self.event_manager.subscribe_to_session(sid)
                    
                    # Start the session
                    await self.start_session(sid)
                    logger.info(f"Session {sid} automatically started and subscribed to events")
                except Exception as e:
                    logger.error(f"Failed to automatically start session {sid}: {e}")
                    # Don't fail session creation if auto-start fails
                    session_context.agent_state = AgentState.ERROR
            
            return sid
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}", exc_info=True)
            raise
    
    async def start_session(self, session_id: str) -> None:
        """Start a session by initializing the agent controller.
        
        Args:
            session_id: ID of the session to start
            
        Raises:
            ValueError: If session ID is not found
            Exception: If session startup fails
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        try:
            logger.info(f"Starting session: {session_id}")
            logger.debug(f"Session {session_id} current state: {session.agent_state}")
            
            # Update agent state to INIT
            logger.debug(f"Setting session {session_id} state to INIT")
            session.agent_state = AgentState.LOADING
            
            # Connect to runtime if not already connected
            if not hasattr(session.runtime, '_connected') or not session.runtime._connected:
                logger.info(f"Connecting to runtime for session {session_id}")
                await session.runtime.connect()
                # Mark session as connected
                self.set_session_connected(session_id, True)
            
            # Set agent state to AWAITING_USER_INPUT to indicate it's ready for interaction
            logger.debug(f"Setting controller state to AWAITING_USER_INPUT for session {session_id}")
            await session.controller.set_agent_state_to(AgentState.AWAITING_USER_INPUT)
            
            # Update our local agent state to match
            logger.debug(f"Updating local session state to AWAITING_USER_INPUT for session {session_id}")
            session.agent_state = AgentState.AWAITING_USER_INPUT
            
            # Subscribe to agent state changes to keep our local state in sync
            def state_change_callback(event):
                from openhands.events.observation import AgentStateChangedObservation
                if isinstance(event, AgentStateChangedObservation):
                    session.agent_state = event.agent_state
                    logger.debug(f"Session {session_id} agent state changed to {event.agent_state}")
            
            # Subscribe to state changes
            session.event_stream.subscribe(
                "MAIN",
                state_change_callback,
                f"session_manager_state_{session_id}"
            )
            
            # Start the agent loop in the background using run_agent_until_done
            # This will run until the agent reaches a terminal state
            from openhands.core.loop import run_agent_until_done
            
            # Create a background task to run the agent
            asyncio.create_task(
                run_agent_until_done(
                    session.controller,
                    session.runtime,
                    session.memory,
                    [AgentState.STOPPED, AgentState.ERROR]
                )
            )
            
            logger.info(f"Session {session_id} started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start session {session_id}: {e}", exc_info=True)
            # Update state to indicate error
            session.agent_state = AgentState.ERROR
            
            # Record the error in session tracking
            self.record_session_error(session_id, str(e))
            
            # Provide user-friendly error messages for common issues
            error_msg = str(e).lower()
            if "docker" in error_msg:
                user_friendly_msg = "Docker-related error. Please ensure Docker is running and accessible."
                logger.error(user_friendly_msg)
                self.record_session_error(session_id, user_friendly_msg)
            elif "network" in error_msg or "connection" in error_msg:
                user_friendly_msg = "Network connectivity issue. Please check your internet connection."
                logger.error(user_friendly_msg)
                self.record_session_error(session_id, user_friendly_msg)
            elif "timeout" in error_msg:
                user_friendly_msg = "Session startup timed out. This may be due to slow Docker container initialization."
                logger.error(user_friendly_msg)
                self.record_session_error(session_id, user_friendly_msg)
            elif "permission" in error_msg:
                user_friendly_msg = "Permission error. Please check file/directory permissions."
                logger.error(user_friendly_msg)
                self.record_session_error(session_id, user_friendly_msg)
            
            raise
    
    async def switch_session(self, session_id: str) -> None:
        """Switch to a different session.
        
        Args:
            session_id: ID of the session to switch to
            
        Raises:
            ValueError: If session ID is not found
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        # Update last activity for the session being switched to
        self.sessions[session_id].last_activity = datetime.now()
        self.active_session_id = session_id
        
        logger.info(f"Switched to session {session_id}")
    
    async def close_session(self, session_id: str) -> None:
        """Close and clean up a session.
        
        Args:
            session_id: ID of the session to close
            
        Raises:
            ValueError: If session ID is not found
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        try:
            logger.info(f"Closing session: {session_id}")
            
            # Save session state
            end_state = session.controller.get_state()
            end_state.save_to_session(
                session.event_stream.sid,
                session.event_stream.file_store,
                session.event_stream.user_id,
            )
            
            # Clean up resources
            if session.agent:
                session.agent.reset()
            session.runtime.close()
            await session.controller.close()
            
            # Cancel any cleanup tasks
            if session_id in self._cleanup_tasks:
                self._cleanup_tasks[session_id].cancel()
                del self._cleanup_tasks[session_id]
            
            # Remove from sessions
            del self.sessions[session_id]
            
            # Update active session if needed
            if self.active_session_id == session_id:
                if self.sessions:
                    # Switch to the most recently active session
                    self.active_session_id = max(
                        self.sessions.keys(),
                        key=lambda sid: self.sessions[sid].last_activity
                    )
                else:
                    self.active_session_id = None
            
            logger.info(f"Closed session {session_id}")
            
        except Exception as e:
            logger.error(f"Error closing session {session_id}: {e}")
            # Still remove from sessions even if cleanup failed
            if session_id in self.sessions:
                del self.sessions[session_id]
            if self.active_session_id == session_id:
                self.active_session_id = None
            raise
    
    def get_active_session(self) -> Optional[SessionContext]:
        """Get currently active session.
        
        Returns:
            Active session context or None if no active session
        """
        if self.active_session_id and self.active_session_id in self.sessions:
            return self.sessions[self.active_session_id]
        return None
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session by ID.
        
        Args:
            session_id: ID of the session to retrieve
            
        Returns:
            Session context or None if not found
        """
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[SessionContext]:
        """Get a list of all sessions.
        
        Returns:
            List of session contexts sorted by last activity (most recent first)
        """
        return sorted(
            self.sessions.values(),
            key=lambda s: s.last_activity,
            reverse=True
        )
    
    def update_session_activity(self, session_id: Optional[str] = None) -> None:
        """Update the last activity timestamp for a session.
        
        Args:
            session_id: ID of the session to update (defaults to active session)
        """
        target_id = session_id or self.active_session_id
        if target_id and target_id in self.sessions:
            self.sessions[target_id].last_activity = datetime.now()
    
    def update_session_task(self, task_description: str, session_id: Optional[str] = None) -> None:
        """Update the task description for a session.
        
        Args:
            task_description: New task description
            session_id: ID of the session to update (defaults to active session)
        """
        target_id = session_id or self.active_session_id
        if target_id and target_id in self.sessions:
            self.sessions[target_id].task_description = task_description
            self.update_session_activity(target_id)
    
    async def cleanup_all_sessions(self) -> None:
        """Clean up all sessions."""
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            try:
                await self.close_session(session_id)
            except Exception as e:
                logger.error(f"Error cleaning up session {session_id}: {e}")
        
        # Cancel all cleanup tasks
        for task in self._cleanup_tasks.values():
            task.cancel()
        self._cleanup_tasks.clear()
    
    def get_session_count(self) -> int:
        """Get the number of active sessions.
        
        Returns:
            Number of active sessions
        """
        return len(self.sessions)
    
    def has_sessions(self) -> bool:
        """Check if there are any active sessions.
        
        Returns:
            True if there are active sessions, False otherwise
        """
        return len(self.sessions) > 0
    
    def reload_session_microagents(self, session_id: Optional[str] = None) -> None:
        """Reload microagents for a session.
        
        Args:
            session_id: ID of the session to reload microagents for (defaults to active session)
        """
        target_id = session_id or self.active_session_id
        if target_id and target_id in self.sessions:
            session = self.sessions[target_id]
            try:
                # Get microagents from the selected repository
                microagents: List[BaseMicroagent] = (
                    session.runtime.get_microagents_from_selected_repo(None)
                )
                # Load microagents into memory
                session.memory.load_user_workspace_microagents(microagents)
                session.reload_microagents = False
                logger.info(f"Reloaded microagents for session {target_id}")
            except Exception as e:
                logger.error(f"Failed to reload microagents for session {target_id}: {e}")
    
    def mark_session_for_microagent_reload(self, session_id: Optional[str] = None) -> None:
        """Mark a session for microagent reload.
        
        Args:
            session_id: ID of the session to mark (defaults to active session)
        """
        target_id = session_id or self.active_session_id
        if target_id and target_id in self.sessions:
            self.sessions[target_id].reload_microagents = True

    # TUI-specific interface methods
    
    def get_session_status(self, session_id: str) -> Dict[str, Union[str, int, bool, float]]:
        """Get comprehensive status information for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dictionary containing session status information
        """
        session = self.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        uptime = (datetime.now() - session.created_at).total_seconds()
        
        return {
            "sid": session.sid,
            "agent_state": session.agent_state.value if session.agent_state else "unknown",
            "task_description": session.task_description,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "uptime_seconds": uptime,
            "error_count": session.error_count,
            "last_error": session.last_error,
            "is_connected": session.is_connected,
            "startup_time": session.startup_time,
            "message_count": session.message_count,
            "repo_directory": session.repo_directory,
            "reload_microagents": session.reload_microagents,
        }

    def get_all_session_statuses(self) -> List[Dict[str, Union[str, int, bool, float]]]:
        """Get status information for all sessions.
        
        Returns:
            List of session status dictionaries
        """
        return [self.get_session_status(sid) for sid in self.sessions.keys()]

    def record_session_error(self, session_id: str, error_message: str) -> None:
        """Record an error for a session.
        
        Args:
            session_id: ID of the session
            error_message: Error message to record
        """
        session = self.get_session(session_id)
        if session:
            session.error_count += 1
            session.last_error = error_message
            session.last_activity = datetime.now()
            logger.warning(f"Session {session_id} error #{session.error_count}: {error_message}")

    def increment_message_count(self, session_id: str) -> None:
        """Increment the message count for a session.
        
        Args:
            session_id: ID of the session
        """
        session = self.get_session(session_id)
        if session:
            session.message_count += 1
            self.update_session_activity(session_id)

    def set_session_connected(self, session_id: str, connected: bool) -> None:
        """Set the connection status for a session.
        
        Args:
            session_id: ID of the session
            connected: Whether the session is connected
        """
        session = self.get_session(session_id)
        if session:
            session.is_connected = connected
            if connected and session.startup_time is None:
                # Record startup time when first connected
                session.startup_time = (datetime.now() - session.created_at).total_seconds()
            self.update_session_activity(session_id)

    def get_session_health(self, session_id: str) -> Dict[str, Union[str, bool, int]]:
        """Get health information for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dictionary containing health information
        """
        session = self.get_session(session_id)
        if not session:
            return {"healthy": False, "reason": "Session not found"}
        
        # Check various health indicators
        health_checks = {
            "session_exists": True,
            "runtime_connected": session.is_connected,
            "agent_state_valid": session.agent_state in [
                AgentState.AWAITING_USER_INPUT, 
                AgentState.RUNNING, 
                AgentState.PAUSED
            ],
            "recent_activity": (datetime.now() - session.last_activity).total_seconds() < 3600,  # 1 hour
            "low_error_count": session.error_count < 10,
        }
        
        healthy = all(health_checks.values())
        
        return {
            "healthy": healthy,
            "checks": health_checks,
            "error_count": session.error_count,
            "last_error": session.last_error,
            "agent_state": session.agent_state.value if session.agent_state else "unknown",
        }

    def get_sessions_by_state(self, state: AgentState) -> List[SessionContext]:
        """Get all sessions in a specific state.
        
        Args:
            state: Agent state to filter by
            
        Returns:
            List of sessions in the specified state
        """
        return [session for session in self.sessions.values() if session.agent_state == state]

    def get_session_summary(self) -> Dict[str, Union[int, List[str]]]:
        """Get a summary of all sessions.
        
        Returns:
            Dictionary containing session summary information
        """
        total_sessions = len(self.sessions)
        active_sessions = len(self.get_sessions_by_state(AgentState.RUNNING))
        waiting_sessions = len(self.get_sessions_by_state(AgentState.AWAITING_USER_INPUT))
        error_sessions = len(self.get_sessions_by_state(AgentState.ERROR))
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "waiting_sessions": waiting_sessions,
            "error_sessions": error_sessions,
            "session_ids": list(self.sessions.keys()),
            "active_session_id": self.active_session_id,
        }