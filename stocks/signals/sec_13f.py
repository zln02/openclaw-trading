"""SEC 13F position change analyzer (Phase 16)."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


@dataclass
class HoldingChange:
    symbol: str
    fund_name: str
    change_type: str
    shares: int
    prev_shares: int
    curr_shares: int

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_symbol(row: dict) -> str:
    sym = str(row.get("symbol") or row.get("ticker") or row.get("cusip") or "").upper().strip()
    return sym


def detect_change_type(prev_shares: int, curr_shares: int) -> str:
    if prev_shares <= 0 and curr_shares > 0:
        return "NEW"
    if prev_shares > 0 and curr_shares <= 0:
        return "EXIT"
    if curr_shares > prev_shares:
        return "ADD"
    if curr_shares < prev_shares:
        return "REDUCE"
    return "HOLD"


def compare_13f_holdings(prev_rows: list[dict], curr_rows: list[dict], fund_name: str) -> list[dict]:
    prev_map = {_normalize_symbol(r): _safe_int(r.get("shares"), 0) for r in prev_rows if _normalize_symbol(r)}
    curr_map = {_normalize_symbol(r): _safe_int(r.get("shares"), 0) for r in curr_rows if _normalize_symbol(r)}

    symbols = sorted(set(prev_map.keys()) | set(curr_map.keys()))
    out: list[dict] = []

    for sym in symbols:
        prev_sh = prev_map.get(sym, 0)
        curr_sh = curr_map.get(sym, 0)
        typ = detect_change_type(prev_sh, curr_sh)
        if typ == "HOLD":
            continue

        out.append(
            HoldingChange(
                symbol=sym,
                fund_name=fund_name,
                change_type=typ,
                shares=curr_sh,
                prev_shares=prev_sh,
                curr_shares=curr_sh,
            ).to_dict()
        )
    return out


def parse_13f_information_table_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)

    rows: list[dict] = []
    for info in root.findall(".//{*}infoTable"):
        symbol = ""
        symbol_node = info.find(".//{*}symbol")
        if symbol_node is not None and symbol_node.text:
            symbol = symbol_node.text.strip().upper()

        if not symbol:
            cusip_node = info.find(".//{*}cusip")
            symbol = (cusip_node.text.strip().upper() if cusip_node is not None and cusip_node.text else "")

        shares_node = info.find(".//{*}sshPrnamt")
        shares = _safe_int(shares_node.text if shares_node is not None else 0, 0)

        if symbol:
            rows.append({"symbol": symbol, "shares": shares})

    return rows


class SEC13FAnalyzer:
    def analyze(self, prev_rows: list[dict], curr_rows: list[dict], fund_name: str) -> dict:
        changes = compare_13f_holdings(prev_rows, curr_rows, fund_name=fund_name)
        return {
            "fund_name": fund_name,
            "count": len(changes),
            "changes": changes,
            "timestamp": _utc_now_iso(),
        }


def _load_rows(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    return []


def _cli() -> int:
    parser = argparse.ArgumentParser(description="SEC 13F analyzer")
    parser.add_argument("--fund", required=True)
    parser.add_argument("--prev-file", required=True, help="json rows file")
    parser.add_argument("--curr-file", required=True, help="json rows file")
    args = parser.parse_args()

    prev_rows = _load_rows(args.prev_file)
    curr_rows = _load_rows(args.curr_file)

    out = SEC13FAnalyzer().analyze(prev_rows, curr_rows, fund_name=args.fund)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
