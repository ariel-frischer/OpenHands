"""TUI Entry Point.

Main entry point for the OpenHands TUI system with proper argument parsing
and CLI integration.
"""

import argparse
import asyncio
import os
import sys
from typing import Optional

from openhands.core.config import AppConfig
from openhands.core.config.utils import get_parser, setup_config_from_args
from openhands.core.logger import openhands_logger as logger
from openhands.storage.settings.file_settings_store import FileSettingsStore

from .app import OpenHandsTUIApp
from .utils.cli_integration import (
    extract_cli_config_setup,
    reuse_cli_security_check,
)


def get_tui_parser() -> argparse.ArgumentParser:
    """Get the argument parser for TUI with CLI argument compatibility.
    
    This extends the CLI argument parser with TUI-specific options while
    maintaining compatibility with all CLI arguments.
    
    Returns:
        ArgumentParser configured for TUI use
    """
    # Start with the CLI parser to maintain compatibility
    parser = get_parser()
    
    # Update description for TUI
    parser.description = 'Run OpenHands with Terminal User Interface (TUI)'
    
    # Add TUI-specific arguments
    parser.add_argument(
        '--tui-theme',
        type=str,
        default='default',
        choices=['default', 'dark', 'light'],
        help='TUI color theme (default: default)'
    )
    
    parser.add_argument(
        '--tui-log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='TUI logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--tui-refresh-rate',
        type=float,
        default=0.1,
        help='TUI refresh rate in seconds (default: 0.1)'
    )
    
    parser.add_argument(
        '--tui-max-history',
        type=int,
        default=1000,
        help='Maximum number of chat history items to keep (default: 1000)'
    )
    
    parser.add_argument(
        '--tui-timeout',
        type=int,
        default=0,
        help='TUI timeout in seconds (0 = no timeout, default: 0)'
    )
    
    parser.add_argument(
        '--tui-debug-layout',
        action='store_true',
        help='Skip session creation and runtime startup for quick layout debugging'
    )
    
    return parser


def parse_tui_arguments() -> argparse.Namespace:
    """Parse command line arguments for TUI.
    
    This function extends CLI argument parsing with TUI-specific options
    while maintaining full compatibility with CLI arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = get_tui_parser()
    args = parser.parse_args()
    
    if args.version:
        from openhands import __version__
        print(f'OpenHands TUI version: {__version__}')
        sys.exit(0)
    
    return args


def _handle_asyncio_exception(loop, context):
    """Global exception handler for asyncio tasks to prevent TUI crashes."""
    exception = context.get('exception')
    if exception:
        logger.error(f"Unhandled asyncio exception: {exception}", exc_info=exception)
    else:
        logger.error(f"Unhandled asyncio error: {context['message']}")


async def main() -> None:
    """Main entry point for the TUI application with CLI integration.
    
    This function provides the complete TUI startup sequence:
    1. Parse arguments (reusing CLI argument parsing)
    2. Setup configuration (reusing CLI config setup)
    3. Validate security (reusing CLI security check)
    4. Create and run TUI app
    """
    # Set up global exception handler for asyncio tasks
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_handle_asyncio_exception)
    
    try:
        # Parse arguments (reuse CLI argument parsing with TUI extensions)
        args = parse_tui_arguments()
        
        # Setup configuration (reuse CLI config setup)
        config = extract_cli_config_setup(args)
        
        # Validate security (reuse CLI security check)
        current_dir = config.workspace_base or os.getcwd()
        if not reuse_cli_security_check(config, current_dir):
            logger.error("Security check failed. Exiting.")
            sys.exit(1)
            return  # This won't be reached, but makes the intent clear
        
        # Create settings store
        settings_store = await FileSettingsStore.get_instance(config, None)
        
        logger.info("Starting OpenHands TUI...")
        logger.info(f"Working directory: {current_dir}")
        logger.info(f"Session name: {args.name if args.name else 'default'}")
        
        # Create and run TUI app
        app = OpenHandsTUIApp(config, settings_store, args)
        await app.run()
        
    except KeyboardInterrupt:
        logger.info("TUI interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"TUI startup error: {e}")
        sys.exit(1)


def main_sync(config: Optional[AppConfig] = None) -> None:
    """Synchronous entry point for backward compatibility.
    
    This function provides backward compatibility for code that expects
    a synchronous main function.
    
    Args:
        config: Optional AppConfig instance. If provided, will skip argument parsing.
    """
    if config is not None:
        # If config is provided, use it directly (backward compatibility)
        logger.info("Starting OpenHands TUI with provided config...")
        
        try:
            # Create settings store
            settings_store = asyncio.run(FileSettingsStore.get_instance(config, None))
            
            # Create mock args for compatibility
            args = argparse.Namespace()
            args.name = ''
            args.directory = config.workspace_base or os.getcwd()
            
            # Create and run TUI app
            app = OpenHandsTUIApp(config, settings_store, args)
            asyncio.run(app.run())
            
        except KeyboardInterrupt:
            logger.info("TUI interrupted by user")
            sys.exit(0)
        except Exception as e:
            logger.error(f"TUI error: {e}")
            sys.exit(1)
    else:
        # Use the full argument parsing and setup
        asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
