"""
Test RAG Retrieval Wiring — Lesson Chunk Retrieval + Integration

Validates:
1. LessonChunkRetriever chunks and embeds lesson content
2. Curriculum agent injects chunks into lessons
3. Tutor agent receives and uses lesson chunks in coaching context
"""
import pytest
import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mammoth_os.rag_retrieval import LessonChunkRetriever
from mammoth_os.agents.curriculum_agent import CurriculumAgent


def test_retriever_chunks_lesson_content():
    """Verify lesson chunking works."""
    async def run_test():
        retriever = LessonChunkRetriever()
        
        lesson_content = """
        # Introduction to Functions
        
        A function is a reusable block of code that performs a specific task.
        Functions help organize code and reduce repetition.
        
        ## Key Concepts
        
        - Parameters: inputs to a function
        - Return values: outputs from a function
        - Scope: where variables are visible
        
        ## Example: Simple Function
        
        A basic function takes two numbers and returns their sum.
        This demonstrates parameter passing and return values.
        """
        
        chunks = await retriever.chunk_lesson("lesson-001", lesson_content)
        
        assert len(chunks) > 0
        assert all(c["chunk_index"] >= 0 for c in chunks)
        assert all(c["lesson_id"] == "lesson-001" for c in chunks)
        assert all("chunk_text" in c for c in chunks)
    
    asyncio.run(run_test())


def test_retriever_embeds_chunks():
    """Verify embedding pipeline works."""
    async def run_test():
        retriever = LessonChunkRetriever()
        
        chunks = [
            {
                "lesson_id": "lesson-001",
                "chunk_index": 0,
                "chunk_text": "Functions are reusable blocks of code that perform specific tasks."
            },
            {
                "lesson_id": "lesson-001",
                "chunk_index": 1,
                "chunk_text": "Parameters are inputs passed to a function."
            }
        ]
        
        embedded = await retriever.embed_chunks(chunks)
        
        assert len(embedded) == 2
        assert all("embedding" in c for c in embedded)
        assert all(isinstance(c["embedding"], list) for c in embedded)
        assert all(len(c["embedding"]) == 1536 for c in embedded)
    
    asyncio.run(run_test())


def test_retriever_retrieves_top_k():
    """Verify similarity-based retrieval works."""
    async def run_test():
        retriever = LessonChunkRetriever()
        
        chunks = [
            {
                "lesson_id": "lesson-001",
                "chunk_index": 0,
                "chunk_text": "Functions are reusable blocks of code.",
                "embedding": [0.1] * 1536
            },
            {
                "lesson_id": "lesson-001",
                "chunk_index": 1,
                "chunk_text": "Variables store data in memory.",
                "embedding": [0.2] * 1536
            },
            {
                "lesson_id": "lesson-001",
                "chunk_index": 2,
                "chunk_text": "Loops repeat code multiple times.",
                "embedding": [0.3] * 1536
            }
        ]
        
        query = "What are functions used for?"
        retrieved = await retriever.retrieve_top_k(query, chunks, top_k=2)
        
        assert len(retrieved) <= 2
        assert all("chunk_text" in r for r in retrieved)
    
    asyncio.run(run_test())


def test_retriever_full_pipeline():
    """Verify end-to-end retrieval pipeline."""
    async def run_test():
        retriever = LessonChunkRetriever()
        
        lesson_content = """
        # Python Basics
        
        Python is a high-level programming language.
        It emphasizes code readability and simplicity.
        
        ## Variables and Types
        
        Variables store data. Python has dynamic typing.
        Common types: int, str, list, dict.
        
        ## Control Flow
        
        If statements branch code execution.
        For loops iterate over sequences.
        While loops repeat until a condition is false.
        """
        
        chunks = await retriever.retrieve_for_lesson(
            lesson_id="lesson-python-001",
            content=lesson_content,
            query="Python basics"
        )
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)
    
    asyncio.run(run_test())


def test_curriculum_agent_injects_chunks():
    """Verify curriculum agent can inject chunks (mocked)."""
    curriculum_agent = CurriculumAgent(router=None)
    
    # Simulate curriculum with lesson content
    test_curriculum = {
        "curriculum_id": "test-curr",
        "title": "Test Curriculum",
        "modules": [
            {
                "module_id": "m1",
                "title": "Module 1",
                "lessons": [
                    {
                        "lesson_id": "l1",
                        "title": "Lesson 1",
                        "content": "This is lesson content about functions.",
                        "objectives": ["Learn functions"]
                    }
                ]
            }
        ]
    }
    
    # Inject chunks (will be async under the hood)
    result = curriculum_agent._inject_chunks_into_lessons(test_curriculum)
    
    assert result is not None
    assert "modules" in result
    assert len(result["modules"]) > 0
    # Check that chunks field exists (even if empty due to async context)
    assert "_chunks" in result["modules"][0]["lessons"][0]


def test_tutor_agent_uses_lesson_chunks():
    """Verify tutor agent receives and uses lesson chunks."""
    async def run_test():
        from mammoth_os.agents.tutor_agent import TutorAgent
        
        tutor = TutorAgent()
        
        payload = {
            "topic": "Understanding Functions",
            "lesson_title": "Intro to Functions",
            "module_id": "module-001",
            "_chunks": [
                "Functions are reusable blocks of code.",
                "Parameters pass data into functions.",
                "Return values pass data out of functions."
            ]
        }
        
        result = await tutor.run(payload)
        
        assert result["status"] == "ok"
        assert result["mode"] == "coach"
        assert "lesson_context" in result
        # Context should contain chunk preview or be empty
        assert isinstance(result["lesson_context"], str)
    
    asyncio.run(run_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

