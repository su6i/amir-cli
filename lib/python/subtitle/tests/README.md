# Subtitle Module Tests

Comprehensive unit test suite for the refactored subtitle module, validating all extracted workflow stages and ensuring correctness of the modularization.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                      # Common test fixtures and utilities
├── test_workflow_base.py            # Base context resolution tests
├── test_workflow_runtime.py         # Runtime execution tests
├── test_workflow_source_stage.py    # Source SRT preparation tests
├── test_workflow_translation_stage.py # Translation orchestration tests
├── test_workflow_rendering.py       # Video rendering tests
└── test_workflow_finalize.py        # Finalize/post/export tests
```

## Running Tests

### Run all tests
```bash
python3 -m pytest lib/python/subtitle/tests -v
```

### Run exactly like CI
```bash
python3 -m compileall lib/python/subtitle
python3 scripts/verify_refactoring.py
cd lib/python && python3 -m pytest subtitle/tests -q
```

### Run specific test file
```bash
python3 -m pytest lib/python/subtitle/tests/test_workflow_base.py -v
```

### Run specific test class
```bash
python3 -m pytest lib/python/subtitle/tests/test_workflow_base.py::TestResolveWorkflowBase -v
```

### Run specific test
```bash
python3 -m pytest lib/python/subtitle/tests/test_workflow_base.py::TestResolveWorkflowBase::test_basic_video_input -v
```

### Run with coverage
```bash
python3 -m pytest lib/python/subtitle/tests --cov=lib/python/subtitle/workflow --cov-report=html
```

## Test Coverage

### Workflow Base (`test_workflow_base.py`)
- Basic video input path resolution
- SRT input detection
- Auto source language detection
- Post-only mode context
- Subtitle geometry detection
- Legacy SRT migration

### Workflow Runtime (`test_workflow_runtime.py`)
- Post-only early exit flag
- Source language auto-detection
- Target language resolution
- Time-range limit handling
- Context dict key validation

### Workflow Source Stage (`test_workflow_source_stage.py`)
- Source SRT preparation
- Transcription with force flag
- Time-limited transcription
- Speaker detection in transcription
- Existing SRT reuse logic

### Workflow Translation Stage (`test_workflow_translation_stage.py`)
- Translation stage orchestration
- Empty input handling
- Per-language translation
- Force retranslation flag

### Workflow Rendering (`test_workflow_rendering.py`)
- Rendering stage success/failure return
- ASS file creation
- Custom resolution handling
- Custom quality/FPS parameters

### Workflow Finalize (`test_workflow_finalize.py`)
- Social post generation
- Export format handling
- Output bundling
- Empty result handling

## Test Utilities (`conftest.py`)

### TempWorkspace Context Manager
Provides automatic temporary directory setup/cleanup:
```python
with TempWorkspace() as temp_dir:
    # Tests run in temp_dir
    # Automatically cleaned up on exit
    pass
```

### create_mock_processor()
Create a mock processor with common method stubs:
```python
processor = create_mock_processor(
    transcribe_result="1\n...",
    detect_language_result='fa'
)
```

### ProcessorBuilder
Builder pattern for creating configured mock processors:
```python
processor = (ProcessorBuilder()
    .with_language_detection('fa')
    .with_transcription(content)
    .with_translation(results)
    .build())
```

## Mock Processor Pattern

All tests follow the mock processor pattern to isolate workflow stages:

```python
def test_something(self):
    self.mock_processor = Mock()
    self.mock_processor.logger = Mock()
    
    # Use in test
    result = workflow_helper(
        self.mock_processor,
        **kwargs
    )
```

This ensures:
- Tests don't require real video files
- Tests don't call actual LLM APIs
- Tests run quickly and reliably
- Extraction correctness is validated

## Continuous Integration

These tests should be:
1. Run after each extraction commit to ensure no regressions
2. Added to CI/CD pipeline to catch breaking changes
3. Extended as new workflow stages are added or modified
4. Used to validate refactoring doesn't change behavior

## Future Enhancements

- Integration tests with real video files (slow, optional)
- Performance regression tests comparing pre/post refactoring
- End-to-end tests of full run_workflow
- Fixtures for various subtitle formats and edge cases
