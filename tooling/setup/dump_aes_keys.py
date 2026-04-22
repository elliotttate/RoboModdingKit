#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PATTERN_SPECS = (
    {
        "pattern": "C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ?",
        "dword_offsets": (3, 10, 17, 24, 35, 42, 49, 56),
    },
    {
        "pattern": "C7 ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ?",
        "dword_offsets": (2, 9, 16, 23, 30, 37, 44, 51),
    },
    {
        "pattern": "C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? 48 ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ?",
        "dword_offsets": (3, 10, 21, 28, 35, 42, 49, 56),
    },
    {
        "pattern": "C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? ? C7 ? ? ? ? ? C3",
        "dword_offsets": (51, 45, 38, 31, 24, 17, 10, 3),
    },
)

FALSE_POSITIVES = {
    "FFD9FFD9FFD9FFD9FFD9FFD9FFD9FFD9FFD9FFD9FFD9FFD9FFD9FFD9FFD9FFD9",
    "67E6096A85AE67BB72F36E3C3AF54FA57F520E518C68059BABD9831F19CDE05B",
    "D89E05C107D57C3617DD703039590EF7310BC0FF11155868A78FF964A44FFABE",
    "9A99593F9A99593F0AD7633F52B8BE3FE17A543FCDCC4C3D4260E53BAE47A13F",
    "6F168073B9B21449D742241700068ADABC306FA9AA3831164DEE8DE34E0EFBB0",
    "0AD7633FCDCC4C3DCDCCCC3D52B8BE3F9A99593F9A99593FC9767E3FE17A543F",
    "168073C7B21449C7430C00064310BC304314AA3843184DEE431C4E0E83C4205B",
    "E6096AC7AE67BBC7430C3AF543107F5243148C684318ABD9431C19CD436C2000",
    "9E05C1C7D57C36C7430C39594310310B431411154318A78F431CA44F436C1C00",
    "9E05C1C7D57C36C7DD7030C7590EF7C70BC0FFC7155868C78FF964C7A44FFABE",
    "168073C7B21449C7422417C7068ADAC7306FA9C7383116C7EE8DE3C74E0EFBB0",
    "0AD7633FCDCC4C3D00C742143DC742183FC7421C3FC742203FC742247E3FC742",
    "0000803F0AD7A33E0AD7633F52B8BE3FE17A543FCDCC4C3D4260E53B54AE47A1",
    "0AD7A33E0AD7633F52B8BE3FE17A543FCDCC4C3D4260E53BAE47A13F58583934",
    "0AD7A33E0AD7633F52B8BE3FE17A543FCDCC4C3D4260E53BAE47A13F38583934",
    "0000803F0AD7A33E0AD7633F52B8BE3FE17A543FCDCC4C3D4260E53B34AE47A1",
    "0000803F0000803F0AD7A33E0AD7633F52B8BE3FE17A543FCDCC4C3D2C4260E5",
    "0AD7633F52B8BE3FE17A543FCDCC4C3D4260E53BAE47A13F5839343C4CC9767E",
    "07D57C3617DD703039590EF7310BC0FF11155868A78FF964A44FFABE6C1C0000",
    "85AE67BB72F36E3C3AF54FA57F520E518C68059BABD9831F19CDE05B6C200000",
    "E6096AC7AE67BBC7F36E3CC7F54FA5C7520E51C768059BC7D9831FC719CDE05B",
    "0AD7A33E0AD7633F52B8BE3FE17A543FCDCC4C3D4260E53BAE47A13F3C583934",
    "E4D6E74FE4D667500044AC47926595380080DC43000A9B46000080BF000080BF",
    "D04C8F7D71ECC047D8A60970FBA31C9E9EC1250BBBF6459AC480947212E1DB8C",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan a UE4 Shipping executable for AES key candidates.")
    parser.add_argument("--exe", required=True, help="Path to the Shipping executable to scan.")
    parser.add_argument("--output", required=True, help="Path to the JSON file to write.")
    parser.add_argument("--verify-pak", help="Optional pak path to test candidate AES keys against.")
    parser.add_argument("--repak", help="Path to repak.exe. Required when --verify-pak is set.")
    parser.add_argument("--min-entropy", type=float, default=3.3, help="Minimum hex-string entropy to rank a candidate.")
    parser.add_argument("--verify-limit", type=int, default=10, help="Maximum ranked candidates to test with repak.")
    return parser.parse_args()


def compile_pattern(pattern: str) -> re.Pattern[bytes]:
    pieces = []
    for token in pattern.split():
        if token == "?":
            pieces.append(b".")
        else:
            pieces.append(re.escape(bytes.fromhex(token)))
    return re.compile(b"".join(pieces), re.DOTALL)


def calc_hex_entropy(hex_string: str) -> float:
    counts = Counter(hex_string)
    length = len(hex_string)
    if length == 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        frequency = count / length
        entropy -= frequency * math.log2(frequency)
    return entropy


def build_key(blob: bytes, match_offset: int, dword_offsets: tuple[int, ...]) -> str:
    key_parts = []
    for dword_offset in dword_offsets:
        key_parts.append(blob[match_offset + dword_offset : match_offset + dword_offset + 4].hex().upper())
    return "".join(key_parts)


def verify_candidate(repak_path: Path, pak_path: Path, key: str) -> dict:
    command = [str(repak_path), "-a", key, "info", str(pak_path)]
    process = subprocess.run(command, capture_output=True, text=True)
    return {
        "attempted": True,
        "verified": process.returncode == 0,
        "exit_code": process.returncode,
        "stdout_excerpt": process.stdout.splitlines()[:8],
        "stderr_excerpt": process.stderr.splitlines()[:8],
    }


def main() -> int:
    args = parse_args()

    exe_path = Path(args.exe).resolve()
    output_path = Path(args.output).resolve()
    if not exe_path.is_file():
        raise SystemExit(f"Executable not found: {exe_path}")

    verify_pak_path = Path(args.verify_pak).resolve() if args.verify_pak else None
    repak_path = Path(args.repak).resolve() if args.repak else None
    if verify_pak_path and not repak_path:
        raise SystemExit("--repak is required when --verify-pak is set.")
    if verify_pak_path and not verify_pak_path.is_file():
        raise SystemExit(f"Pak not found: {verify_pak_path}")
    if repak_path and not repak_path.is_file():
        raise SystemExit(f"repak executable not found: {repak_path}")

    blob = exe_path.read_bytes()

    raw_candidates = []
    for pattern_index, spec in enumerate(PATTERN_SPECS):
        compiled = compile_pattern(spec["pattern"])
        for match in compiled.finditer(blob):
            offset = match.start()
            key = build_key(blob, offset, spec["dword_offsets"])
            entropy = calc_hex_entropy(key)
            raw_candidates.append(
                {
                    "key": key,
                    "entropy": entropy,
                    "pattern_index": pattern_index,
                    "offset": offset,
                    "offset_hex": f"0x{offset:X}",
                    "false_positive": key in FALSE_POSITIVES,
                    "passes_threshold": entropy >= args.min_entropy,
                }
            )

    by_key: dict[str, dict] = {}
    for candidate in raw_candidates:
        existing = by_key.get(candidate["key"])
        occurrence = {
            "pattern_index": candidate["pattern_index"],
            "offset": candidate["offset"],
            "offset_hex": candidate["offset_hex"],
        }
        if existing is None:
            by_key[candidate["key"]] = {
                "key": candidate["key"],
                "entropy": candidate["entropy"],
                "false_positive": candidate["false_positive"],
                "passes_threshold": candidate["passes_threshold"],
                "passes_filters": (not candidate["false_positive"]) and candidate["passes_threshold"],
                "occurrences": [occurrence],
                "verified": False,
                "verification": None,
            }
            continue

        existing["occurrences"].append(occurrence)

    candidates = list(by_key.values())
    for candidate in candidates:
        candidate["occurrences"].sort(key=lambda item: item["offset"])
        candidate["occurrence_count"] = len(candidate["occurrences"])
        candidate["first_offset"] = candidate["occurrences"][0]["offset"]
        candidate["first_offset_hex"] = candidate["occurrences"][0]["offset_hex"]

    ranked_candidates = sorted(
        (candidate for candidate in candidates if candidate["passes_filters"]),
        key=lambda item: (-item["entropy"], item["first_offset"]),
    )

    verified_key = None
    verification_target = str(verify_pak_path) if verify_pak_path else None
    if verify_pak_path and repak_path:
        for candidate in ranked_candidates[: max(args.verify_limit, 0)]:
            verification = verify_candidate(repak_path, verify_pak_path, candidate["key"])
            candidate["verification"] = verification
            candidate["verified"] = verification["verified"]
            if verification["verified"]:
                verified_key = candidate["key"]
                break

    ranked_candidates = sorted(
        ranked_candidates,
        key=lambda item: (0 if item["verified"] else 1, -item["entropy"], item["first_offset"]),
    )

    result = {
        "exe_path": str(exe_path),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "min_entropy": args.min_entropy,
        "raw_candidate_count": len(raw_candidates),
        "unique_candidate_count": len(candidates),
        "ranked_candidate_count": len(ranked_candidates),
        "best_key": ranked_candidates[0]["key"] if ranked_candidates else None,
        "verified_key": verified_key,
        "verification_target_pak": verification_target,
        "candidates": ranked_candidates,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Scanned {exe_path}")
    print(f"Raw matches: {len(raw_candidates)}")
    print(f"Ranked candidates: {len(ranked_candidates)}")
    if verified_key:
        print(f"Verified AES key: 0x{verified_key}")
    elif ranked_candidates:
        print(f"Top AES candidate: 0x{ranked_candidates[0]['key']}")
    else:
        print("No AES candidates met the ranking threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
