# AGENTS.md

## Build/Lint/Test Commands
- **Install dependencies**: `pip install -r requirements.txt`
- **Run server**: `uvicorn app.main:app --reload`
- **Debug single cycle**: `python debug_engine.py`
- **Run tests**: No test framework configured yet
- **Run single test**: No test framework configured yet

## Code Style Guidelines

### Imports
- Standard library imports first
- Third-party imports second
- Local imports last
- Use absolute imports for local modules

### Formatting
- Use 4 spaces for indentation
- Line length: no strict limit, but keep readable
- Use f-strings for string formatting

### Types
- Use type hints for all function parameters and return values
- Use `typing` module for complex types (List, Dict, Optional, etc.)
- Use Pydantic BaseModel for data structures

### Naming Conventions
- Functions/variables: snake_case
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE
- Private methods: _leading_underscore

### Error Handling
- Use try/except blocks for expected errors
- Log errors with descriptive messages
- Don't suppress exceptions without good reason

### Documentation
- Use docstrings for all public functions and classes
- Keep docstrings concise but informative</content>
<parameter name="filePath">/home/wzhao/Github/alpha_arena/AGENTS.md