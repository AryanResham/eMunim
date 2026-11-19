"""Conservative, geometry-checked reconstruction of OCR-split IDs and dates.

Uses only recognized characters and their boxes. No field values or labels.
"""
import re

VERSION='ocr-compounds-v1'
_IDENTIFIER=re.compile(r'[A-Za-z]{1,8}/\d{2,4}-\d{2,4}/\d{1,12}')
_DATE=re.compile(r'(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}-[A-Za-z]{3,9}-\d{2,4})')


def _bounds(box):
    return [min(p[0] for p in box),min(p[1] for p in box),max(p[0] for p in box),max(p[1] for p in box)]


def _neighbors(a,b):
    a,b=_bounds(a),_bounds(b)
    height=max(1,min(a[3]-a[1],b[3]-b[1]))
    overlap=max(0,min(a[3],b[3])-max(a[1],b[1]))
    gap=b[0]-a[2]
    return overlap/height>=.5 and -height*.5<=gap<=height*.9


def normalize_compounds(words,boxes):
    if len(words)!=len(boxes):raise ValueError('Words and boxes must align')
    out_words=[];out_boxes=[];sources=[];i=0
    while i<len(words):
        if _IDENTIFIER.fullmatch(words[i]) or _DATE.fullmatch(words[i]):
            out_words.append(words[i]);out_boxes.append(boxes[i]);sources.append([i]);i+=1
            continue
        longest=None
        text=words[i]
        for end in range(i+1,min(len(words),i+11)):
            if not _neighbors(boxes[end-1],boxes[end]):break
            text+=words[end]
            if _IDENTIFIER.fullmatch(text) or _DATE.fullmatch(text):longest=(end+1,text)
        if longest:
            end,text=longest
            bounds=[_bounds(box) for box in boxes[i:end]]
            x0=min(b[0] for b in bounds);y0=min(b[1] for b in bounds)
            x1=max(b[2] for b in bounds);y1=max(b[3] for b in bounds)
            out_words.append(text);out_boxes.append([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])
            sources.append(list(range(i,end)));i=end
        else:
            out_words.append(words[i]);out_boxes.append(boxes[i]);sources.append([i]);i+=1
    return out_words,out_boxes,sources


def assemble_field_text(key,tokens):
    """Restore separators only; never invent missing identifier characters."""
    text=' '.join(tokens)
    identifiers={'invoice_no','bill_no','receipt_no','credit_note_no','debit_note_no','original_invoice_no','po_number'}
    if key in identifiers or key.endswith('_date'):
        text=re.sub(r'\s*([/-])\s*',r'\1',text)
    return text
