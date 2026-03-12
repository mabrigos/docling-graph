"""
Sample Pydantic extraction templates for testing.

Place your own templates here alongside these examples.
The template class is referenced by its dotted path, e.g.:
    scripts.tests.templates.LessonPlan
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class LessonPlan(BaseModel):
    """Template for extracting lesson plan information from a document."""

    title: str = Field(description="Title of the lesson or module")
    subject: str = Field(description="Subject area (e.g., Mathematics, Science, English)")
    grade_level: Optional[str] = Field(
        default=None, description="Target grade level or age group"
    )
    objectives: List[str] = Field(
        default_factory=list,
        description="List of learning objectives or outcomes",
    )
    topics: List[str] = Field(
        default_factory=list,
        description="Key topics or concepts covered in the lesson",
    )
    activities: List[str] = Field(
        default_factory=list,
        description="Activities or exercises described in the lesson",
    )
    materials: List[str] = Field(
        default_factory=list,
        description="Materials or resources needed for the lesson",
    )
    duration: Optional[str] = Field(
        default=None, description="Estimated duration of the lesson"
    )
    assessment: Optional[str] = Field(
        default=None,
        description="Assessment method or criteria described in the document",
    )
    summary: Optional[str] = Field(
        default=None, description="Brief summary of the lesson content"
    )


class DocumentSummary(BaseModel):
    """Generic template for extracting a structured summary from any document."""

    title: str = Field(description="Document title")
    document_type: Optional[str] = Field(
        default=None,
        description="Type of document (e.g., report, article, manual, lesson plan)",
    )
    main_topics: List[str] = Field(
        default_factory=list, description="Main topics or themes in the document"
    )
    key_points: List[str] = Field(
        default_factory=list, description="Key points or findings"
    )
    summary: str = Field(description="Concise summary of the document contents")
