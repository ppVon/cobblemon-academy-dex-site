#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compute Base Stat Totals (BST) for Pokémon JSON files, assign tiers, and export per-tier species JSON.

Usage (from project root):
    python bst_analysis.py --in site/out/mons --out site/_bst_analysis --tiers 6

Outputs (under --out, NOT in /out):
  - pokemon_bst_sorted.csv
  - pokemon_bst_tiers_<k>.csv
  - tiers/tier_1.json, tiers/tier_2.json, ..., tiers/tier_k.json
"""

from __future__ import annotations
import argparse
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

# --- Key variants for base stats ---
STAT_KEYS_ALIASES: Dict[str, Tuple[str, ...]] = {
    "hp": ("hp",),
    "attack": ("attack", "atk"),
    "defense": ("defence", "defense", "def"),
    "special_attack": ("special_attack", "sp_attack", "spattack", "sp_atk", "spatk", "spa"),
    "special_defense": ("special_defence", "special_defense", "sp_defence", "sp_defense", "spdef", "sp_def", "spd"),
    "speed": ("speed", "spe"),
}

ID_KEYS = ("id", "name", "slug", "identifier")

@dataclass
class MonRow:
    ident: str
    bst: int
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    source: Path

def find_first(d: Dict, keys: Iterable[str]):
    for k in keys:
        if k in d:
            return d[k]
    return None

def coerce_int(x) -> int:
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, (int, float)):
        return int(x)
    if isinstance(x, str):
        s = x.strip()
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return int(s)
        try:
            return int(float(s))
        except ValueError:
            pass
    raise ValueError(f"Cannot coerce to int: {x!r}")

def extract_base_stats(obj: Dict) -> Dict[str, int] | None:
    for k in ("baseStats", "base_stats", "basestats"):
        if isinstance(obj.get(k), dict):
            bs = obj[k]
            break
    else:
        # fallback: treat root as stats if several keys present
        candidates = [a for aliases in STAT_KEYS_ALIASES.values() for a in aliases]
        present = sum(1 for a in candidates if a in obj)
        if present >= 3:
            bs = obj
        else:
            return None

    out: Dict[str, int] = {}
    for canon, aliases in STAT_KEYS_ALIASES.items():
        val = find_first(bs, aliases)
        if val is None:
            return None
        try:
            out[canon] = coerce_int(val)
        except Exception:
            return None
    return out

def extract_id(obj: Dict) -> str | None:
    ident = find_first(obj, ID_KEYS)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    for parent in ("pokemon", "meta", "info"):
        if isinstance(obj.get(parent), dict):
            ident = find_first(obj[parent], ID_KEYS)
            if isinstance(ident, str) and ident.strip():
                return ident.strip()
    return None

def scan_dir(input_dir: Path) -> List[MonRow]:
    rows: List[MonRow] = []
    for fp in sorted(input_dir.rglob("*.json")):
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        bs = extract_base_stats(data)
        if not bs:
            continue

        ident = extract_id(data) or fp.stem
        bst = bs["hp"] + bs["attack"] + bs["defense"] + bs["special_attack"] + bs["special_defense"] + bs["speed"]
        rows.append(MonRow(
            ident=ident,
            bst=bst,
            hp=bs["hp"],
            attack=bs["attack"],
            defense=bs["defense"],
            special_attack=bs["special_attack"],
            special_defense=bs["special_defense"],
            speed=bs["speed"],
            source=fp
        ))
    return rows

def quantile_cutpoints(values: List[int], k: int) -> List[float]:
    if k <= 1 or not values:
        return []
    vs = sorted(values)
    cuts = []
    for i in range(1, k):
        pos = (len(vs) - 1) * (i / k)
        lo = math.floor(pos)
        hi = math.ceil(pos)
        if lo == hi:
            cuts.append(float(vs[lo]))
        else:
            frac = pos - lo
            cuts.append(vs[lo] + frac * (vs[hi] - vs[lo]))
    return cuts

def assign_tier(bst: int, cuts: List[float]) -> int:
    for idx, c in enumerate(cuts, start=1):
        if bst <= c:
            return idx
    return len(cuts) + 1

def write_csv(path: Path, header: List[str], rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")

def write_json(path: Path, obj: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")

def to_species_id(ident: str) -> str:
    """Ensure namespaced species ID (default to cobblemon:)."""
    return ident if ":" in ident else f"cobblemon:{ident}"

def main():
    ap = argparse.ArgumentParser(description="Compute BST from Pokémon JSON, assign tiers, export per-tier species.")
    ap.add_argument("--in", dest="input_dir", type=Path, default=Path("site/out/mons"),
                    help="Input folder to scan for *.json (recursively).")
    ap.add_argument("--out", dest="output_dir", type=Path, default=Path("bst_analysis"),
                    help="Output folder (must NOT be inside /out).")
    ap.add_argument("--tiers", dest="tiers", type=int, default=7,
                    help="Number of quantile-based tiers.")
    ap.add_argument("--show-top", dest="show_top", type=int, default=5,
                    help="Console: show top N by BST.")
    ap.add_argument("--show-bottom", dest="show_bottom", type=int, default=5,
                    help="Console: show bottom N by BST.")
    args = ap.parse_args()

    # Guard: avoid writing into /out
    out_parts = [p.lower() for p in args.output_dir.parts]
    if "out" in out_parts:
        raise SystemExit("Refusing to write into a folder named 'out'. Choose a different --out directory.")

    rows = scan_dir(args.input_dir)
    if not rows:
        print(f"No Pokémon JSONs with baseStats found under: {args.input_dir}")
        return

    rows_sorted = sorted(rows, key=lambda r: (r.bst, r.ident.lower()))
    bst_values = [r.bst for r in rows_sorted]

    # Stats
    n = len(bst_values)
    bst_min, bst_max = min(bst_values), max(bst_values)
    bst_mean = statistics.fmean(bst_values)
    bst_median = statistics.median(bst_values)
    bst_stdev = statistics.pstdev(bst_values) if n > 1 else 0.0
    p10, p25, p50, p75, p90 = (
        statistics.quantiles(bst_values, n=10, method="inclusive")[0],
        statistics.quantiles(bst_values, n=4, method="inclusive")[0],
        bst_median,
        statistics.quantiles(bst_values, n=4, method="inclusive")[2],
        statistics.quantiles(bst_values, n=10, method="inclusive")[8],
    )

    print(f"\nFound {n} Pokémon.")
    print(f"BST  min={bst_min}  max={bst_max}  mean={bst_mean:.2f}  median={bst_median:.2f}  stdev={bst_stdev:.2f}")
    print(f"Pct  p10={p10:.0f}  p25={p25:.0f}  p50={p50:.0f}  p75={p75:.0f}  p90={p90:.0f}\n")

    print("Bottom by BST:")
    for r in rows_sorted[:args.show_bottom]:
        print(f"  {r.ident:20s}  BST={r.bst:4d}  (hp {r.hp}, atk {r.attack}, def {r.defense}, spa {r.special_attack}, spd {r.special_defense}, spe {r.speed})")

    print("\nTop by BST:")
    for r in rows_sorted[-args.show_top:]:
        print(f"  {r.ident:20s}  BST={r.bst:4d}  (hp {r.hp}, atk {r.attack}, def {r.defense}, spa {r.special_attack}, spd {r.special_defense}, spe {r.speed})")

    # Sorted CSV
    sorted_csv = args.output_dir / "pokemon_bst_sorted.csv"
    write_csv(
        sorted_csv,
        header=["ident", "bst", "hp", "attack", "defense", "special_attack", "special_defense", "speed", "source_path"],
        rows=((r.ident, r.bst, r.hp, r.attack, r.defense, r.special_attack, r.special_defense, r.speed, str(r.source)) for r in rows_sorted),
    )

    # Tiers + counts
    k = max(1, args.tiers)
    cuts = quantile_cutpoints(bst_values, k)
    tiers_csv = args.output_dir / f"pokemon_bst_tiers_{k}.csv"

    # Prepare per-tier species lists and counts
    tier_species: List[set[str]] = [set() for _ in range(k)]
    tier_counts = [0] * k
    tiered_rows = []

    for r in rows_sorted:
        t = assign_tier(r.bst, cuts)  # 1..k
        tiered_rows.append((r.ident, r.bst, t))
        tier_counts[t - 1] += 1
        tier_species[t - 1].add(to_species_id(r.ident))

    write_csv(tiers_csv, header=["ident", "bst", "tier"], rows=tiered_rows)

    # Friendly printout of tier boundaries with counts
    print("\nTier boundaries (quantile cutpoints):")
    if not cuts:
        print(f"  1 tier: all {n} Pokémon in the same tier.")
    else:
        bounds = [bst_min] + [round(c) for c in cuts] + [bst_max]
        for idx in range(1, k + 1):
            lo = bounds[idx - 1]
            hi = bounds[idx]
            lo_sym = "[" if idx == 1 else "("  # first bin inclusive, others (lo..hi]
            print(f"  Tier {idx}: {lo_sym}{lo}, {hi}]  count={tier_counts[idx-1]}")

    # --- NEW: write per-tier species JSONs ---
    tiers_dir = args.output_dir / "tiers"
    for idx in range(1, k + 1):
        species_sorted = sorted(tier_species[idx - 1])
        tier_path = tiers_dir / f"tier_{idx}.json"
        write_json(tier_path, {"species": species_sorted})

    print(f"\nWrote:\n  - {sorted_csv}\n  - {tiers_csv}\n  - {tiers_dir}/tier_*.json\n")

if __name__ == "__main__":
    main()
