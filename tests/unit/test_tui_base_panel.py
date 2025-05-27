"""Unit tests for TUI Base Panel."""

import pytest
from unittest.mock import MagicMock, patch
import pytermgui as ptg

from openhands.tui.panels.base_panel import BasePanel


class TestBasePanel(BasePanel):
    """Test implementation of BasePanel for testing."""
    
    def update_display(self, session_id: str = "") -> None:
        """Test implementation."""
        pass
    
    def get_panel_name(self) -> str:
        """Test implementation."""
        return "test"


class TestBasePanelClass:
    """Test cases for BasePanel class."""
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create mock session manager."""
        return MagicMock()
    
    @pytest.fixture
    def mock_file_manager(self):
        """Create mock file manager."""
        return MagicMock()
    
    @pytest.fixture
    def base_panel(self, mock_session_manager, mock_file_manager):
        """Create test base panel instance."""
        return TestBasePanel(mock_session_manager, mock_file_manager, "Test Panel")
    
    def test_initialization(self, base_panel, mock_session_manager, mock_file_manager):
        """Test base panel initialization."""
        assert base_panel.session_manager == mock_session_manager
        assert base_panel.file_manager == mock_file_manager
        assert base_panel.title == "Test Panel"
        
        # Check that title label was added
        assert len(base_panel._widgets) >= 2
        assert isinstance(base_panel._widgets[0], ptg.Label)
        assert "[bold]Test Panel[/bold]" in str(base_panel._widgets[0])
    
    def test_clear_content(self, base_panel):
        """Test clearing panel content."""
        # Add some content
        base_panel.add_content(ptg.Label("Test content 1"))
        base_panel.add_content(ptg.Label("Test content 2"))
        
        initial_count = len(base_panel._widgets)
        assert initial_count > 2
        
        # Clear content
        base_panel.clear_content()
        
        # Should keep title and spacer
        assert len(base_panel._widgets) == 2
    
    def test_add_content(self, base_panel):
        """Test adding content to panel."""
        initial_count = len(base_panel._widgets)
        
        test_widget = ptg.Label("Test content")
        base_panel.add_content(test_widget)
        
        assert len(base_panel._widgets) == initial_count + 1
        assert base_panel._widgets[-1] == test_widget
    
    def test_set_focus(self, base_panel):
        """Test setting focus to panel."""
        # Should not raise an exception
        base_panel.set_focus()
    
    def test_handle_key_event_default(self, base_panel):
        """Test default key event handling."""
        # Default implementation should return False
        assert base_panel.handle_key_event("a") is False
        assert base_panel.handle_key_event("Enter") is False
    
    def test_abstract_methods_implemented(self, base_panel):
        """Test that abstract methods are implemented in test class."""
        # Should not raise NotImplementedError
        base_panel.update_display()
        assert base_panel.get_panel_name() == "test"
    
    def test_abstract_methods_required(self, mock_session_manager, mock_file_manager):
        """Test that abstract methods are required in base class."""
        # Cannot instantiate BasePanel directly due to abstract methods
        with pytest.raises(TypeError):
            BasePanel(mock_session_manager, mock_file_manager, "Test")