# TUI Development Workflow

This document outlines the development workflow for OpenHands TUI (Terminal User Interface) components.

## Development Environment Setup

### Prerequisites
- Poetry 2.1.3+
- Python 3.12+
- pytest 8.3.5+
- ruff 0.11.10+

### Environment Verification
```bash
# Verify poetry environment
poetry --version
poetry run python --version
poetry run pytest --version
poetry run ruff --version
```

## Code Quality Standards

### Mandatory Linting Steps
All TUI code must pass these quality checks before completion:

```bash
# 1. Fix linting issues automatically
poetry run ruff check openhands/tui/ --fix

# 2. Format code consistently
poetry run ruff format openhands/tui/

# 3. Run relevant TUI tests
poetry run python -m pytest tests/unit/test_tui_*.py -v
```

### Pre-commit Requirements
- All TUI code must be linted with ruff
- All TUI code must be formatted with ruff
- All TUI tests must pass
- No lint errors or warnings allowed

## TUI Testing Guidelines

### CRITICAL: Never Use `make tui`
**NEVER** run `make tui` during development as it gets stuck and cannot exit properly.

### Use `make test-tui` Instead
Always use the following command for TUI testing:

```bash
# Test TUI with proper logging and timeout
make test-tui
```

This command:
- Runs TUI with debug layout (skips problematic session creation)
- Uses 15-second OS timeout and 12-second TUI timeout
- Captures all logs to timestamped files in `logs/` directory
- Shows real-time output with DEBUG log level
- Provides log file statistics after completion

### Alternative Testing Scripts
```bash
# Test with debug layout (recommended for development)
bash scripts/test_tui.sh

# Test with full session creation (for integration testing)
bash scripts/test_tui_full.sh
```

## TUI Architecture Constraints

### TUI-Only Scope
- Only modify files in `openhands/tui/` directory
- Preserve existing backend logic - use CLI methods without duplication
- TUI should be a thin interface layer only
- No modifications to core OpenHands functionality

### Interface Pattern
- TUI wraps existing functionality, doesn't reimplement it
- Use existing CLI integration methods
- Maintain strict separation between TUI and backend

## Testing Requirements

### Unit Test Coverage
All TUI components must have comprehensive unit tests in `tests/unit/test_tui_*.py`:

- Mock all external dependencies
- Test all public methods and key private methods
- Include error handling and edge cases
- Use proper async/await patterns for async methods

### Test Execution
```bash
# Run all TUI tests
poetry run python -m pytest tests/unit/test_tui_*.py -v

# Run specific test file
poetry run python -m pytest tests/unit/test_tui_chat_panel.py -v

# Run with coverage
poetry run python -m pytest tests/unit/test_tui_*.py --cov=openhands.tui --cov-report=html
```

### Mock Requirements
- Mock all PyTermGUI components
- Mock all session managers and event managers
- Mock all file operations and external services
- Use AsyncMock for async methods

## Development Workflow

### 1. Setup Development Environment
```bash
# Verify environment
make check-dependencies
poetry install

# Verify TUI testing works
make test-tui
```

### 2. Code Development
```bash
# Make changes to TUI code in openhands/tui/
# Follow TUI-only scope constraints
```

### 3. Quality Assurance
```bash
# Fix linting issues
poetry run ruff check openhands/tui/ --fix

# Format code
poetry run ruff format openhands/tui/

# Run tests
poetry run python -m pytest tests/unit/test_tui_*.py -v
```

### 4. Integration Testing
```bash
# Test TUI functionality
make test-tui

# Check logs for issues
ls -la logs/tui_test_*.log
tail -50 logs/tui_test_*.log
```

### 5. Final Validation
```bash
# Ensure all quality checks pass
poetry run ruff check openhands/tui/
poetry run ruff format openhands/tui/ --check
poetry run python -m pytest tests/unit/test_tui_*.py
make test-tui
```

## File Structure

```
openhands/tui/
├── __init__.py
├── app.py                 # Main TUI application
├── main.py               # TUI entry point
├── managers/             # TUI managers
│   ├── event_manager.py  # Event handling
│   └── session_manager.py # Session management
├── panels/               # TUI panels
│   ├── __init__.py
│   ├── base_panel.py     # Base panel class
│   ├── chat_panel.py     # Chat interface
│   ├── logs_panel.py     # Log display
│   └── sessions_panel.py # Session management
├── utils/                # TUI utilities
│   └── keybindings.py    # Keyboard shortcuts
└── widgets/              # Custom widgets

tests/unit/
├── test_tui_*.py         # TUI unit tests
```

## Common Issues and Solutions

### Import Errors
- Ensure poetry environment is activated
- Check that all dependencies are installed
- Verify Python path includes project root

### Test Failures
- Check mock configurations
- Verify async/await patterns
- Ensure proper cleanup in test teardown

### TUI Hanging
- Never use `make tui` directly
- Always use `make test-tui` with timeout
- Check logs for session creation issues

### Linting Errors
- Run `poetry run ruff check openhands/tui/ --fix`
- Run `poetry run ruff format openhands/tui/`
- Check for import order and unused imports

## Best Practices

### Code Organization
- Keep TUI logic separate from business logic
- Use dependency injection for testability
- Follow single responsibility principle
- Maintain consistent error handling

### Testing
- Write tests before implementing features
- Use descriptive test names
- Test both success and failure paths
- Mock external dependencies completely

### Documentation
- Document all public methods
- Include type hints
- Provide usage examples
- Keep documentation up to date

### Performance
- Avoid blocking operations in TUI thread
- Use async/await for I/O operations
- Implement proper cleanup for resources
- Monitor memory usage in long-running sessions 