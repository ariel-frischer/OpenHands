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
            
            # Create agent
            agent = create_agent(self.config)
            
            # Create runtime
            runtime = create_runtime(
                self.config,
                sid=sid,
                headless_mode=True,
                agent=agent,
            )
            
            # Connect runtime
            await runtime.connect()
            
            # Create controller
            controller, initial_state = create_controller(agent, runtime, self.config)
            
            # Get event stream
            event_stream = runtime.event_stream
            
            # Initialize repository if needed
            repo_directory = None
            if self.config.sandbox.selected_repo:
                repo_directory = initialize_repository_for_runtime(
                    runtime,
                    selected_repository=self.config.sandbox.selected_repo,
                )
            
            # Create memory (this will load microagents from the selected repository)
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
            
            logger.info(f"Session {sid} created successfully")
            return sid
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
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