"""Session Manager.

Manages multiple concurrent OpenHands sessions for the TUI.
"""

import asyncio
import socket
import time
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
from openhands.mcp import add_mcp_tools_to_agent
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
    # Network/offline mode tracking
    is_offline_mode: bool = False
    connection_attempts: int = 0
    microagents_loaded: bool = False


class NetworkConnectivityChecker:
    """Utility class to check network connectivity and service availability."""

    @staticmethod
    def check_internet_connectivity(
        host: str = "8.8.8.8", port: int = 53, timeout: float = 3
    ) -> bool:
        """Check if internet connectivity is available.

        Args:
            host: Host to test connectivity to (default: Google DNS)
            port: Port to test (default: DNS port 53)
            timeout: Timeout in seconds

        Returns:
            True if connectivity is available, False otherwise
        """
        try:
            socket.setdefaulttimeout(timeout)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect((host, port))
                return True
            finally:
                sock.close()
        except (socket.error, socket.timeout, OSError):
            return False

    @staticmethod
    def check_http_connectivity(timeout: float = 5) -> bool:
        """Check if HTTP requests work properly (detects DNS/hostname resolution issues).

        Args:
            timeout: Timeout in seconds

        Returns:
            True if HTTP requests work, False if DNS/hostname issues detected
        """
        try:
            import httpx

            # Test a simple HTTP request to a reliable service
            with httpx.Client(timeout=timeout) as client:
                response = client.get("http://httpbin.org/status/200")
                return response.status_code == 200
        except Exception as e:
            error_msg = str(e).lower()
            # Specifically detect the "[Errno -8]" and related DNS issues
            if (
                "[errno -8]" in error_msg
                or "servname not supported" in error_msg
                or "ai_socktype" in error_msg
                or "name resolution" in error_msg
                or "dns" in error_msg
            ):
                logger.warning(f"DNS/hostname resolution issue detected: {e}")
                return False
            # Other network errors
            logger.debug(f"HTTP connectivity check failed: {e}")
            return False

    @staticmethod
    def check_docker_availability() -> bool:
        """Check if Docker is available and running.

        Returns:
            True if Docker is available, False otherwise
        """
        try:
            import subprocess

            result = subprocess.run(
                ["docker", "version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    @staticmethod
    def check_local_runtime_dependencies() -> bool:
        """Check if LocalRuntime dependencies are available.

        Returns:
            True if LocalRuntime can be used, False otherwise
        """
        try:
            # Check if poetry is available
            import subprocess

            result = subprocess.run(
                ["poetry", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    @classmethod
    def get_connectivity_status(cls) -> Dict[str, bool]:
        """Get comprehensive connectivity status.

        Returns:
            Dictionary with connectivity status for different services
        """
        return {
            "internet": cls.check_internet_connectivity(),
            "http": cls.check_http_connectivity(),
            "docker": cls.check_docker_availability(),
            "local_runtime": cls.check_local_runtime_dependencies(),
        }


class SessionManager:
    """Manages multiple concurrent OpenHands sessions."""

    def __init__(
        self,
        config: AppConfig,
        settings_store: Optional[FileSettingsStore],
        offline_mode: bool = False,
    ):
        """Initialize the session manager.

        Args:
            config: Application configuration
            settings_store: Settings store for session persistence
            offline_mode: Whether to enable offline mode (use LocalRuntime)
        """
        self.config = config
        self.settings_store = settings_store
        self.sessions: Dict[str, SessionContext] = {}
        self.active_session_id: Optional[str] = None
        self._cleanup_tasks: Dict[str, asyncio.Task] = {}
        self._session_creation_lock = asyncio.Lock()  # Prevent concurrent session creation

        # Network connectivity tracking
        self._connectivity_status = NetworkConnectivityChecker.get_connectivity_status()
        self._offline_mode_enabled = offline_mode
        self._last_connectivity_check = 0.0
        self._connectivity_check_interval = 30.0  # Check every 30 seconds

    def _should_use_offline_mode(self) -> bool:
        """Determine if offline mode should be used based on connectivity and config.

        Returns:
            True if offline mode should be used, False otherwise
        """
        # Force offline mode if explicitly enabled
        if self._offline_mode_enabled:
            return True

        # Check connectivity status (with caching to avoid frequent checks)
        current_time = time.time()
        if (
            current_time - self._last_connectivity_check
            > self._connectivity_check_interval
        ):
            self._connectivity_status = (
                NetworkConnectivityChecker.get_connectivity_status()
            )
            self._last_connectivity_check = current_time

        # Use offline mode if HTTP requests fail (DNS/hostname resolution issues)
        if (
            not self._connectivity_status.get("http", True)
            and self._connectivity_status["local_runtime"]
        ):
            logger.info(
                "HTTP connectivity issues detected (likely DNS/hostname resolution), using offline mode with LocalRuntime"
            )
            return True

        # Use offline mode if Docker isn't available but LocalRuntime is
        if (
            not self._connectivity_status["docker"]
            and self._connectivity_status["local_runtime"]
        ):
            logger.info("Docker not available, using offline mode with LocalRuntime")
            return True

        # Use offline mode if internet connectivity is poor
        if not self._connectivity_status["internet"]:
            logger.info("Limited internet connectivity, using offline mode if possible")
            return self._connectivity_status["local_runtime"]

        return False

    def _get_runtime_for_session(self, sid: str, agent: Agent) -> Runtime:
        """Get the appropriate runtime for a session based on connectivity.

        Args:
            sid: Session ID
            agent: Agent instance

        Returns:
            Runtime instance
        """
        use_offline = self._should_use_offline_mode()

        if use_offline:
            logger.info(f"Creating LocalRuntime for session {sid} (offline mode)")
            # Temporarily override the runtime config to use local runtime
            original_runtime = self.config.runtime
            try:
                self.config.runtime = "local"
                runtime = create_runtime(
                    self.config,
                    sid=sid,
                    headless_mode=True,
                    agent=agent,
                )
                return runtime
            finally:
                # Restore original runtime config
                self.config.runtime = original_runtime
        else:
            logger.info(f"Creating {self.config.runtime} runtime for session {sid}")
            return create_runtime(
                self.config,
                sid=sid,
                headless_mode=True,
                agent=agent,
            )

    async def create_session(self, task: str = "", name: str = "") -> str:
        """Create a new OpenHands session using CLI-proven pattern.

        Args:
            task: Initial task description for the session
            name: Optional name for the session (used in ID generation)

        Returns:
            Session ID of the created session

        Raises:
            Exception: If session creation fails
        """
        # Prevent concurrent session creation attempts
        async with self._session_creation_lock:
            start_time = time.time()

            try:
                # 1. Generate session ID (same as CLI)
                sid = generate_sid(self.config, name if name else None)
                logger.info(f"Creating new session: {sid}")

                # 2. Create agent (same as CLI)
                logger.debug(f"Creating agent for session {sid}")
                agent = create_agent(self.config)

                # 3. Create runtime (same as CLI)
                logger.debug(f"Creating runtime for session {sid}")
                runtime = self._get_runtime_for_session(sid, agent)

                # Track if we're in offline mode
                is_offline_mode = (
                    isinstance(runtime.__class__.__name__, str)
                    and "Local" in runtime.__class__.__name__
                )

                # 4. Create controller (same as CLI)
                logger.debug(f"Creating controller for session {sid}")
                controller, initial_state = create_controller(agent, runtime, self.config)

                # 5. Get event stream (same as CLI)
                logger.debug(f"Getting event stream for session {sid}")
                event_stream = runtime.event_stream

                # 6. Get event stream (will subscribe after session is stored)

                # 7. Connect runtime with timeout (MISSING IN CURRENT TUI - CRITICAL FIX)
                logger.info(f"Connecting runtime for session {sid}")
                try:
                    # Add timeout to prevent hanging
                    await asyncio.wait_for(runtime.connect(), timeout=30.0)
                    logger.info(f"Runtime connected successfully for session {sid}")
                except asyncio.TimeoutError:
                    logger.error(f"Runtime connection timeout for session {sid}")
                    raise RuntimeError(f"Runtime connection timeout after 30 seconds for session {sid}")
                except Exception as e:
                    logger.error(f"Runtime connection failed for session {sid}: {e}")
                    raise RuntimeError(f"Runtime connection failed for session {sid}: {e}")

                # 8. Initialize repository if needed (CLI pattern)
                repo_directory = None
                if self.config.sandbox.selected_repo:
                    logger.debug(f"Initializing repository for session {sid}")
                    repo_directory = initialize_repository_for_runtime(
                        runtime, selected_repository=self.config.sandbox.selected_repo
                    )

                # 9. Create memory AFTER runtime connection (CLI pattern)
                logger.debug(f"Creating memory for session {sid}")
                memory = create_memory(
                    runtime=runtime,
                    event_stream=event_stream,
                    sid=sid,
                    selected_repository=self.config.sandbox.selected_repo,
                    repo_directory=repo_directory,
                    conversation_instructions=None,
                )

                # 10. Add MCP tools if enabled (CLI pattern)
                if agent.config.enable_mcp:
                    logger.debug(f"Adding MCP tools for session {sid}")
                    await add_mcp_tools_to_agent(agent, runtime, memory, self.config)

                # 11. Create session context with AWAITING_USER_INPUT state (not LOADING)
                now = datetime.now()
                session_context = SessionContext(
                    sid=sid,
                    config=self.config,
                    runtime=runtime,
                    controller=controller,
                    event_stream=event_stream,
                    memory=memory,
                    agent_state=AgentState.AWAITING_USER_INPUT,  # Ready state, not LOADING
                    created_at=now,
                    last_activity=now,
                    task_description=task,
                    agent=agent,
                    repo_directory=repo_directory,
                    reload_microagents=False,
                    is_offline_mode=is_offline_mode,
                    is_connected=True,  # Connected after runtime.connect()
                    startup_time=time.time() - start_time,
                )

                # 12. Store session
                self.sessions[sid] = session_context

                # 13. Subscribe to events AFTER session is stored
                if hasattr(self, "event_manager") and self.event_manager:
                    logger.debug(f"Subscribing to events for session {sid}")
                    self.event_manager.subscribe_to_session(sid)

                # 14. Set as active if first session
                if self.active_session_id is None:
                    self.active_session_id = sid

                mode_info = "offline mode" if is_offline_mode else "online mode"
                logger.info(f"Session {sid} created successfully and ready for input in {mode_info}")

                return sid

            except Exception as e:
                logger.error(f"Failed to create session: {e}", exc_info=True)

                # Provide enhanced error messaging based on error type
                error_msg = str(e).lower()
                if (
                    "docker" in error_msg
                    and not NetworkConnectivityChecker.check_docker_availability()
                ):
                    enhanced_msg = (
                        "Docker is not available. Consider installing Docker or "
                        "setting tui_offline_mode=True in config to use LocalRuntime."
                    )
                    logger.error(enhanced_msg)
                elif "network" in error_msg or "connection" in error_msg:
                    enhanced_msg = (
                        "Network connectivity issues detected. "
                        "Check your internet connection or enable offline mode."
                    )
                    logger.error(enhanced_msg)
                elif "[errno -8]" in error_msg or "ai_socktype" in error_msg:
                    enhanced_msg = (
                        "DNS/socket resolution error detected. "
                        "This typically indicates network service configuration issues. "
                        "Try enabling offline mode or check your network configuration."
                    )
                    logger.error(enhanced_msg)

                raise

    async def start_session(self, session_id: str) -> None:
        """Start a session by initializing the agent controller with enhanced error handling.

        Args:
            session_id: ID of the session to start

        Raises:
            ValueError: If session ID is not found
            Exception: If session startup fails
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]
        session.connection_attempts += 1

        try:
            logger.info(
                f"Starting session: {session_id} (attempt {session.connection_attempts})"
            )
            logger.debug(f"Session {session_id} current state: {session.agent_state}")

            # Log session mode
            mode_info = "offline mode" if session.is_offline_mode else "online mode"
            logger.info(f"Session {session_id} running in {mode_info}")

            # Update agent state to LOADING
            logger.debug(f"Setting session {session_id} state to LOADING")
            session.agent_state = AgentState.LOADING

            # Connect to runtime if not already connected
            # Enhanced error handling for connection issues
            if (
                not hasattr(session.runtime, "_connected")
                or not session.runtime._connected
            ):
                logger.info(f"Connecting to runtime for session {session_id}")

                try:
                    await session.runtime.connect()
                    # Mark session as connected
                    self.set_session_connected(session_id, True)
                    logger.info(
                        f"Successfully connected to runtime for session {session_id}"
                    )

                except Exception as connect_error:
                    logger.error(
                        f"Runtime connection failed for session {session_id}: {connect_error}"
                    )

                    # Attempt fallback to LocalRuntime if not already using it
                    if (
                        not session.is_offline_mode
                        and NetworkConnectivityChecker.check_local_runtime_dependencies()
                    ):
                        logger.info(
                            f"Attempting fallback to LocalRuntime for session {session_id}"
                        )

                        try:
                            # Create a new LocalRuntime
                            original_runtime = self.config.runtime
                            self.config.runtime = "local"
                            new_runtime = create_runtime(
                                self.config,
                                sid=session_id,
                                headless_mode=True,
                                agent=session.agent,
                            )
                            self.config.runtime = original_runtime

                            # Close old runtime
                            try:
                                session.runtime.close()
                            except Exception as e:
                                logger.debug(f"Error closing old runtime: {e}")

                            # Replace runtime
                            session.runtime = new_runtime
                            session.is_offline_mode = True

                            # Try connecting with new runtime
                            await session.runtime.connect()
                            self.set_session_connected(session_id, True)
                            logger.info(
                                f"Successfully fell back to LocalRuntime for session {session_id}"
                            )

                        except Exception as fallback_error:
                            logger.error(
                                f"Fallback to LocalRuntime also failed: {fallback_error}"
                            )
                            raise connect_error  # Raise original error
                    else:
                        raise connect_error

            # Set agent state to AWAITING_USER_INPUT to indicate it's ready for interaction
            logger.debug(
                f"Setting controller state to AWAITING_USER_INPUT for session {session_id}"
            )
            await session.controller.set_agent_state_to(AgentState.AWAITING_USER_INPUT)

            # Update our local agent state to match
            logger.debug(
                f"Updating local session state to AWAITING_USER_INPUT for session {session_id}"
            )
            session.agent_state = AgentState.AWAITING_USER_INPUT

            # Subscribe to agent state changes to keep our local state in sync
            def state_change_callback(event):
                from openhands.events.observation import AgentStateChangedObservation

                if isinstance(event, AgentStateChangedObservation):
                    session.agent_state = event.agent_state
                    logger.debug(
                        f"Session {session_id} agent state changed to {event.agent_state}"
                    )

            # Subscribe to state changes
            session.event_stream.subscribe(
                "MAIN", state_change_callback, f"session_manager_state_{session_id}"
            )

            # Try to load microagents now that runtime is connected
            # This handles cases where microagents failed to load during session creation
            if not session.microagents_loaded:
                logger.info(f"Attempting to load microagents for session {session_id}")
                microagents_success = self.load_session_microagents(session_id)
                if microagents_success:
                    logger.info(
                        f"Successfully loaded microagents for session {session_id}"
                    )
                else:
                    logger.warning(
                        f"Microagents loading failed for session {session_id}, continuing without them"
                    )

            # Start the agent loop in the background using run_agent_until_done
            # This will run until the agent reaches a terminal state
            from openhands.core.loop import run_agent_until_done

            # Create a background task to run the agent with proper exception handling
            agent_task = asyncio.create_task(
                self._run_agent_until_done_safe(
                    session_id,
                    session.controller,
                    session.runtime,
                    session.memory,
                    [AgentState.STOPPED, AgentState.ERROR],
                )
            )

            # Track the task for cleanup and add exception handler
            self._cleanup_tasks[session_id] = agent_task
            agent_task.add_done_callback(
                lambda task: self._handle_agent_task_completion(session_id, task)
            )

            mode_info = "offline mode" if session.is_offline_mode else "online mode"
            logger.info(f"Session {session_id} started successfully in {mode_info}")

        except Exception as e:
            logger.error(f"Failed to start session {session_id}: {e}", exc_info=True)
            # Update state to indicate error
            session.agent_state = AgentState.ERROR

            # Record the error in session tracking
            self.record_session_error(session_id, str(e))

            # Provide enhanced error messages for common issues
            error_msg = str(e).lower()
            if "docker" in error_msg:
                user_friendly_msg = (
                    "Docker-related error. Please ensure Docker is running and accessible, "
                    "or enable offline mode to use LocalRuntime."
                )
                logger.error(user_friendly_msg)
                self.record_session_error(session_id, user_friendly_msg)
            elif "network" in error_msg or "connection" in error_msg:
                user_friendly_msg = (
                    "Network connectivity issue. Please check your internet connection "
                    "or enable offline mode."
                )
                logger.error(user_friendly_msg)
                self.record_session_error(session_id, user_friendly_msg)
            elif "[errno -8]" in error_msg or "ai_socktype" in error_msg:
                user_friendly_msg = (
                    "DNS/socket resolution error. This indicates network configuration issues. "
                    "Try enabling offline mode or checking your network setup."
                )
                logger.error(user_friendly_msg)
                self.record_session_error(session_id, user_friendly_msg)
            elif "timeout" in error_msg:
                user_friendly_msg = (
                    "Session startup timed out. This may be due to slow container initialization "
                    "or network issues. Try enabling offline mode for faster startup."
                )
                logger.error(user_friendly_msg)
                self.record_session_error(session_id, user_friendly_msg)
            elif "permission" in error_msg:
                user_friendly_msg = (
                    "Permission error. Please check file/directory permissions."
                )
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

            # Cancel any agent background tasks first
            if session_id in self._cleanup_tasks:
                agent_task = self._cleanup_tasks[session_id]
                if not agent_task.done():
                    logger.info(
                        f"Cancelling agent background task for session {session_id}"
                    )
                    agent_task.cancel()
                    try:
                        # Wait briefly for task to cancel
                        await asyncio.wait_for(agent_task, timeout=2.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        # Expected when cancelling
                        pass
                    except Exception as e:
                        logger.debug(
                            f"Exception during task cancellation for session {session_id}: {e}"
                        )

                del self._cleanup_tasks[session_id]

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

            # Remove from sessions
            del self.sessions[session_id]

            # Update active session if needed
            if self.active_session_id == session_id:
                if self.sessions:
                    # Switch to the most recently active session
                    self.active_session_id = max(
                        self.sessions.keys(),
                        key=lambda sid: self.sessions[sid].last_activity,
                    )
                else:
                    self.active_session_id = None

            logger.info(f"Closed session {session_id}")

        except Exception as e:
            logger.error(f"Error closing session {session_id}: {e}")
            # Still remove from sessions even if cleanup failed
            if session_id in self.sessions:
                del self.sessions[session_id]
            if session_id in self._cleanup_tasks:
                self._cleanup_tasks[session_id].cancel()
                del self._cleanup_tasks[session_id]
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
            self.sessions.values(), key=lambda s: s.last_activity, reverse=True
        )

    def update_session_activity(self, session_id: Optional[str] = None) -> None:
        """Update the last activity timestamp for a session.

        Args:
            session_id: ID of the session to update (defaults to active session)
        """
        target_id = session_id or self.active_session_id
        if target_id and target_id in self.sessions:
            self.sessions[target_id].last_activity = datetime.now()

    def update_session_task(
        self, task_description: str, session_id: Optional[str] = None
    ) -> None:
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
        # First cancel all background agent tasks
        if self._cleanup_tasks:
            logger.info(f"Cancelling {len(self._cleanup_tasks)} background agent tasks")
            for session_id, task in self._cleanup_tasks.items():
                if not task.done():
                    task.cancel()

            # Wait briefly for tasks to cancel
            if self._cleanup_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            *self._cleanup_tasks.values(), return_exceptions=True
                        ),
                        timeout=3.0,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Some background tasks did not cancel within timeout"
                    )
                except Exception as e:
                    logger.debug(f"Exception during background task cleanup: {e}")

            self._cleanup_tasks.clear()

        # Then close all sessions
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            try:
                await self.close_session(session_id)
            except Exception as e:
                logger.error(f"Error cleaning up session {session_id}: {e}")

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

    def load_session_microagents(self, session_id: Optional[str] = None) -> bool:
        """Load microagents for a session when runtime is connected.

        Args:
            session_id: ID of the session to load microagents for (defaults to active session)

        Returns:
            True if microagents were loaded successfully, False otherwise
        """
        target_id = session_id or self.active_session_id
        if target_id and target_id in self.sessions:
            session = self.sessions[target_id]
            try:
                # Get microagents from the selected repository
                selected_repo = getattr(session.config.sandbox, "selected_repo", None)
                microagents: List[BaseMicroagent] = (
                    session.runtime.get_microagents_from_selected_repo(selected_repo)
                )
                # Load microagents into memory
                session.memory.load_user_workspace_microagents(microagents)
                session.microagents_loaded = True
                session.reload_microagents = False
                logger.info(f"Successfully loaded microagents for session {target_id}")
                return True
            except Exception as e:
                logger.warning(
                    f"Failed to load microagents for session {target_id}: {e}"
                )
                logger.debug(f"Microagents loading error details: {e}", exc_info=True)
                session.microagents_loaded = False
                return False
        return False

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
                session.microagents_loaded = True
                logger.info(f"Reloaded microagents for session {target_id}")
            except Exception as e:
                logger.error(
                    f"Failed to reload microagents for session {target_id}: {e}"
                )
                session.microagents_loaded = False

    def mark_session_for_microagent_reload(
        self, session_id: Optional[str] = None
    ) -> None:
        """Mark a session for microagent reload.

        Args:
            session_id: ID of the session to mark (defaults to active session)
        """
        target_id = session_id or self.active_session_id
        if target_id and target_id in self.sessions:
            self.sessions[target_id].reload_microagents = True

    # TUI-specific interface methods

    def get_session_status(
        self, session_id: str
    ) -> Dict[str, Union[str, int, bool, float]]:
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
            "agent_state": session.agent_state.value
            if session.agent_state
            else "unknown",
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
            "microagents_loaded": session.microagents_loaded,
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
            logger.warning(
                f"Session {session_id} error #{session.error_count}: {error_message}"
            )

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
                session.startup_time = (
                    datetime.now() - session.created_at
                ).total_seconds()
            self.update_session_activity(session_id)

    async def _run_agent_until_done_safe(
        self,
        session_id: str,
        controller: AgentController,
        runtime: Runtime,
        memory: Memory,
        end_states: list[AgentState],
    ) -> None:
        """Safely run agent until done with proper exception handling.

        This method wraps run_agent_until_done to prevent background task
        exceptions from crashing the TUI event loop.

        Args:
            session_id: Session ID for logging and error tracking
            controller: Agent controller
            runtime: Runtime instance
            memory: Memory instance
            end_states: States that indicate the agent should stop
        """
        try:
            logger.info(f"Starting agent loop for session {session_id}")

            from openhands.core.loop import run_agent_until_done

            await run_agent_until_done(controller, runtime, memory, end_states)

            logger.info(f"Agent loop completed normally for session {session_id}")

        except asyncio.CancelledError:
            logger.info(f"Agent loop cancelled for session {session_id}")
            # Don't re-raise CancelledError as it's expected during cleanup

        except Exception as e:
            logger.error(
                f"Agent loop failed for session {session_id}: {e}", exc_info=True
            )

            # Update session to error state but don't crash the TUI
            session = self.get_session(session_id)
            if session:
                session.agent_state = AgentState.ERROR
                self.record_session_error(session_id, f"Agent loop failed: {e}")

            # Provide user-friendly error messages
            error_msg = str(e).lower()
            if "docker" in error_msg:
                user_friendly_msg = (
                    "Docker container error during agent execution. "
                    "Check Docker status or try offline mode."
                )
            elif "network" in error_msg or "connection" in error_msg:
                user_friendly_msg = (
                    "Network error during agent execution. "
                    "Check internet connection or try offline mode."
                )
            elif "timeout" in error_msg:
                user_friendly_msg = (
                    "Agent execution timed out. This may be due to resource constraints "
                    "or long-running operations."
                )
            else:
                user_friendly_msg = f"Agent execution error: {e}"

            logger.error(f"Session {session_id}: {user_friendly_msg}")

            # Note: We don't re-raise the exception to prevent TUI crashes

    def _handle_agent_task_completion(
        self, session_id: str, task: asyncio.Task
    ) -> None:
        """Handle completion of agent background task.

        Args:
            session_id: Session ID
            task: The completed asyncio task
        """
        try:
            # Remove from cleanup tasks tracking
            if session_id in self._cleanup_tasks:
                del self._cleanup_tasks[session_id]

            # Check if task completed successfully or with error
            if task.cancelled():
                logger.debug(f"Agent task cancelled for session {session_id}")
            elif task.done():
                # Task completed - check for exceptions
                try:
                    task.result()  # This will raise if there was an exception
                    logger.debug(
                        f"Agent task completed successfully for session {session_id}"
                    )
                except Exception as e:
                    # Exception was already handled in _run_agent_until_done_safe
                    logger.debug(
                        f"Agent task completed with handled exception for session {session_id}: {e}"
                    )

        except Exception as e:
            # Ensure task completion handler never crashes
            logger.error(
                f"Error in agent task completion handler for session {session_id}: {e}"
            )

        finally:
            # Update session activity to reflect task completion
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
            "agent_state_valid": session.agent_state
            in [AgentState.AWAITING_USER_INPUT, AgentState.RUNNING, AgentState.PAUSED],
            "recent_activity": (datetime.now() - session.last_activity).total_seconds()
            < 3600,  # 1 hour
            "low_error_count": session.error_count < 10,
        }

        healthy = all(health_checks.values())

        return {
            "healthy": healthy,
            "checks": health_checks,
            "error_count": session.error_count,
            "last_error": session.last_error,
            "agent_state": session.agent_state.value
            if session.agent_state
            else "unknown",
        }

    def get_sessions_by_state(self, state: AgentState) -> List[SessionContext]:
        """Get all sessions in a specific state.

        Args:
            state: Agent state to filter by

        Returns:
            List of sessions in the specified state
        """
        return [
            session
            for session in self.sessions.values()
            if session.agent_state == state
        ]

    def get_session_summary(self) -> Dict[str, Union[int, List[str]]]:
        """Get a summary of all sessions.

        Returns:
            Dictionary containing session summary information
        """
        total_sessions = len(self.sessions)
        active_sessions = len(self.get_sessions_by_state(AgentState.RUNNING))
        waiting_sessions = len(
            self.get_sessions_by_state(AgentState.AWAITING_USER_INPUT)
        )
        error_sessions = len(self.get_sessions_by_state(AgentState.ERROR))

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "waiting_sessions": waiting_sessions,
            "error_sessions": error_sessions,
            "session_ids": list(self.sessions.keys()),
            "active_session_id": self.active_session_id,
        }
