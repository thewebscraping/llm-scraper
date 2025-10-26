from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# This regex is used to count words in a unicode-aware way.
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def estimate_tokens_from_text(text: str, avg_token_per_word: float = 1.33) -> int:
    """
    Provides a fast, heuristic-based estimate of token count for a given text.

    This method is a safe and quick way to approximate tokenization without needing
    to load a full tokenizer. It's based on the average number of tokens per word,
    which is a reasonable approximation for many subword tokenization strategies.

    Args:
        text: The input string to estimate tokens for.
        avg_token_per_word: The average token-to-word ratio. The default of 1.33
                            is a good starting point for many models.

    Returns:
        An integer representing the estimated number of tokens.
    """
    if not text:
        return 0
    words = len(_WORD_RE.findall(text))
    return int(math.ceil(words * avg_token_per_word))


class ArticleChunk(BaseModel):
    """
    Represents a single chunk of an article's content.

    This model holds the chunk's text and associated metadata, such as its length,
    word count, and estimated token count. It can also store an embedding vector
    if one is computed for the chunk.
    """

    index: int = Field(default=1, ge=0, description="The sequential index of the chunk.")
    content: str = Field(default="", description="The cleaned text content of the chunk.")
    char_length: int = Field(default=0, description="The length of the content in characters.")
    word_count: int = Field(default=0, description="The number of words in the content.")
    token_estimate: int = Field(default=0, description="An estimated token count for the content.")
    embedding: Optional[List[float]] = Field(default=None, description="The embedding vector for the chunk, if computed.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Any additional metadata associated with the chunk.")

    @classmethod
    def from_text(cls, index: int, text: str) -> "ArticleChunk":
        """
        A factory method to create an ArticleChunk from a raw text string.

        It automatically calculates the character length, word count, and estimated
        token count for the provided text.
        """
        word_count = len(_WORD_RE.findall(text))
        return cls(
            index=index,
            content=text,
            char_length=len(text),
            word_count=word_count,
            token_estimate=estimate_tokens_from_text(text),
        )


def chunk_text_by_char(
    text: str,
    max_chars: int = 2000,
    overlap_chars: int = 200,
) -> List[ArticleChunk]:
    """
    Splits a text into chunks based on a maximum character length.

    This method uses a sliding window approach to create chunks of a specified
    character length with a defined overlap between them.

    Args:
        text: The text to be chunked.
        max_chars: The maximum number of characters for each chunk.
        overlap_chars: The number of characters to overlap between consecutive chunks.

    Returns:
        A list of ArticleChunk objects.
    """
    if not text:
        return []

    chunks: List[ArticleChunk] = []
    start_pos = 0
    index = 0
    text_len = len(text)

    while start_pos < text_len:
        end_pos = min(text_len, start_pos + max_chars)
        chunk_text = text[start_pos:end_pos].strip()

        if chunk_text:
            chunks.append(ArticleChunk.from_text(index=index, text=chunk_text))
            index += 1

        # Move the start position for the next chunk
        next_start = end_pos - overlap_chars
        if next_start <= start_pos:
            # If overlap is too large or chunks are too small, prevent infinite loops
            next_start = end_pos
        start_pos = next_start

    return chunks


def chunk_text_by_token_estimate(
    text: str,
    max_tokens: int = 800,
    overlap_tokens: int = 64,
    sentence_split: bool = True,
) -> List[ArticleChunk]:
    """
    Splits a text into chunks based on an estimated maximum token count.

    This is generally safer for LLM context windows than character-based chunking.
    It can split by sentences (default) or by words to create chunks that are
    less likely to exceed token limits. It also handles cases where a single
    sentence or word is longer than the max_tokens limit.

    Args:
        text: The text to be chunked.
        max_tokens: The estimated maximum number of tokens for each chunk.
        overlap_tokens: The estimated number of tokens to overlap between chunks.
        sentence_split: If True, splits the text by sentences. If False, splits by words.

    Returns:
        A list of ArticleChunk objects.
    """
    if not text:
        return []

    if sentence_split:
        delimiters = re.split(r'(?<=[.?!])\s+(?=[A-Z0-9"\'“‘])', text)
    else:
        delimiters = text.split()

    chunks: List[ArticleChunk] = []
    current_buffer: List[str] = []
    current_tokens = 0
    chunk_index = 0

    def flush_buffer(buf: List[str], idx: int) -> Optional[ArticleChunk]:
        """Helper to create a chunk from the current buffer."""
        chunk_content = " ".join(buf).strip()
        if not chunk_content:
            return None
        return ArticleChunk.from_text(index=idx, text=chunk_content)

    for item in delimiters:
        item_tokens = estimate_tokens_from_text(item)

        # Handle items that are themselves larger than the max token limit
        if item_tokens > max_tokens:
            # First, flush whatever is in the buffer
            if current_buffer:
                new_chunk = flush_buffer(current_buffer, chunk_index)
                if new_chunk:
                    chunks.append(new_chunk)
                    chunk_index += 1
                current_buffer = []
                current_tokens = 0

            # Now, split the oversized item into smaller pieces
            # We'll do this by character count as a proxy for tokens
            avg_chars_per_token = len(item) / item_tokens
            sub_chunk_max_len = int(max_tokens * avg_chars_per_token)
            
            for i in range(0, len(item), sub_chunk_max_len):
                sub_chunk_text = item[i:i + sub_chunk_max_len]
                new_chunk = ArticleChunk.from_text(index=chunk_index, text=sub_chunk_text)
                chunks.append(new_chunk)
                chunk_index += 1
            continue

        # Standard logic: if adding the next item exceeds the limit, flush the buffer
        if current_tokens + item_tokens > max_tokens and current_buffer:
            new_chunk = flush_buffer(current_buffer, chunk_index)
            if new_chunk:
                chunks.append(new_chunk)
                chunk_index += 1

            # Handle overlap
            if overlap_tokens > 0:
                overlap_word_count = int(overlap_tokens / 1.33)
                words_in_buffer = " ".join(current_buffer).split()
                overlap_buffer = words_in_buffer[-overlap_word_count:] if overlap_word_count > 0 else []
                current_buffer = overlap_buffer[:]
                current_tokens = estimate_tokens_from_text(" ".join(current_buffer))
            else:
                current_buffer = []
                current_tokens = 0

        current_buffer.append(item)
        current_tokens += item_tokens

    # Flush any remaining content in the buffer
    final_chunk = flush_buffer(current_buffer, chunk_index)
    if final_chunk:
        chunks.append(final_chunk)

    return chunks
