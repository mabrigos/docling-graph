# Integration Test Assets

Place your test files here:

1. **PDF document** — any PDF you want to extract from (e.g., `sample.pdf`)
2. **Pydantic template** — a Python file with your extraction template (e.g., `templates.py`)

## Example template structure

```python
# templates.py
from pydantic import BaseModel, Field
from typing import List, Optional

class LessonPlan(BaseModel):
    title: str = Field(description="Title of the lesson")
    subject: str = Field(description="Subject area")
    objectives: List[str] = Field(description="Learning objectives")
    # ... add your fields
```

## Running the integration test

```bash
# Make sure .env is configured (copy from .env.example)
cp .env.example .env
# Edit .env with your values

# Run the test
python scripts/test_integration.py \
    --source scripts/tests/sample.pdf \
    --template scripts.tests.templates.LessonPlan
```
