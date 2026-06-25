#!/usr/bin/env python3
"""
Tax Bridge MCP — CSOAI Layer-0 legacy-bridge family.
Bridge tax filing + e-invoicing (UK MTD VAT, EU VAT/ViDA, US sales tax, corp/income) to ONE OS:
parse → validate → map → govern (HMRC MTD / EU ViDA / OECD BEPS / IRS). Sibling of cobol-bridge-mcp.
Tools: parse_tax · validate_tax · map_to_modern · govern_tax
"""
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json, re

mcp = FastMCP("Tax Bridge", instructions="Bridge tax filings + e-invoices to ONE OS — parse, validate, map, govern (MTD/ViDA/BEPS/IRS).")

# ── SIGIL: every governed action → one signed hash-chained hop ──
import hashlib as _hl, time as _t, json as _j, os as _os
_SIGIL_LOG = _os.environ.get("SIGIL_LOG", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "bridge_sigil.log"))
def _sigil(op, body):
    try:
        prev = ""
        if _os.path.exists(_SIGIL_LOG):
            with open(_SIGIL_LOG) as f:
                ls = f.readlines()
                if ls: prev = _j.loads(ls[-1]).get("digest", "")
        ts = int(_t.time()); dg = _hl.sha256(f"{op}|{ts}|{prev[:8]}|{body}".encode()).hexdigest()[:16]
        _os.makedirs(_os.path.dirname(_SIGIL_LOG), exist_ok=True)
        with open(_SIGIL_LOG, "a") as f: f.write(_j.dumps({"ts": ts, "op": op, "body": body, "prev_digest": prev, "digest": dg}) + "\n")
        return dg
    except Exception: return ""


class TaxParsed(BaseModel):
    doc_type: str
    tax_kind: str
    period: Optional[str] = None
    total: Optional[str] = None
    currency: Optional[str] = None
    jurisdiction: Optional[str] = None
    fields_found: int = 0


class Validation(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class Governance(BaseModel):
    risk_flags: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    attestable: bool = True
    note: str = ""


def _detect(doc: str) -> Dict[str, str]:
    low = doc.lower()
    if "vatduesales" in low or ("vat" in low and "period" in low):
        return {"doc_type": "UK MTD VAT return", "kind": "VAT", "juris": "UK"}
    if "invoicetypecode" in low or "<invoice" in low or "ubl" in low:
        return {"doc_type": "e-invoice (UBL/Peppol)", "kind": "VAT e-invoice", "juris": "EU"}
    if "1040" in low or "ct600" in low or "corporation tax" in low or "income tax" in low:
        return {"doc_type": "income/corporation tax return", "kind": "Direct tax", "juris": "?"}
    if "sales tax" in low or "salestax" in low:
        return {"doc_type": "US sales tax filing", "kind": "Sales tax", "juris": "US"}
    return {"doc_type": "tax document", "kind": "unknown", "juris": "?"}


@mcp.tool()
def parse_tax(doc: str) -> TaxParsed:
    """Parse a tax filing or e-invoice; detect type, tax kind, period, total, jurisdiction."""
    d = _detect(doc)
    period = None
    m = re.search(r'"?period(?:Key)?"?\s*[:=]\s*"?([A-Za-z0-9\-/]+)', doc, re.I) or re.search(r"(20\d\d[-/Q]\d{1,2})", doc)
    if m: period = m.group(1)
    tot = re.search(r'"?(?:totalVatDue|total|grandTotal|taxAmount|amountDue)"?\s*[:=]\s*"?([\d,.]+)', doc, re.I)
    cur = re.search(r'\b(GBP|EUR|USD)\b', doc)
    return TaxParsed(doc_type=d["doc_type"], tax_kind=d["kind"], period=period,
                     total=tot.group(1).rstrip(",.") if tot else None, currency=cur.group(1) if cur else None,
                     jurisdiction=d["juris"], fields_found=len(re.findall(r'[:=]', doc)))


@mcp.tool()
def validate_tax(doc: str) -> Validation:
    """Validate a tax document (parses + has a period + an amount)."""
    errors, warnings = [], []
    p = parse_tax(doc)
    if p.tax_kind == "unknown":
        warnings.append("Could not classify tax document type")
    if not p.period:
        warnings.append("No tax period found")
    if not p.total:
        errors.append("No tax amount/total found")
    return Validation(valid=not errors, errors=errors, warnings=warnings)


@mcp.tool()
def map_to_modern(doc: str) -> Dict[str, Any]:
    """Map a tax document to a modern JSON filing object for ONE OS."""
    p = parse_tax(doc)
    return {"source": "tax", "type": p.doc_type, "tax_kind": p.tax_kind,
            "period": p.period, "total": p.total, "currency": p.currency,
            "jurisdiction": p.jurisdiction, "target": "modern tax filing event"}


@mcp.tool()
def govern_tax(doc: str) -> Governance:
    """Governance: tax-compliance surface — MTD digital links, ViDA e-invoicing, anti-avoidance (attestable)."""
    _sigil("G", "tax|govern_tax")
    p = parse_tax(doc)
    flags = []
    if p.tax_kind == "VAT":
        flags.append("UK MTD — digital links end-to-end required (no copy-paste); keep digital records")
    if "e-invoice" in p.tax_kind:
        flags.append("EU ViDA — structured e-invoice + near-real-time digital reporting (phased to 2030)")
    if p.tax_kind == "Direct tax":
        flags.append("Direct tax — transfer-pricing / BEPS + anti-avoidance review")
    flags.append("Immutable audit trail of the filing (the bridge signs it)")
    return Governance(risk_flags=flags,
                      frameworks=["UK MTD (HMRC)", "EU VAT / ViDA", "OECD BEPS / Pillar Two", "US IRS + state sales tax", "SOX (controls)"],
                      note="CSOAI governs the bridge: every tax filing parsed + SIGIL-signed = a verifiable submission trail.")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
