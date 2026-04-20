"""
Traditional coordinate-based table parser for invoice line items.
Works on the OCR word list from Google Cloud Vision / PaddleOCR.
No ML required — pure spatial heuristics.
"""

from __future__ import annotations

_HEADER_KEYWORDS = {
    "description": ["description", "particulars", "item", "product", "goods", "details"],
    "hsn_sac":     ["hsn", "sac", "hsn/sac", "hsn code"],
    "quantity":    ["qty", "quantity", "units", "nos"],
    "unit":        ["unit", "uom", "u/m"],
    "rate":        ["rate", "price", "unit price", "mrp"],
    "amount":      ["amount", "total", "value", "amt"],
}

_Y_ROW_TOLERANCE = 12  # pixels — words within this Y range are on the same row


def _cluster_into_rows(words: list[dict]) -> list[list[dict]]:
    """
    Group OCR words into rows by Y coordinate.
    Each word dict must have: text, x_min, y_min, x_max, y_max.
    """
    if not words:
        return []

    sorted_words = sorted(words, key=lambda w: w["y_min"])
    rows: list[list[dict]] = []
    current_row: list[dict] = [sorted_words[0]]
    current_y = sorted_words[0]["y_min"]

    for word in sorted_words[1:]:
        if abs(word["y_min"] - current_y) <= _Y_ROW_TOLERANCE:
            current_row.append(word)
        else:
            rows.append(sorted(current_row, key=lambda w: w["x_min"]))
            current_row = [word]
            current_y = word["y_min"]

    if current_row:
        rows.append(sorted(current_row, key=lambda w: w["x_min"]))

    return rows


def _find_header_row(rows: list[list[dict]]) -> int | None:
    """
    Find the row index that contains column header keywords.
    Returns None if no header row found.
    """
    all_keywords = [kw for kws in _HEADER_KEYWORDS.values() for kw in kws]
    for idx, row in enumerate(rows):
        row_text = " ".join(w["text"].lower() for w in row)
        if sum(1 for kw in all_keywords if kw in row_text) >= 2:
            return idx
    return None


def _build_column_map(header_row: list[dict]) -> dict[str, tuple[int, int]]:
    """
    Map column names to their (x_min, x_max) ranges based on header word positions.
    Returns dict like: {"description": (0, 300), "hsn_sac": (300, 380), ...}
    """
    column_map: dict[str, tuple[int, int]] = {}

    for col_name, keywords in _HEADER_KEYWORDS.items():
        for word in header_row:
            if word["text"].lower() in keywords:
                column_map[col_name] = (word["x_min"], word["x_max"])
                break

    # Extend each column's x_max to the start of the next column
    sorted_cols = sorted(column_map.items(), key=lambda c: c[1][0])
    for i, (col_name, (x_min, x_max)) in enumerate(sorted_cols):
        if i + 1 < len(sorted_cols):
            next_x_min = sorted_cols[i + 1][1][0]
            column_map[col_name] = (x_min, next_x_min - 1)
        else:
            column_map[col_name] = (x_min, 9999)

    return column_map


def _assign_word_to_column(word: dict, column_map: dict[str, tuple[int, int]]) -> str | None:
    """Find which column a word's X position falls into."""
    word_x_center = (word["x_min"] + word["x_max"]) // 2
    for col_name, (x_min, x_max) in column_map.items():
        if x_min <= word_x_center <= x_max:
            return col_name
    return None


def _row_to_line_item(row: list[dict], column_map: dict[str, tuple[int, int]]) -> dict:
    """Convert a data row into a line item dict."""
    item: dict[str, list[str]] = {col: [] for col in _HEADER_KEYWORDS}

    for word in row:
        col = _assign_word_to_column(word, column_map)
        if col:
            item[col].append(word["text"])

    return {
        "description": " ".join(item["description"]),
        "hsn_sac":     " ".join(item["hsn_sac"]),
        "quantity":    " ".join(item["quantity"]),
        "unit":        " ".join(item["unit"]),
        "rate":        " ".join(item["rate"]),
        "amount":      " ".join(item["amount"]),
    }


def ocr_words_to_flat(ocr_words: list[dict]) -> list[dict]:
    """
    Convert OCR words from the API schema to the flat format used by the parser.
    Input OCR word schema: { text, bounding_box: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]] }
    Output flat schema:    { text, x_min, y_min, x_max, y_max }
    """
    flat = []
    for w in ocr_words:
        bb = w["bounding_box"]
        xs = [p[0] for p in bb]
        ys = [p[1] for p in bb]
        flat.append({
            "text": w["text"],
            "x_min": min(xs), "y_min": min(ys),
            "x_max": max(xs), "y_max": max(ys),
        })
    return flat


def parse_line_items(ocr_words: list[dict]) -> list[dict]:
    """
    Entry point. Takes raw OCR words and returns structured line items.
    Returns empty list if no table structure is detected.
    """
    flat_words = ocr_words_to_flat(ocr_words)
    rows = _cluster_into_rows(flat_words)

    header_idx = _find_header_row(rows)
    if header_idx is None:
        return []

    column_map = _build_column_map(rows[header_idx])
    if not column_map:
        return []

    line_items = []
    for row in rows[header_idx + 1:]:
        item = _row_to_line_item(row, column_map)
        # Skip empty rows and subtotal/total rows
        if not item["description"] and not item["amount"]:
            continue
        if any(kw in item["description"].lower() for kw in ["total", "subtotal", "grand"]):
            break
        line_items.append(item)

    return line_items
