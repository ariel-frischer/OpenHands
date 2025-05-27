"""CLI Integration Utilities for TUI.

This module provides utilities to reuse existing CLI functions for session creation,
command handling, and configuration within the TUI environment.
"""

import asyncio
import logging
from typing import Callable

from openhands.cli.commands import check_folder_security_agreement, handle_commands
from openhands.cli.settings import display_settings
from openhands.cli.tui import UsageMetrics
from openhands.controller import AgentController
from openhands.controller.agent import Agent
from openhands.core.config import AppConfig, setup_config_from_args
from openhands.core.logger import openhands_logger as logger
from openhands.core.setup import (
    create_agent,
    create_controller,
    create_runtime,
    generate_sid,
)
from openhands.events.event import Event
from openhands.events.stream import EventStream
from openhands.runtime.base import Runtime
from openhands.storage.settings.file_settings_store import FileSettingsStore


class SessionContext:
    """Context object containing all session-related components."""

    def __init__(
        self,
        sid: str,
        agent: Agent,
        runtime: Runtime,
        controller: AgentController,
        event_stream: EventStream,
        usage_metrics: UsageMetrics,
        config: AppConfig,
    ):
        self.sid = sid
        self.agent = agent
        self.runtime = runtime
        self.controller = controller
        self.event_stream = event_stream
        self.usage_metrics = usage_metrics
        self.config = config


async def create_session_context(
    config: AppConfig,
    settings_store: FileSettingsStore,
    current_dir: str,
    session_name: str | None = None,
) -> SessionContext:
    """Create a session context using CLI session creation logic.
    
    This extracts the session creation logic from CLI's run_session function
    but returns a context object instead of running the full CLI loop.
    
    Args:
        config: Application configuration
        settings_store: Settings storage
        current_dir: Current working directory
        session_name: Optional session name
        
    Returns:
        SessionContext containing all session components
    """
    try:
        # Generate session ID
        sid = generate_sid(config, session_name)
        
        # Create agent
        agent = create_agent(config)
        
        # Create runtime
        runtime = create_runtime(
            config,
            sid=sid,
            headless_mode=True,
            agent=agent,
        )
        
        # Create controller
        controller, initial_state = create_controller(agent, runtime, config)
        
        # Get event stream
        event_stream = runtime.event_stream
        
        # Create usage metrics
        usage_metrics = UsageMetrics()
        
        logger.info(f"Created session context with SID: {sid}")
        
        return SessionContext(
            sid=sid,
            agent=agent,
            runtime=runtime,
            controller=controller,
            event_stream=event_stream,
            usage_metrics=usage_metrics,
            config=config,
        )
        
    except Exception as e:
        logger.error(f"Failed to create session context: {e}")
        raise


def adapt_cli_event_handler(
    session_context: SessionContext,
    tui_callback: Callable[[Event], None],
) -> Callable[[Event], None]:
    """Wrap CLI event handling with TUI updates.
    
    This creates an event handler that processes events through the CLI
    logic but also forwards them to the TUI for display updates.
    
    Args:
        session_context: Session context containing event stream
        tui_callback: TUI callback function for event updates
        
    Returns:
        Event handler function
    """
    def event_handler(event: Event) -> None:
        try:
            # Forward event to TUI callback
            tui_callback(event)
            
            # Log event for debugging
            logger.debug(f"Processed event: {event.event_type}")
            
        except Exception as e:
            logger.error(f"Error in event handler: {e}")
    
    return event_handler


def extract_cli_config_setup(args) -> AppConfig:
    """Reuse CLI configuration setup.
    
    This function wraps the CLI's setup_config_from_args function
    to provide the same configuration setup logic for the TUI.
    
    Args:
        args: Command line arguments or equivalent configuration
        
    Returns:
        Configured AppConfig object
    """
    try:
        config = setup_config_from_args(args)
        logger.info("Successfully set up configuration from CLI logic")
        return config
        
    except Exception as e:
        logger.error(f"Failed to setup configuration: {e}")
        raise


def reuse_cli_security_check(config: AppConfig, current_dir: str) -> bool:
    """Reuse CLI security validation.
    
    This function wraps the CLI's check_folder_security_agreement function
    to provide the same security validation logic for the TUI.
    
    Args:
        config: Application configuration
        current_dir: Current working directory to validate
        
    Returns:
        True if security check passes, False otherwise
    """
    try:
        result = check_folder_security_agreement(config, current_dir)
        logger.info(f"Security check for {current_dir}: {'passed' if result else 'failed'}")
        return result
        
    except Exception as e:
        logger.error(f"Security check failed: {e}")
        return False


async def handle_cli_command(
    command: str,
    session_context: SessionContext,
    current_dir: str,
    settings_store: FileSettingsStore,
) -> tuple[bool, bool, bool]:
    """Handle commands using CLI command processing logic.
    
    This function wraps the CLI's handle_commands function to process
    commands in the same way the CLI does, but within the TUI context.
    
    Args:
        command: Command string to process
        session_context: Session context containing event stream and metrics
        current_dir: Current working directory
        settings_store: Settings storage
        
    Returns:
        Tuple of (close_repl, reload_microagents, new_session_requested)
    """
    try:
        result = await handle_commands(
            command=command,
            event_stream=session_context.event_stream,
            usage_metrics=session_context.usage_metrics,
            sid=session_context.sid,
            config=session_context.config,
            current_dir=current_dir,
            settings_store=settings_store,
        )
        
        logger.info(f"Processed command: {command}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to handle command '{command}': {e}")
        # Return safe defaults
        return False, False, False


def display_cli_settings(config: AppConfig) -> None:
    """Display settings using CLI settings display logic.
    
    This function wraps the CLI's display_settings function to show
    configuration settings in the same format as the CLI.
    
    Args:
        config: Application configuration to display
    """
    try:
        display_settings(config)
        logger.info("Displayed settings using CLI logic")
        
    except Exception as e:
        logger.error(f"Failed to display settings: {e}")


async def cleanup_session_context(session_context: SessionContext) -> None:
    """Clean up session context resources.
    
    This function provides cleanup logic similar to the CLI's cleanup_session
    function but adapted for the session context structure.
    
    Args:
        session_context: Session context to clean up
    """
    try:
        # Save session state
        end_state = session_context.controller.get_state()
        end_state.save_to_session(
            session_context.event_stream.sid,
            session_context.event_stream.file_store,
            session_context.event_stream.user_id,
        )
        
        # Clean up resources
        session_context.agent.reset()
        session_context.runtime.close()
        await session_context.controller.close()
        
        logger.info(f"Cleaned up session context: {session_context.sid}")
        
    except Exception as e:
        logger.error(f"Error during session cleanup: {e}")


def create_stream_callback(tui_output_handler: Callable[[str], None]) -> Callable[[str], None]:
    """Create a stream callback for runtime output.
    
    This creates a callback function that can be used with runtime.subscribe_to_shell_stream
    to forward shell output to the TUI instead of the console.
    
    Args:
        tui_output_handler: TUI function to handle output strings
        
    Returns:
        Callback function for runtime stream subscription
    """
    def stream_callback(output: str) -> None:
        try:
            tui_output_handler(output)
        except Exception as e:
            logger.error(f"Error in stream callback: {e}")
    
    return stream_callback