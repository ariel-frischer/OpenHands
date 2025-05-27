"""Tests for TUI session manager network connectivity features."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.core.config import AppConfig
from openhands.core.schema import AgentState
from openhands.tui.managers.session_manager import (
    NetworkConnectivityChecker,
    SessionManager,
    SessionContext,
)


class TestNetworkConnectivityChecker:
    """Test cases for NetworkConnectivityChecker."""

    def test_check_internet_connectivity_success(self):
        """Test successful internet connectivity check."""
        with patch('socket.socket') as mock_socket:
            mock_socket_instance = MagicMock()
            mock_socket.return_value = mock_socket_instance
            mock_socket_instance.connect.return_value = None
            
            result = NetworkConnectivityChecker.check_internet_connectivity()
            assert result is True
            mock_socket_instance.connect.assert_called_once_with(("8.8.8.8", 53))

    def test_check_internet_connectivity_failure(self):
        """Test failed internet connectivity check."""
        with patch('socket.socket') as mock_socket:
            mock_socket_instance = MagicMock()
            mock_socket.return_value = mock_socket_instance
            mock_socket_instance.connect.side_effect = OSError("Connection failed")
            
            result = NetworkConnectivityChecker.check_internet_connectivity()
            assert result is False

    def test_check_docker_availability_success(self):
        """Test successful Docker availability check."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            result = NetworkConnectivityChecker.check_docker_availability()
            assert result is True
            mock_run.assert_called_once_with(
                ["docker", "version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )

    def test_check_docker_availability_failure(self):
        """Test failed Docker availability check."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("docker not found")
            
            result = NetworkConnectivityChecker.check_docker_availability()
            assert result is False

    def test_check_local_runtime_dependencies_success(self):
        """Test successful LocalRuntime dependencies check."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            result = NetworkConnectivityChecker.check_local_runtime_dependencies()
            assert result is True
            mock_run.assert_called_once_with(
                ["poetry", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )

    def test_check_local_runtime_dependencies_failure(self):
        """Test failed LocalRuntime dependencies check."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("poetry not found")
            
            result = NetworkConnectivityChecker.check_local_runtime_dependencies()
            assert result is False

    def test_get_connectivity_status(self):
        """Test comprehensive connectivity status check."""
        with patch.object(NetworkConnectivityChecker, 'check_internet_connectivity', return_value=True), \
             patch.object(NetworkConnectivityChecker, 'check_docker_availability', return_value=False), \
             patch.object(NetworkConnectivityChecker, 'check_local_runtime_dependencies', return_value=True):
            
            status = NetworkConnectivityChecker.get_connectivity_status()
            
            expected = {
                "internet": True,
                "docker": False,
                "local_runtime": True,
            }
            assert status == expected


class TestSessionManagerNetworkFeatures:
    """Test cases for SessionManager network connectivity features."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock AppConfig."""
        config = MagicMock()
        config.runtime = "docker"
        config.sandbox = MagicMock()
        config.sandbox.selected_repo = None
        config.jwt_secret = "test-secret"
        config.workspace_base = "/tmp/test"
        config.tui_offline_mode = False
        return config

    @pytest.fixture
    def session_manager(self, mock_config):
        """Create a SessionManager instance."""
        return SessionManager(mock_config, None)

    def test_should_use_offline_mode_explicit_config(self, session_manager):
        """Test offline mode when explicitly enabled in config."""
        session_manager.config.tui_offline_mode = True
        
        result = session_manager._should_use_offline_mode()
        assert result is True

    def test_should_use_offline_mode_no_docker_with_local(self, session_manager):
        """Test offline mode when Docker unavailable but LocalRuntime available."""
        session_manager.config.tui_offline_mode = False
        session_manager._connectivity_status = {
            "internet": True,
            "docker": False,
            "local_runtime": True,
        }
        
        # Mock time.time to prevent connectivity refresh
        with patch('time.time', return_value=0.0):
            session_manager._last_connectivity_check = 0.0
            result = session_manager._should_use_offline_mode()
            assert result is True

    def test_should_use_offline_mode_no_internet_with_local(self, session_manager):
        """Test offline mode when no internet but LocalRuntime available."""
        session_manager.config.tui_offline_mode = False
        session_manager._connectivity_status = {
            "internet": False,
            "docker": True,
            "local_runtime": True,
        }
        
        # Mock time.time to prevent connectivity refresh
        with patch('time.time', return_value=0.0):
            session_manager._last_connectivity_check = 0.0
            result = session_manager._should_use_offline_mode()
            assert result is True

    def test_should_use_offline_mode_all_available(self, session_manager):
        """Test online mode when all services available."""
        session_manager.config.tui_offline_mode = False
        session_manager._connectivity_status = {
            "internet": True,
            "docker": True,
            "local_runtime": True,
        }
        
        result = session_manager._should_use_offline_mode()
        assert result is False

    def test_get_runtime_for_session_offline_mode(self, session_manager):
        """Test runtime creation in offline mode."""
        mock_agent = MagicMock()
        
        with patch.object(session_manager, '_should_use_offline_mode', return_value=True), \
             patch('openhands.tui.managers.session_manager.create_runtime') as mock_create_runtime:
            
            mock_runtime = MagicMock()
            mock_create_runtime.return_value = mock_runtime
            
            result = session_manager._get_runtime_for_session("test-sid", mock_agent)
            
            # Verify that runtime was created with "local" config
            mock_create_runtime.assert_called_once()
            call_args = mock_create_runtime.call_args
            assert call_args[1]['sid'] == "test-sid"
            assert call_args[1]['headless_mode'] is True
            assert call_args[1]['agent'] == mock_agent
            
            # Verify config was temporarily changed to "local"
            assert session_manager.config.runtime == "docker"  # Should be restored

    def test_get_runtime_for_session_online_mode(self, session_manager):
        """Test runtime creation in online mode."""
        mock_agent = MagicMock()
        
        with patch.object(session_manager, '_should_use_offline_mode', return_value=False), \
             patch('openhands.tui.managers.session_manager.create_runtime') as mock_create_runtime:
            
            mock_runtime = MagicMock()
            mock_create_runtime.return_value = mock_runtime
            
            result = session_manager._get_runtime_for_session("test-sid", mock_agent)
            
            # Verify that runtime was created with original config
            mock_create_runtime.assert_called_once()
            call_args = mock_create_runtime.call_args
            assert call_args[1]['sid'] == "test-sid"
            assert call_args[1]['headless_mode'] is True
            assert call_args[1]['agent'] == mock_agent

    @pytest.mark.asyncio
    async def test_create_session_with_connectivity_logging(self, session_manager):
        """Test session creation logs connectivity status."""
        with patch('openhands.tui.managers.session_manager.generate_sid', return_value="test-sid"), \
             patch('openhands.tui.managers.session_manager.create_agent') as mock_create_agent, \
             patch.object(session_manager, '_get_runtime_for_session') as mock_get_runtime, \
             patch('openhands.tui.managers.session_manager.create_controller') as mock_create_controller, \
             patch('openhands.tui.managers.session_manager.create_memory') as mock_create_memory, \
             patch.object(NetworkConnectivityChecker, 'get_connectivity_status') as mock_connectivity, \
             patch('openhands.tui.managers.session_manager.logger') as mock_logger:
            
            # Setup mocks
            mock_agent = MagicMock()
            mock_create_agent.return_value = mock_agent
            
            mock_runtime = MagicMock()
            mock_runtime.__class__.__name__ = "LocalRuntime"
            mock_runtime.event_stream = MagicMock()
            mock_get_runtime.return_value = mock_runtime
            
            mock_controller = MagicMock()
            mock_initial_state = MagicMock()
            mock_create_controller.return_value = (mock_controller, mock_initial_state)
            
            mock_memory = MagicMock()
            mock_create_memory.return_value = mock_memory
            
            connectivity_status = {
                "internet": False,
                "docker": False,
                "local_runtime": True,
            }
            mock_connectivity.return_value = connectivity_status
            
            # Call create_session
            result = await session_manager.create_session("test task")
            
            # Verify connectivity status was logged
            mock_logger.info.assert_any_call(f"Connectivity status: {connectivity_status}")
            
            # Verify session was created with offline mode
            assert result == "test-sid"
            session = session_manager.get_session("test-sid")
            assert session.is_offline_mode is True

    @pytest.mark.asyncio
    async def test_start_session_with_fallback_to_local_runtime(self, session_manager):
        """Test session start with fallback to LocalRuntime on connection failure."""
        # Create a mock session
        mock_runtime = MagicMock()
        mock_runtime._connected = False
        mock_runtime.connect = AsyncMock(side_effect=Exception("Docker connection failed"))
        mock_runtime.close = MagicMock()
        
        mock_controller = MagicMock()
        mock_controller.set_agent_state_to = AsyncMock()
        
        mock_event_stream = MagicMock()
        mock_event_stream.subscribe = MagicMock()
        
        mock_agent = MagicMock()
        
        session = SessionContext(
            sid="test-session",
            config=session_manager.config,
            runtime=mock_runtime,
            controller=mock_controller,
            event_stream=mock_event_stream,
            memory=MagicMock(),
            agent_state=AgentState.LOADING,
            created_at=MagicMock(),
            last_activity=MagicMock(),
            agent=mock_agent,
            is_offline_mode=False,
        )
        
        session_manager.sessions["test-session"] = session
        
        # Mock fallback runtime creation
        mock_new_runtime = MagicMock()
        mock_new_runtime.connect = AsyncMock()
        
        with patch.object(NetworkConnectivityChecker, 'check_local_runtime_dependencies', return_value=True), \
             patch('openhands.tui.managers.session_manager.create_runtime', return_value=mock_new_runtime) as mock_create_runtime, \
             patch('openhands.core.loop.run_agent_until_done') as mock_run_agent, \
             patch('asyncio.create_task') as mock_create_task:
            
            # Call start_session
            await session_manager.start_session("test-session")
            
            # Verify fallback runtime was created
            mock_create_runtime.assert_called_once()
            
            # Verify old runtime was closed
            mock_runtime.close.assert_called_once()
            
            # Verify session was updated to offline mode
            assert session.is_offline_mode is True
            assert session.runtime == mock_new_runtime
            
            # Verify new runtime was connected
            mock_new_runtime.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_session_enhanced_error_messages(self, session_manager):
        """Test enhanced error messages for different failure types."""
        # Create a mock session
        mock_runtime = MagicMock()
        mock_runtime._connected = False
        mock_runtime.connect = AsyncMock(side_effect=Exception("[Errno -8] Servname not supported for ai_socktype"))
        
        session = SessionContext(
            sid="test-session",
            config=session_manager.config,
            runtime=mock_runtime,
            controller=MagicMock(),
            event_stream=MagicMock(),
            memory=MagicMock(),
            agent_state=AgentState.LOADING,
            created_at=MagicMock(),
            last_activity=MagicMock(),
            agent=MagicMock(),
            is_offline_mode=False,
        )
        
        session_manager.sessions["test-session"] = session
        
        with patch.object(NetworkConnectivityChecker, 'check_local_runtime_dependencies', return_value=False), \
             patch('openhands.tui.managers.session_manager.logger') as mock_logger, \
             pytest.raises(Exception):
            
            await session_manager.start_session("test-session")
            
            # Verify enhanced error message was logged
            mock_logger.error.assert_any_call(
                "DNS/socket resolution error. This indicates network configuration issues. "
                "Try enabling offline mode or checking your network setup."
            )

    def test_connectivity_status_caching(self, session_manager):
        """Test that connectivity status is cached to avoid frequent checks."""
        with patch.object(NetworkConnectivityChecker, 'get_connectivity_status') as mock_get_status:
            mock_get_status.return_value = {"internet": True, "docker": True, "local_runtime": True}
            
            # First call should check connectivity
            session_manager._should_use_offline_mode()
            assert mock_get_status.call_count == 1
            
            # Second call within cache interval should not check again
            session_manager._should_use_offline_mode()
            assert mock_get_status.call_count == 1
            
            # Simulate time passing beyond cache interval
            session_manager._last_connectivity_check = 0.0
            session_manager._should_use_offline_mode()
            assert mock_get_status.call_count == 2

    @pytest.mark.asyncio
    async def test_create_session_enhanced_error_handling(self, session_manager):
        """Test enhanced error handling during session creation."""
        with patch('openhands.tui.managers.session_manager.generate_sid', side_effect=Exception("Docker daemon not running")), \
             patch.object(NetworkConnectivityChecker, 'check_docker_availability', return_value=False), \
             patch('openhands.tui.managers.session_manager.logger') as mock_logger, \
             pytest.raises(Exception):
            
            await session_manager.create_session("test task")
            
            # Verify enhanced error message was logged
            mock_logger.error.assert_any_call(
                "Docker is not available. Consider installing Docker or "
                "setting tui_offline_mode=True in config to use LocalRuntime."
            ) 