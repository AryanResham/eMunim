# Annotation and study contract

Use single-page English GST invoices first. Store only documents you can use.
Manually transcribe values exactly. Include all schema keys; use JSON null for
genuinely absent fields. Track unreadable/ambiguous documents separately and
resolve/exclude under a declared protocol before evaluating; null is not a
substitute for unknown truth. Independently verify a subset.

Create a JSON manifest with a documents list. Each entry has id, image
(relative to manifest), group (vendor/template family), split (development
or test), doc_type and fields. Optional ocr points to a saved production
OCRResult JSON for the exact normalized image (boxes must use those pixels).
Do not reuse test vendors/templates or duplicate images across splits.

GST schema keys: invoice_no, invoice_date, vendor_name, vendor_gstin, buyer_name,
buyer_gstin, taxable_amount, cgst_amount, sgst_amount, igst_amount, total_amount,
due_date, po_number. Other types derive from backend field_mapper label sets.
All values are strings or null. Manually verify annotations, including absences.
GT values never enter hosted prompts or extraction decisions.

Before final testing freeze provider/model/prompt, checkpoint hashes, normalization,
rules, fallback policy and review policy. Calibrate on development data only.
The policy example is NOT a calibrated policy.

Any wrong, missing applicable or extra field makes an invoice incorrect.
Operational failures count against the cohort. Raw extraction F1 is unchanged
by review policies. Hosted corrections are upstream extraction changes, and
human corrections are a separate outcome.

Do not mix historical SROIE/synthetic/real metrics or average OCR confidence with
measured OCR accuracy. A small independent real set warrants pilot-study claims.
