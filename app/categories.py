"""Document categories, default keyword weights, image prompts and folder names."""

CATEGORY_GROUPS = {
    "Financial":   ["invoice", "credit_note", "debit_note", "receipt"],
    "Procurement": ["purchase_order", "quotation", "vendor_agreement"],
    "Identity":    ["aadhaar", "pan", "passport", "driving_licence"],
    "Banking":     ["bank_statement", "cancelled_cheque"],
    "Logistics":   ["delivery_challan", "eway_bill", "lorry_receipt"],
    "Supporting":  ["address_proof", "payment_proof", "declaration", "others"],
}
LABELS = [l for group in CATEGORY_GROUPS.values() for l in group]
SYSTEM_LABELS = ["BLANK_PAGE", "UNKNOWN", "ERROR"]

DISPLAY = {
    "invoice": "Invoice", "credit_note": "Credit Note", "debit_note": "Debit Note", "receipt": "Receipt",
    "purchase_order": "Purchase Order", "quotation": "Quotation", "vendor_agreement": "Vendor Agreement",
    "aadhaar": "Aadhaar", "pan": "PAN", "passport": "Passport", "driving_licence": "Driving Licence",
    "bank_statement": "Bank Statement", "cancelled_cheque": "Cancelled Cheque",
    "delivery_challan": "Delivery Challan", "eway_bill": "E-Way Bill", "lorry_receipt": "Lorry Receipt",
    "address_proof": "Address Proof", "payment_proof": "Payment Proof", "declaration": "Declaration", "others": "Others",
    "BLANK_PAGE": "Blank Page", "UNKNOWN": "Unknown", "ERROR": "Error",
}

# label -> {"scale": points needed for evidence 1.0, "keywords": {phrase: weight}}
DEFAULT_KEYWORDS = {
    "invoice": {"scale": 10, "keywords": {
        "tax invoice": 5, "invoice number": 5, "invoice no": 5, "invoice date": 4, "gstin": 3, "bill to": 2,
        "subtotal": 2, "sales tax": 2, "total amount": 2, "amount payable": 3, "taxable value": 3,
        "unit price": 1, "quantity": 1, "total": 1, "invoice": 1, "balance due": 2, "total due": 2}},
    "credit_note": {"scale": 10, "keywords": {
        "credit note": 6, "credit note no": 5, "credit note number": 5, "credit memo": 4, "against invoice": 3,
        "original invoice": 2, "reason for credit": 3, "credit amount": 2}},
    "debit_note": {"scale": 10, "keywords": {
        "debit note": 6, "debit note no": 5, "debit note number": 5, "debit memo": 4, "against invoice": 3,
        "original invoice": 2, "reason for debit": 3, "debit amount": 2}},
    "receipt": {"scale": 10, "keywords": {
        "payment receipt": 5, "receipt no": 5, "receipt number": 5, "money receipt": 5, "cash receipt": 4,
        "received with thanks": 5, "received from": 3, "amount received": 4, "receipt": 2, "thank you visit again": 3,
        "paid by": 2, "total": 1, "cashier": 2}},

    "purchase_order": {"scale": 10, "keywords": {
        "purchase order": 5, "purchase order number": 5, "purchase order no": 5, "po number": 5, "po no": 5,
        "order date": 4, "ordered quantity": 3, "supplier": 2, "unit price": 2, "delivery date": 2, "purchase": 1,
        "invoice": 0.2}},
    "quotation": {"scale": 10, "keywords": {
        "quotation": 6, "quotation no": 5, "quote no": 5, "quote number": 5, "quotation date": 4, "valid until": 3,
        "validity": 3, "quoted price": 3, "estimated cost": 3, "estimate": 2, "proforma": 2, "prepared for": 2,
        "offer valid": 3}},
    "vendor_agreement": {"scale": 12, "keywords": {
        "vendor agreement": 6, "supplier agreement": 5, "this agreement": 4, "agreement": 2, "party of the first part": 4,
        "second party": 3, "governing law": 3, "jurisdiction": 2, "term of agreement": 3, "indemnity": 3,
        "termination": 2, "in witness whereof": 4, "terms and conditions": 2, "vendor": 2, "confidentiality": 2}},

    "aadhaar": {"scale": 8, "keywords": {
        "unique identification authority": 5, "uidai": 5, "aadhaar": 4, "your aadhaar no": 5, "government of india": 2,
        "enrolment number": 3, "enrolment no": 3, "year of birth": 2, "vid": 2, "aam aadmi": 3}},
    "pan": {"scale": 8, "keywords": {
        "permanent account number": 5, "income tax department": 4, "pan card": 5, "govt of india": 2,
        "father name": 2, "fathers name": 2}},
    "passport": {"scale": 10, "keywords": {
        "passport": 5, "passport no": 5, "passport number": 5, "republic of india": 3, "nationality": 2,
        "place of birth": 2, "place of issue": 3, "date of expiry": 3, "date of issue": 1, "given names": 2,
        "surname": 1, "p ind": 4}},
    "driving_licence": {"scale": 10, "keywords": {
        "driving licence": 6, "driving license": 6, "dl no": 5, "licence no": 4, "license no": 4, "class of vehicle": 4,
        "form of licence": 3, "valid till": 2, "blood group": 2, "motor vehicles act": 3, "rto": 2, "cov": 2,
        "authorisation to drive": 4}},

    "bank_statement": {"scale": 8, "keywords": {
        "bank statement": 5, "statement of account": 5, "account statement": 5, "mini statement": 5,
        "statement of transactions": 5, "opening balance": 4, "closing balance": 4, "transaction date": 3,
        "account number": 3, "statement period": 3, "narration": 3, "running balance": 3, "withdrawal": 2,
        "deposit": 2, "available balance": 3, "value date": 2}},
    "cancelled_cheque": {"scale": 8, "keywords": {
        "cheque number": 5, "cheque": 3, "cancelled": 4, "payable at": 3, "or bearer": 3, "or order": 3,
        "a c payee": 4, "account payee": 4, "pay": 2, "pay to": 3, "rupees": 2, "micr": 4, "ifsc": 3,
        "please sign above": 3, "not valid after": 2, "counterfoil": 2}},

    "delivery_challan": {"scale": 10, "keywords": {
        "delivery challan": 5, "challan number": 5, "challan no": 5, "delivery note": 5, "challan": 3,
        "goods dispatched": 4, "goods dispatched via": 4, "quantity dispatched": 4, "received the above goods": 4,
        "received by": 3, "delivery date": 2, "dispatch date": 2, "vehicle number": 2, "vehicle no": 2,
        "transporter": 2, "no of packages": 2, "receivers signature": 2}},
    "eway_bill": {"scale": 12, "keywords": {
        "e way bill": 6, "eway bill": 6, "e way bill no": 5, "eway bill no": 5, "ewb no": 5, "ewaybill": 5,
        "transporter id": 3, "valid upto": 3, "from gstin": 3, "to gstin": 3, "approximate distance": 3,
        "supply type": 2, "transaction type": 2, "hsn code": 2}},
    "lorry_receipt": {"scale": 10, "keywords": {
        "lorry receipt": 6, "consignment note": 6, "lr no": 5, "lr number": 5, "gc note": 4, "consignor": 4,
        "consignee": 3, "goods consigned": 3, "freight": 2, "weight charged": 3, "booked from": 3, "booked to": 3,
        "at owners risk": 3, "truck no": 3, "no of packages": 2}},

    "address_proof": {"scale": 10, "keywords": {
        "address proof": 5, "proof of address": 5, "utility bill": 4, "electricity bill": 4, "bill of supply": 3,
        "water bill": 4, "gas bill": 4, "telephone bill": 3, "consumer no": 3, "consumer name": 2, "billing period": 2,
        "units consumed": 3, "meter": 2, "rent agreement": 4, "residential address": 3, "service address": 3,
        "amount payable": 1}},
    "payment_proof": {"scale": 12, "keywords": {
        "payment proof": 5, "payment confirmation": 5, "payment successful": 5, "transaction successful": 4,
        "paid successfully": 4, "transaction id": 4, "utr no": 5, "utr number": 5, "upi ref": 4, "payment status": 3,
        "debited from": 3, "credited to": 3, "beneficiary": 3, "remitter": 3, "amount paid": 3, "payment date": 2,
        "google pay": 3, "phonepe": 3, "paytm": 3, "upi": 1, "neft": 1, "rtgs": 1, "imps": 1}},
    "declaration": {"scale": 10, "keywords": {
        "declaration": 6, "i hereby declare": 6, "hereby declare": 5, "self declaration": 6, "affidavit": 4,
        "solemnly affirm": 4, "true and correct": 4, "to the best of my knowledge": 4, "undertaking": 3,
        "i undertake": 3, "deponent": 3, "signature of declarant": 4}},
    "others": {"scale": 10, "keywords": {}},
}

# Zero-shot text prompts for the Nutrient image model (one per label, incl. BLANK_PAGE)
DEFAULT_IMAGE_PROMPTS = {
    "invoice": "a tax invoice with itemised charges and totals",
    "credit_note": "a credit note issued against an invoice",
    "debit_note": "a debit note issued against an invoice",
    "receipt": "a payment receipt",
    "purchase_order": "a purchase order document",
    "quotation": "a price quotation document",
    "vendor_agreement": "a legal vendor agreement contract",
    "aadhaar": "Indian Aadhaar identity document",
    "pan": "Indian PAN card identity document",
    "passport": "an Indian passport page",
    "driving_licence": "an Indian driving licence card",
    "bank_statement": "bank account statement with a transactions table",
    "cancelled_cheque": "a bank cheque",
    "delivery_challan": "a delivery challan goods dispatch document",
    "eway_bill": "an e-way bill for transport of goods",
    "lorry_receipt": "a lorry receipt consignment note",
    "address_proof": "a utility bill used as address proof",
    "payment_proof": "a payment confirmation slip or screenshot",
    "declaration": "a signed declaration or affidavit",
    "others": "some other miscellaneous document",
    "BLANK_PAGE": "a blank empty white page",
}

DEFAULT_FOLDERS = {l: l for l in LABELS}
DEFAULT_FOLDERS.update({"BLANK_PAGE": "blank_pages", "UNKNOWN": "unknown", "ERROR": "errors"})

# regexes (applied to normalised text) removed BEFORE keyword matching
DEFAULT_IGNORE_PHRASES = [r"not an? (tax )?invoice", r"this is not an invoice"]
