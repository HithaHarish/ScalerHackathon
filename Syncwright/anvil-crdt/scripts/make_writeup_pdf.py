from __future__ import annotations

from pathlib import Path


PAGES = [
    """Page 1: Lattice Choices and CRDT Type Mapping

Rows use an observed-remove set. Inserts add peer/clock tags; deletes remove only observed tags, so concurrent inserts survive. Cells use MV-registers per column, preserving all non-dominated concurrent writes while exposing deterministic reads. Primary keys are immutable row ids. Unique email uses post-hoc escrow arbitration with recoverable losers. Foreign keys use a uniform tombstone policy. Secondary indexes are derived views. Causal order uses bounded vector clocks with one entry per distinct writer, not per write.
""",
    """Page 2: Protocol Designs

Uniqueness resolution groups rows by unique value after merge. The winner is chosen deterministically by minimum clock sum, writer id, and row id. Losers are marked non-live and copied to _conflict_log with full JSON row data. For foreign keys, deleting a parent creates a tombstone containing table id, row id, delete clock, deleting peer, and merged row data. Children remain queryable; joins return NULL parent fields for tombstoned parents. Pairwise sync merges CRDT state, resolves conflicts, and rebuilds indexes.
""",
    """Page 3: Metadata Growth and Q&A Preparation

Clock metadata is O(distinct writers) because each clock is a peer_id to logical_time map. Tombstones are O(deletes), and conflict logs are O(unique violations). After quiescence, acknowledged clock entries can be compacted to the global minimum. Covered edge cases include tombstone resurrection, empty peer sync, self-sync, idempotent repeated sync, out-of-order tombstones, uniqueness conflicts under partition, and sync ordering invariance.
""",
]


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def stream_for(page: str) -> str:
    lines = ["BT", "/F1 11 Tf", "72 760 Td", "14 TL"]
    for raw in page.splitlines():
        line = raw[:92]
        lines.append(f"({pdf_escape(line)}) Tj")
        lines.append("T*")
    lines.append("ET")
    return "\n".join(lines)


def build_pdf() -> bytes:
    objects: list[str] = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R 5 0 R 7 0 R] /Count 3 >>",
    ]
    for index, page in enumerate(PAGES):
        page_obj = 3 + index * 2
        content_obj = page_obj + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> "
            f"/Contents {content_obj} 0 R >>"
        )
        stream = stream_for(page)
        objects.append(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
    xref_at = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode("latin-1")
    )
    return bytes(output)


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "writeup" / "architecture.pdf"
    out.write_bytes(build_pdf())
    print(out)

