"""
chunking.py
Implements recursive character splitting for breaking extracted page/section
text into smaller, semantically coherent, overlapping chunks.

Why recursive splitting instead of a flat sliding window:
A naive sliding window cuts text at fixed character offsets regardless of
what's there, which can split a sentence (or even a word) right down the
middle. Recursive splitting tries the "nicest" separator first (paragraph
breaks), and only falls back to a smaller separator (line break, then
space, then raw characters) if a piece is still too big after splitting
on the nicer one. This keeps chunks aligned with natural text boundaries
whenever possible.
"""

# Ordered from "nicest" cut point to "last resort" cut point.
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _split_text(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """
    Recursively splits `text` using the first separator in `separators`
    that actually breaks it into pieces. Any resulting piece still longer
    than chunk_size gets recursively split again with the next separator
    down the list.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    if not separators:
        # Last resort: hard-cut at chunk_size with no separator logic left.
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep = separators[0]
    remaining_seps = separators[1:]

    if sep == "":
        pieces = list(text)
    else:
        pieces = text.split(sep)

    # Greedily pack split pieces back together up to chunk_size,
    # so we don't end up with tons of tiny fragments.
    merged_pieces = []
    current = ""
    for piece in pieces:
        candidate = (current + sep + piece) if current else piece
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                merged_pieces.append(current)
            # If the piece itself is still too large, recurse into it
            # with the next, finer-grained separator.
            if len(piece) > chunk_size:
                merged_pieces.extend(_split_text(piece, chunk_size, remaining_seps))
                current = ""
            else:
                current = piece
    if current:
        merged_pieces.append(current)

    return [p for p in merged_pieces if p.strip()]


def _apply_overlap(pieces: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    Adds character-level overlap between consecutive chunk pieces.
    This ensures information sitting near a chunk boundary isn't lost
    entirely from context - it appears (at least partially) in both
    the preceding and following chunk.
    """
    if chunk_overlap <= 0 or len(pieces) <= 1:
        return pieces

    overlapped = [pieces[0]]
    for i in range(1, len(pieces)):
        prev_tail = pieces[i - 1][-chunk_overlap:]
        combined = prev_tail + pieces[i]
        # Keep within chunk_size bounds even after adding overlap.
        overlapped.append(combined[:chunk_size + chunk_overlap])
    return overlapped


def chunk_extracted_pages(
    pages: list[dict],
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> list[dict]:
    """
    Splits page-level extracted documents into smaller, overlapping chunks
    using recursive character splitting. Source metadata (filename, page
    number) is carried over from the parent page into every chunk derived
    from it, which is what powers citation generation at query time.
    """
    all_chunks = []

    for page in pages:
        text = page["text"]
        metadata = page["metadata"]

        raw_pieces = _split_text(text, chunk_size, SEPARATORS)
        final_pieces = _apply_overlap(raw_pieces, chunk_size, chunk_overlap)

        for idx, chunk_text in enumerate(final_pieces):
            all_chunks.append({
                "text": chunk_text,
                "metadata": {
                    "source": metadata["source"],
                    "page": metadata["page"],
                    "chunk_index": idx
                }
            })

    return all_chunks
