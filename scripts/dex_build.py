import os, json, zipfile
from pathlib import Path
from collections import defaultdict
import re

ROOT = Path(".")        # run from your instance root (same folder as /mods, /datapacks or /world/datapacks)
DEX_OUT = ROOT / "out/dex.json"
PRESETS_OUT = ROOT / "out/presets.json"
BIOMES_OUT = ROOT / "out/biomes.json"
BLOCKS_OUT = ROOT / "out/blocks.json"   # NEW
SPECIES_SOURCES_OUT = ROOT / "out/species_sources.json"  # NEW

# --- Per-mon output directories ---
OUT_DIR = ROOT / "out"
MONS_DIR = OUT_DIR / "mons"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MONS_DIR.mkdir(parents=True, exist_ok=True)
DROPS_OUT = ROOT / "out" / "drops_index.json"



PACK_ORDER = [
    # built-ins & fabric mods (earlier ones = lower priority)
    "vanilla","fabric","academy","additional_lights","amendments","animal_pen","another_furniture",
    "arts_and_crafts","atistructures","balm","beautify","bettervillage","biomeblends","biomeswevegone",
    "bookshelf","chalk","chimes","cloudboots","cobblefurnies","cobbleloots","cobblemon","cobblemon_counter",
    "cobblemon_ultrabeast","cobblemon_utility","cobblemonalphas","cobblemonsizevariation","cobblenav",
    "cobbleride","collective","comforts","connectiblechains","constructionwand","cozyhome","craftingtweaks",
    "crafttweaker","desolate-dwellings","display","dynamiccrosshair-api","dynamiccrosshaircompat","effectual",
    "elevatorid","emojiful","enhancedcelestials","eternal_starlight","exposure","exposure_polaroid",
    "fabric-convention-tags-v2","fading_clouds","fightorflight","fireworkcapsules","ftbfiltersystem","ftbquests",
    "glassential","gliding","handcrafted","heartstone","hopobetterunderwaterruins","hotkettles","knowlogy","labels",
    "laserbridges","letsparkour","libraryferret","linkedchests","lootr","mcpitanlib","mega_showdown","mermod","mes",
    "mighty_mail","minerally","mns","moonlight","mr_dungeons_andtavernsdeserttemplereplacement",
    "mr_dungeons_andtavernsjungletemplereplacement","mr_dungeons_andtavernspillageroutpostoverhaul",
    "mr_dungeons_andtavernsswamphutoverhaul","mr_dungeons_andtavernswoodlandmansionreplacement",
    "mr_ly_agilityenchantment","mss","mvs","naturescompass","nightlights","numismatic-overhaul","ohmymeteors",
    "ohthetreesyoullgrow","particleanimationlib","player_roles","pokeblocks","porting_lib_item_abilities",
    "potleaves","rad-gyms","rechiseled","regions_unexplored","rightclickharvest","scholar","seasonhud","sereneseasons",
    "shutter","simpletms","sootychimneys","sophisticatedbackpacks","sophisticatedcore","sophisticatedstorage",
    "sophisticatedstorageinmotion","stoneworks","supermartijn642corelib","telepass","templates","terrablender",
    "tim_core","toms_storage","totw_modded","travelerstitles","trinkets","vanity","vanity_black_gold","vanity_bone",
    "vanity_druid","vanity_helios","vanity_magma","vanity_spartan","vanity_spectral","vanity_steel","vanity_viking",
    "veinmining","visualworkbench","waystones","wingedsandals","wwoo","xercapaint","yungsapi","zipline",
    # built-ins added by mods
    "$polymer-resources","moonlight:mods_dynamic_assets",
    # globals (these are the ones whose order changed most vs earlier)
    "Trek 1.21.x B0.4.1","stellarity_lite_3.0.5.6","MythsandLegends-Datapack-v1.0.4","MysticMons_v3.2.1",
    "JakesBuildTools-v2.0.1.4-(1.21.1)-Data-Resource-Pack.zip","Disable SeasonHUD Slot 1.1.1.zip","CCC_MAL_1.6.4.1",
    "Academy",
]


FORM_SYNONYMS = {
    "alola": "alola", "alolan": "alola",
    "galar": "galar", "galarian": "galar",
    "hisui": "hisui", "hisuian": "hisui",
    "paldea": "paldea", "paldean": "paldea",
    "kanto": "kanto", "kantonian": "kanto",
}
REGIONAL_KEYS = set(FORM_SYNONYMS.values())

NON_REGIONAL_SUFFIXES = {"hero", "mega", "gmax", "partner"}


# ------------------------- FS helpers -------------------------

def _biomes_are_none(selectors) -> bool:
    vals = selectors or []
    if isinstance(vals, str):
        vals = [vals]
    norms = [str(x).strip().lower() for x in vals if x is not None]
    return len(norms) > 0 and all(v == "none" for v in norms)

def _canon(s: str) -> str:
    """lowercase; replace non-alnum with '_'."""
    return re.sub(r'[^a-z0-9]+', '_', str(s).lower()).strip('_')

PACK_ORDER_CANON = [_canon(n) for n in PACK_ORDER]  # keep this line as you had it
def _pack_priority_map():
    """
    Map canonical pack name -> rank (higher number = higher priority),
    based on the static PACK_ORDER above.
    """
    return {name: idx for idx, name in enumerate(PACK_ORDER_CANON)}

def _pack_id_from_source_marker(marker: str, priority_map: dict) -> str:
    """
    marker examples:
      'SomeMod.jar!/data/...'
      'datapacks\\CCC_MAL_1.6.4.1\\data\\...'
    """
    m = str(marker)
    m_low = m.lower()

    # datapacks/<folder>/...
    if "datapacks" in m_low:
        parts = re.split(r'[\\/]', m)
        for i, p in enumerate(parts):
            if p.lower() == "datapacks" and i + 1 < len(parts):
                return _canon(parts[i + 1])

    # jar base name
    jar_base = _canon(Path(m.split('!/', 1)[0]).stem)

    # exact
    if jar_base in priority_map:
        return jar_base

    # fuzzy: any known id substring
    for pid in priority_map:
        if pid in jar_base or jar_base in pid:
            return pid

    # fallback
    return jar_base

def _priority_for_marker(marker: str, priority_map: dict) -> int:
    pid = _pack_id_from_source_marker(marker, priority_map)
    return priority_map.get(pid, 0)  # unknown packs get lowest score

def _extract_pokemon_ids_from_spawn(spawn_obj):
    """
    Returns a list of species ids referenced by the spawn line.

    Accepts:
      - plain strings: "ekans", "slowpoke galarian"
      - namespaced ids: "cobblemon:pansage"
      - strings with attributes: "ekans snake_pattern=classic"
      - lists of strings/dicts
      - dicts with 'id' / 'species' / 'name'
    """
    v = spawn_obj.get("pokemon")
    ids = []

    def _coerce_one(s):
        if not isinstance(s, str):
            return None
        sid = _normalize_species_id_from_pokemon_value(s)
        # Fallback: if we couldn't parse multi-word form, try filename-style
        if not sid:
            sid = _normalize_species_id_from_filename(s)
        return sid

    if isinstance(v, str):
        sid = _coerce_one(v)
        if sid:
            ids.append(sid)

    elif isinstance(v, list):
        for item in v:
            if isinstance(item, str):
                sid = _coerce_one(item)
                if sid:
                    ids.append(sid)
            elif isinstance(item, dict):
                s = item.get("id") or item.get("species") or item.get("name")
                sid = _coerce_one(s) if s else None
                if sid:
                    ids.append(sid)

    elif isinstance(v, dict):
        s = v.get("id") or v.get("species") or v.get("name")
        sid = _coerce_one(s) if s else None
        if sid:
            ids.append(sid)

    return ids

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def _parse_leading_dexnum(base_name: str):
    m = re.match(r"^0*(\d{1,4})(?:[_-]|$)", base_name.lower())
    return int(m.group(1)) if m else None

def _strip_leading_dex(base_name: str) -> str:
    # "058_growlithe_hisui" -> "growlithe_hisui"
    return re.sub(r"^0*\d+[_-]*", "", base_name.lower())

def _extract_region_from_name(base_name: str) -> str | None:
    # Return canonical region token if present in the filename
    tokens = re.split(r"[^a-z0-9]+", base_name.lower())
    for t in tokens:
        if t in FORM_SYNONYMS:
            return FORM_SYNONYMS[t]
    return None

def _canonical_region_token_from_text(text: str | None) -> str | None:
    if not text: return None
    import re
    t = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    for part in t.split("_"):
        if part in FORM_SYNONYMS:
            return FORM_SYNONYMS[part]
    return None

def _canonical_form_suffix(form: dict, base_name: str = "") -> str | None:
    # Prefer the form's “name”
    tok = _canonical_region_token_from_text(form.get("name"))
    if tok: return tok
    # Then look at labels/aspects/features on the form
    for src in (form.get("labels"), form.get("aspects"), form.get("features")):
        if isinstance(src, list):
            for v in src:
                tok = _canonical_region_token_from_text(str(v))
                if tok: return tok
    return None

def _normalize_species_id_from_filename(stem: str) -> str:
    """
    Normalize ids inferred from filenames:
      - lowercase
      - drop leading ####_ if present (e.g., '0105_growlithe-hisui' -> 'growlithe-hisui')
      - '-' -> '_' 
      - canonicalize regional suffixes (alolan→alola, hisuian→hisui, etc.)
    """
    s = stem.lower()
    m = re.match(r"^(?:\d+_)(.+)$", s)
    if m:
        s = m.group(1)
    s = s.replace("-", "_").strip("_")

    parts = s.split("_")
    if len(parts) >= 2:
        last = parts[-1]
        if last in FORM_SYNONYMS:
            parts[-1] = FORM_SYNONYMS[last]
            s = "_".join(parts)
    return s

def _normalize_species_id_from_pokemon_value(text: str) -> str | None:
    """
    Normalize Cobblemon 'pokemon' field values from spawn rows.
    Handles:
      - "slowpoke galarian"   -> "slowpoke_galar"
      - "meowth alolan"       -> "meowth_alola"
      - "growlithe hisuian"   -> "growlithe_hisui"
      - "tauros paldean combat" -> "tauros_paldea_combat"
      - "cobblemon:pansage"   -> "pansage"
      - "ekans snake_pattern=classic" -> "ekans"   (drops attribute tail)
    """
    if not isinstance(text, str):
        return None

    s = text.strip().lower()
    if not s:
        return None

    # replace '%' so things like "10%" won't be lost, then kill punctuation into spaces
    s = s.replace("%", " percent")
    s = re.sub(r"[^\w\s:-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Split into space tokens but stop before attribute chunks (anything with '=')
    raw_tokens = [t for t in s.split(" ") if t and "=" not in t]
    if not raw_tokens:
        return None

    # First token may be namespaced, keep rhs
    first = raw_tokens[0]
    if ":" in first:
        first = first.split(":", 1)[1]

    base = re.sub(r"[^a-z0-9]+", "", first)
    if not base:
        return None

    tail_tokens = raw_tokens[1:]  # e.g., ["galarian"], ["paldean","combat"], etc.
    # Map any regional adjective to canonical region token (alolan->alola, etc.)
    region = None
    other_suffix = []

    for t in tail_tokens:
        t_clean = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
        # try to map this token to a region
        mapped = FORM_SYNONYMS.get(t_clean)
        if mapped and mapped in REGIONAL_KEYS and region is None:
            region = mapped
        else:
            if t_clean:
                other_suffix.append(t_clean)

    parts = [base]
    if region:
        parts.append(region)
    if other_suffix:
        parts.extend(other_suffix)

    return "_".join(parts)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")

def iter_datapack_dirs():
    # Datapacks in world or root (pack-dependent)
    for dp in [ROOT/"datapacks", ROOT/"world"/"datapacks"]:
        if dp.is_dir():
            yield from [p for p in dp.iterdir() if p.is_dir()]

def iter_mod_jars():
    mods = ROOT/"mods"
    if mods.is_dir():
        yield from sorted(mods.glob("*.jar"))

def read_json_from_fs(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def read_jsons_from_zip(z, prefix):
    for name in z.namelist():
        if name.startswith(prefix) and name.endswith(".json"):
            try:
                with z.open(name) as f:
                    yield name, json.loads(f.read().decode("utf-8"))
            except Exception:
                pass

def _filter_species(name):
    filters = ['_mega', '_gmax', '_bias', '_hero', 'partner']
    for filter in filters:
        if filter in name:
            return True 
    return False


# ------------------------- Species & spawns -------------------------
def expand_species_with_forms(species: dict) -> dict:
    """
    Create '<baseid>_<suffix>' entries for forms[] using canonical regional suffixes.
    - Skip expanding for species whose id already ends with a regional suffix (prevents form-of-form).
    - If a variant id already exists (from a separate file), MERGE base -> existing -> form (form wins).
    """
    out = dict(species)

    # keys form JSONs commonly override
    override_keys = [
        "name","primaryType","secondaryType","maleRatio","height","weight",
        "pokedex","labels","aspects","abilities","eggGroups",
        "baseStats","evYield","baseExperienceYield","experienceGroup",
        "catchRate","eggCycles","baseFriendship","features","baseScale",
        "hitbox","behaviour","drops","moves","preEvolution","evolutions",
        "battleOnly","types","spawns"
    ]

    for sid, base in list(species.items()):
        # Don't expand forms for ids that already look like a regional variant
        last = sid.split("_")[-1]
        if last in REGIONAL_KEYS:
            continue

        forms = base.get("forms", [])
        if not isinstance(forms, list):
            continue

        for f in forms:
            if not isinstance(f, dict):
                continue
            """
            if not _is_implemented(f):
                continue
            """
            fname = f.get("name")
            if not fname:
                continue

            # Determine a canonical suffix like "hisui"
            suffix = _canonical_form_suffix(f, base.get("name", "")) or _slug(fname)
            if suffix in FORM_SYNONYMS:
                suffix = FORM_SYNONYMS[suffix]

            fid = f"{sid}_{suffix}"

            if(_filter_species(fid)):
                continue


            # Start with base, apply existing variant (if any), then the form overrides (form wins)
            merged = dict(base)
            if fid in out:
                # Preserve anything the standalone variant file already had
                for k, v in out[fid].items():
                    merged[k] = v

            # Apply form-level overrides
            for k in override_keys:
                if k in f:
                    merged[k] = f[k]

            # Ensure display name reflects the form (even if file had a plain name)
            merged["name"] = f"{base.get('name', sid)} {fname}"

            merged["variantOf"] = sid
            merged["forms"] = []  # avoid nested expansions

            if not "spawns" in f:
                merged["spawns"] = []

            out[fid] = merged

    return out


def _parse_leading_dexnum(base_name: str):
    # e.g. "019_rattata", "0105_marowak_alola" -> 19/105
    m = re.match(r"^0*(\d{1,4})(?:[_-]|$)", base_name.lower())
    return int(m.group(1)) if m else None

def _is_implemented(obj) -> bool:
    v = obj.get("implemented", False)
    # handle quirky string values like "false"
    if isinstance(v, str):
        v = v.strip().lower() not in ("false", "no", "0")
    return bool(v)


def collect_species():
    species = {}                   # id -> chosen JSON
    sources = defaultdict(set)     # id -> all markers
    best_rank = {}                 # id -> numeric rank

    order_map = _pack_priority_map()

    def maybe_take(sid: str, js: dict, marker: str):
        sources[sid].add(marker)
        rank = _priority_for_marker(marker, order_map)
        if sid not in best_rank or rank >= best_rank[sid]:
            species[sid] = js
            best_rank[sid] = rank

    # from mods
    for jar in iter_mod_jars():
        with zipfile.ZipFile(jar) as z:
            for name, js in read_jsons_from_zip(z, "data/cobblemon/species/"):
                if not js:
                    continue
                sid = _normalize_species_id_from_filename(Path(name).stem)
                if _filter_species(sid):
                    continue
                maybe_take(sid, js, f"{Path(jar).name}!/{name}")

    # from datapacks
    for dp in iter_datapack_dirs():
        for p in dp.rglob("data/cobblemon/species/**/*.json"):
            js = read_json_from_fs(p)
            if not js:
                continue
            sid = _normalize_species_id_from_filename(p.stem)
            maybe_take(sid, js, str(p))

    sources = {k: sorted(v) for k, v in sources.items()}
    return species, sources

def collect_spawns():
    spawns = defaultdict(list)
    itr = 0

    def _mark_source(spawn_obj, marker: str):
        s2 = dict(spawn_obj)
        s2["_source"] = marker
        return s2

    def add_spawn_entry(name, js):
        """
        Route spawn lines to the correct species. Prefer explicit 'pokemon' on each spawn;
        fall back to filename guessing if no explicit pokemon is present anywhere.
        """
        any_routed = False
        sp_list = js.get("spawns") or []
        for s in sp_list:
            weight = s.get("weight")
            cond = s.get("condition") or {}
            biomes = cond.get("biomes") or []
            s['source'] = name

            if weight is None or float(weight) <= 0:
                continue

            if _biomes_are_none(cond.get("biomes")):
                continue

            # normalize biome list
            biomes_norm = [str(b).lower().strip() for b in biomes if b]

            if (weight is None or float(weight) <= 0) or (not biomes_norm or biomes_norm == ["none"]):
                continue

            sids = _extract_pokemon_ids_from_spawn(s)
            if sids:
                any_routed = True
                for sid in sids:
                    spawns[sid].append({"spawns": [_mark_source(s, name)]})



        if not any_routed:
            base = Path(name).stem.lower()
            parts = base.split("_", 1)
            sid = parts[1] if len(parts) == 2 else base
            marked_spawns = []
            for s in js.get("spawns") or []:
                marked_spawns.append(_mark_source(s, name))
            if marked_spawns:
                spawns[sid].append({"spawns": marked_spawns})

    # mods
    for jar in iter_mod_jars():
        with zipfile.ZipFile(jar) as z:
            for name, js in read_jsons_from_zip(z, "data/"):
                if "/spawn_pool_world/" in name and name.endswith(".json"):
                    add_spawn_entry(f"{Path(jar).name}!/{name}", js)


    # datapacks
    for dp in iter_datapack_dirs():
        for p in dp.rglob("data/**/spawn_pool_world/*.json"):
            js = read_json_from_fs(p)
            if js:
                rel = p.as_posix()
                add_spawn_entry(rel, js)
        for p in dp.rglob("data/**/spawn_pool_world/**/*.json"):
            js = read_json_from_fs(p)
            if js:
                rel = p.as_posix()
                add_spawn_entry(rel, js)
    
    deduped = defaultdict(list)
    for sid, raw_list in spawns.items():
        seen = set()
        for raw in raw_list:
            # raw is {"spawns": [spawn_obj, ...]} (we stored one-at-a-time above)
            for e in raw.get("spawns", []):
                # canonical string for exact-match de-dupe
                key = json.dumps(e, sort_keys=True, ensure_ascii=False)
                if key in seen:
                    continue
                seen.add(key)
                deduped[sid].append({"spawns": [e]})
    return deduped

# ------------------------- Biome tags (separate reference) -------------------------
def _normalize_drop_entry(ent, extra=None):
    """Normalize a drop entry to a common shape and attach optional metadata."""
    extra = extra or {}
    return {
        "item": (ent.get("item") or "").strip().lower(),
        "percentage": ent.get("percentage"),
        "quantityRange": ent.get("quantityRange"),
        **({k: v for k, v in extra.items() if v is not None}),
    }

def _extract_drops_from_spawn(spawn_obj):
    """
    From a single spawn line (the dict inside 'spawns': [...]), pull any drops.
    Returns {"amount": int|0, "entries": [normalized entries...], "meta": {...}} or None if no drops.
    """
    drops = spawn_obj.get("drops")
    if not isinstance(drops, dict):
        return None

    cond = spawn_obj.get("condition") or {}
    anti = spawn_obj.get("anticondition") or {}
    biomes_inc = cond.get("biomes")
    biomes_exc = anti.get("biomes")

    amt = 0
    try:
        amt = int(drops.get("amount") or 0)
    except Exception:
        amt = 0

    entries = []
    for e in drops.get("entries") or []:
        if not isinstance(e, dict):
            continue
        extra = {}
        if biomes_inc:
            extra["biomes"] = biomes_inc
        if biomes_exc:
            extra["excludeBiomes"] = biomes_exc
        entries.append(_normalize_drop_entry(e, extra=extra))

    return {"amount": amt, "entries": entries}

def _merge_drops(species_drops, spawn_drop_objs):
    """
    Merge species-level drops with any number of spawn-sourced drops.
    Rules:
      - amount = max of all provided amounts
      - de-dup entries by item:
          * prefer an entry that has percentage over one that doesn't
          * if both have percentage, keep the higher
          * if neither has percentage, keep the wider quantityRange (fallback: keep the first seen)
      - merge metadata (e.g., biomes) by unioning lists
    """
    out_amt = 0
    merged = {}

    def _width(range_str):
        try:
            a, b = str(range_str or "").split("-")
            a, b = float(a), float(b)
            return abs(b - a)
        except Exception:
            return -1

    # seed with species
    if isinstance(species_drops, dict):
        try:
            out_amt = max(out_amt, int(species_drops.get("amount") or 0))
        except Exception:
            pass
        for e in species_drops.get("entries") or []:
            ne = _normalize_drop_entry(e, extra={"source": "species"})
            if not ne["item"]:
                continue
            merged[ne["item"]] = ne

    # overlay spawn-sourced
    for sd in (spawn_drop_objs or []):
        if not sd:
            continue
        try:
            out_amt = max(out_amt, int(sd.get("amount") or 0))
        except Exception:
            pass
        for e in sd.get("entries") or []:
            ne = _normalize_drop_entry(e, extra={"source": "spawn_pool_world", **{k: v for k, v in e.items() if k in ("biomes","excludeBiomes")}})
            if not ne["item"]:
                continue
            prev = merged.get(ne["item"])
            if not prev:
                merged[ne["item"]] = ne
                continue

            # Decide which wins
            pick = dict(prev)
            if ne["percentage"] is not None:
                if prev.get("percentage") is None or float(ne["percentage"]) > float(prev["percentage"]):
                    pick["percentage"] = ne["percentage"]
                    pick["quantityRange"] = None
            elif prev.get("percentage") is None:
                # both ranges -> wider wins
                if _width(ne.get("quantityRange")) > _width(prev.get("quantityRange")):
                    pick["quantityRange"] = ne.get("quantityRange")

            # merge metadata lists
            for key in ("biomes", "excludeBiomes"):
                vals = []
                if isinstance(prev.get(key), list):
                    vals += prev[key]
                if isinstance(ne.get(key), list):
                    vals += ne[key]
                if vals:
                    # dedup, stable
                    seen, out = set(), []
                    for v in vals:
                        if v not in seen:
                            seen.add(v); out.append(v)
                    pick[key] = out

            merged[ne["item"]] = pick

    return {"amount": out_amt, "entries": list(merged.values())}


def _normalize_tag_values(vals):
    """
    Tag 'values' can be strings or objects like {"id": "...", "required": false}.
    Return a list[str] of ids/tags only.
    """
    out = []
    for v in vals or []:
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            _id = v.get("id")
            if isinstance(_id, str):
                out.append(_id)
    return out

def collect_biome_tags():
    """
    Build a map of '#namespace:tag' -> list(values...), where values are biome IDs or other '#tag's.
    Later datapacks/files overwrite earlier ones (last-writer-wins per tag file).
    """
    tags = {}
    # From mod jars
    for jar in iter_mod_jars():
        with zipfile.ZipFile(jar) as z:
            for name, js in read_jsons_from_zip(z, "data/"):
                if "/tags/worldgen/biome/" in name and name.endswith(".json"):
                    # data/<ns>/tags/worldgen/biome/<tag>.json  (no nested folders here usually)
                    parts = name.split("/")
                    try:
                        ns = parts[1]
                        tag = parts[-1][:-5]
                        tag_key = f"#{ns}:{tag}"
                        vals = _normalize_tag_values(js.get("values", []))
                        tags[tag_key] = vals
                    except Exception:
                        pass
    # From datapacks
    for dp in iter_datapack_dirs():
        for p in dp.rglob("data/*/tags/worldgen/biome/*.json"):
            try:
                ns = p.parts[p.parts.index("data")+1]
                tag_key = f"#{ns}:{p.stem}"
                js = read_json_from_fs(p) or {}
                vals = _normalize_tag_values(js.get("values", []))
                tags[tag_key] = vals
            except Exception:
                pass
    return tags

def resolve_biome_selectors(selectors, tag_map):
    """
    selectors: list[str] ('minecraft:plains' or '#cobblemon:is_grassland')
    Returns a sorted list[str] of concrete biome IDs with tags fully expanded (recursively).
    """
    if isinstance(selectors, str):
        selectors = [selectors]
    elif not isinstance(selectors, list):
        selectors = []

    resolved = set()
    visiting = set()  # guard against cycles

    def expand(sel):
        if not isinstance(sel, str):
            return
        if sel.startswith("#"):
            if sel in visiting:
                return
            visiting.add(sel)
            for v in tag_map.get(sel, []):
                expand(v)
            visiting.remove(sel)
        else:
            resolved.add(sel)

    for s in selectors:
        expand(s)

    return sorted(resolved)

# ------------------------- Presets (separate reference) -------------------------

def _normalize_preset_json(js: dict):
    # Support singular/plural keys
    cond = js.get("conditions") or js.get("condition") or {}
    anti = js.get("anticonditions") or js.get("anticondition") or {}
    ctx  = js.get("contexts") or js.get("context") or []
    if isinstance(ctx, str):
        ctx = [ctx]
    return {
        "conditions": cond or {},
        "anticonditions": anti or {},
        "contexts": ctx or [],
    }

def collect_presets():
    """
    Returns: dict[preset_name -> {"conditions": {...}, "anticonditions": {...}, "contexts": [...] }]
    Later datapacks override earlier ones (last-writer-wins).
    """
    presets = {}
    # From mod jars
    for jar in iter_mod_jars():
        with zipfile.ZipFile(jar) as z:
            for name, js in read_jsons_from_zip(z, "data/"):
                if "/spawn_detail_presets/" in name and name.endswith(".json"):
                    try:
                        preset_name = Path(name).stem
                        presets[preset_name] = _normalize_preset_json(js or {})
                    except Exception:
                        pass
    # From datapacks
    for dp in iter_datapack_dirs():
        for p in dp.rglob("data/**/spawn_detail_presets/*.json"):
            try:
                js = read_json_from_fs(p) or {}
                presets[p.stem] = _normalize_preset_json(js)
            except Exception:
                pass
    return presets

# ------------------------- BLOCK TAGS (improved) -------------------------

def _extract_block_tag_key_from_zip(name: str):
    """
    Turn a zip entry like:
      data/minecraft/tags/blocks/mineable/pickaxe.json
    into: #minecraft:mineable/pickaxe

    Works for both 'blocks' and 'block' directories and nested paths.
    """
    if "/tags/blocks/" in name:
        prefix = name.split("/tags/blocks/", 1)[0]
        ns = prefix.split("/")[1]  # data/<ns>
        rel = name.split("/tags/blocks/", 1)[1][:-5]
        return f"#{ns}:{rel}"
    if "/tags/block/" in name:
        prefix = name.split("/tags/block/", 1)[0]
        ns = prefix.split("/")[1]
        rel = name.split("/tags/block/", 1)[1][:-5]
        return f"#{ns}:{rel}"
    return None

def _extract_block_tag_key_from_fs(path: Path):
    """
    Same as above but for filesystem paths.
    """
    s = path.as_posix()
    if "/tags/blocks/" in s:
        ns = s.split("/data/",1)[1].split("/",1)[0]
        rel = s.split("/tags/blocks/",1)[1][:-5]
        return f"#{ns}:{rel}"
    if "/tags/block/" in s:
        ns = s.split("/data/",1)[1].split("/",1)[0]
        rel = s.split("/tags/block/",1)[1][:-5]
        return f"#{ns}:{rel}"
    return None

def collect_block_tags():
    """
    Build a map of '#namespace:path' -> list(values...) for BLOCK tags.
    Scans both tags/blocks/** and tags/block/** recursively.
    """
    tags = {}
    # From mod jars
    for jar in iter_mod_jars():
        with zipfile.ZipFile(jar) as z:
            # scan all jsons under data/**/tags/**block(s)/**.json
            for name in z.namelist():
                if "/tags/blocks/" in name or "/tags/block/" in name:
                    if not name.endswith(".json"): continue
                    try:
                        key = _extract_block_tag_key_from_zip(name)
                        if not key: continue
                        with z.open(name) as f:
                            js = json.loads(f.read().decode("utf-8"))
                        tags[key] = _normalize_tag_values(js.get("values", []))
                    except Exception:
                        pass
    # From datapacks (recursive)
    for dp in iter_datapack_dirs():
        # both singular & plural, recursive
        for p in list(dp.rglob("data/*/tags/blocks/**/*.json")) + list(dp.rglob("data/*/tags/block/**/*.json")):
            try:
                key = _extract_block_tag_key_from_fs(p)
                if not key: continue
                js = read_json_from_fs(p) or {}
                tags[key] = _normalize_tag_values(js.get("values", []))
            except Exception:
                pass
    return tags

def resolve_block_selectors(selectors, tag_map, include_unresolved_child_tags=True):
    """
    selectors: list/str with 'minecraft:stone' or '#minecraft:base_stone_overworld'
    Recursively expand tags to concrete block IDs.
    If a child tag is missing from tag_map and include_unresolved_child_tags=True,
    include that child tag string in the output so you still see e.g. '#minecraft:...' rather than losing it.
    """
    if isinstance(selectors, str):
        selectors = [selectors]
    elif not isinstance(selectors, list):
        selectors = []

    resolved, visiting = set(), set()

    def expand(sel):
        if not isinstance(sel, str):
            return
        if sel.startswith("#"):
            if sel in visiting:
                return
            visiting.add(sel)
            values = tag_map.get(sel)
            if values is None:
                # Unknown tag – keep it if asked
                if include_unresolved_child_tags:
                    resolved.add(sel)
            else:
                any_expanded = False
                for v in values:
                    if isinstance(v, str) and v.startswith("#"):
                        # recurse into child tag
                        before = len(resolved)
                        expand(v)
                        any_expanded = any_expanded or (len(resolved) > before)
                    else:
                        resolved.add(v)
                        any_expanded = True
                # If nothing concrete came out and we want to preserve the structure,
                # include direct children tags so we surface e.g. '#minecraft:...'
                if not any_expanded and include_unresolved_child_tags:
                    for v in values:
                        if isinstance(v, str) and v.startswith("#"):
                            resolved.add(v)
            visiting.remove(sel)
        else:
            resolved.add(sel)

    for s in selectors:
        expand(s)

    # keep order stable-ish
    return sorted(resolved)

def _resolved_blocks_subset(obj, tag_map):
    """
    Walk a dict and return a parallel dict containing ONLY keys where we
    actually resolved one or more '#...' block tags into concrete IDs or child tags.
    """
    if not isinstance(obj, dict):
        return {}
    out = {}
    for k, v in obj.items():
        if isinstance(v, list):
            acc, saw_tag = [], False
            for itm in v:
                if isinstance(itm, str) and itm.startswith("#"):
                    acc.extend(resolve_block_selectors(itm, tag_map, include_unresolved_child_tags=True))
                    saw_tag = True
                elif isinstance(itm, str):
                    acc.append(itm)
            if saw_tag:
                # de-dup while keeping deterministic order
                seen = set()
                flat = []
                for a in acc:
                    if a not in seen:
                        seen.add(a)
                        flat.append(a)
                out[k] = flat
        elif isinstance(v, str) and v.startswith("#"):
            out[k] = resolve_block_selectors(v, tag_map, include_unresolved_child_tags=True)
        elif isinstance(v, dict):
            sub = _resolved_blocks_subset(v, tag_map)
            if sub:
                out[k] = sub
    return out

# ------------------------- Spawn flattening (link out to refs) -------------------------

def _as_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def _extract_times(condition: dict):
    times = []
    for k in ("times", "time", "timeRange"):
        v = condition.get(k)
        if v:
            if isinstance(v, list):
                times.extend(v)
            else:
                times.append(v)
    return sorted({str(t).lower() for t in times})

def flatten_spawn_entry_linked(entry, block_tag_map=None):
    """
    Lean spawn shape for the UI.
    Keeps: presets, rarity, weight, levels, contexts, times, biomeTags, source.
    Adds dynamic bits only when present & meaningful (no null/empty noise).
    """
    def _as_list(x):
        if x is None:
            return []
        if isinstance(x, list):
            return x
        return [x]

    def _nonempty(x):
        if x is None:
            return False
        if isinstance(x, (list, dict, str)):
            return len(x) > 0
        return True

    def _compact_dict(d):
        """Drop keys where value is '', None, empty list/dict, or an object with all-None members."""
        out = {}
        for k, v in d.items():
            if isinstance(v, dict):
                sub = _compact_dict(v)
                if _nonempty(sub):
                    out[k] = sub
            elif isinstance(v, list):
                vv = [i for i in v if i is not None and (not isinstance(i, str) or i != "")]
                if vv:
                    out[k] = vv
            elif v not in (None, ""):
                out[k] = v
        return out

    def _resolve_blocks_if_useful(selectors):
        if not selectors:
            return None
        if block_tag_map is None:
            # If any selector is a tag, keep selectors (client can resolve later)
            return None
        resolved = resolve_block_selectors(selectors, block_tag_map, include_unresolved_child_tags=True)
        # only return resolved if it adds value (contains a '#tag' OR differs from selectors)
        sel_set = set(selectors)
        res_set = set(resolved)
        if any(isinstance(s, str) and s.startswith("#") for s in selectors) or sel_set != res_set:
            return resolved
        return None

    result = []
    for e in entry.get("spawns", []):
        cond = e.get("condition", {}) or {}
        anti = e.get("anticondition", {}) or {}

        if _biomes_are_none(cond.get("biomes")):
            continue

        presets  = _as_list(e.get("presets"))
        contexts = _as_list(e.get("context"))
        times = sorted({str(t).lower() for t in _as_list(cond.get("times"))})

        inc_tags = _as_list(cond.get("biomes"))
        exc_tags = _as_list(anti.get("biomes"))

        out = {
            # core
            "presets": presets,
            "rarity": e.get("bucket"),
            "weight": e.get("weight"),
            "levels": e.get("level"),
            "contexts": contexts,
            "times": times,
            "biomeTags": _compact_dict({"include": inc_tags, "exclude": exc_tags}),
            "source": e.get("_source"),
        }

        # optional: only attach if present & meaningful
        key_item = cond.get("key_item")
        if key_item:
            out["keyItem"] = key_item

        nearby_sel = _as_list(cond.get("neededNearbyBlocks"))
        if nearby_sel:
            maybe_resolved = _resolve_blocks_if_useful(nearby_sel)
            nb = {"selectors": nearby_sel}
            if maybe_resolved:
                nb["resolved"] = maybe_resolved
            out["nearbyBlocks"] = nb

        structures = _as_list(cond.get("structures") or cond.get("structure"))
        if structures:
            out["structures"] = structures

        sky = {k: cond.get(k) for k in ("canSeeSky", "minSkyLight", "maxSkyLight")}
        sky = _compact_dict(sky)
        if sky:
            out["sky"] = sky

        weather = {k: cond.get(k) for k in ("isRaining", "isThundering")}
        weather = _compact_dict(weather)
        if weather:
            out["weather"] = weather

        ylev = {"minY": cond.get("minY") or cond.get("minYLevel"),
                "maxY": cond.get("maxY") or cond.get("maxYLevel")}
        ylev = _compact_dict(ylev)
        if ylev:
            out["yLevel"] = ylev

        # Final compaction to drop any leftover empties
        out = _compact_dict(out)
        result.append(out)

    return result

# ------------------------- Sprites (images from resourcepacks & mods) -------------------------
SPRITES_OUT = ROOT / "out/sprites.json"
SPRITES_DIR = ROOT / "out/sprites"

def iter_resourcepacks():
    rp = ROOT / "resourcepacks"
    if rp.is_dir():
        # folders
        for p in rp.iterdir():
            if p.is_dir():
                yield ("dir", p)
            elif p.suffix.lower() in (".zip", ".jar"):
                yield ("zip", p)

def _parse_leading_dexnum(base_name: str):
    # e.g. "019_rattata" -> 19
    import re
    m = re.match(r"^0*(\d{1,4})[_-]?", base_name.lower())
    return int(m.group(1)) if m else None

def _is_pokemon_sprite_path(path_str: str) -> bool:
    s = path_str.replace("\\", "/").lower()
    if not s.endswith(".png") or "/assets/" not in s or "/textures/" not in s:
        return False

    # Accept dCIM/Cobblemon icon path
    if "/textures/entity_icon/" in s:
        return True

    # Accept GUI-based icon paths only if explicitly pokemon/pokedex related
    if "/textures/gui/" in s:
        if any(seg in s for seg in ("/textures/gui/pokemon/",
                                    "/textures/gui/pokedex/",
                                    "/textures/gui/sprites/pokemon/")):
            return True

    # Exclude everything else (esp. generic minecraft GUI/numbered files)
    return False


def _assets_namespace(path_str: str) -> str:
    s = path_str.replace("\\", "/")
    try:
        i = s.index("/assets/")
        rest = s[i+1:].split("/")  # assets/<ns>/...
        return rest[1].lower()
    except Exception:
        return "unknown"

def _match_species_from_filename(base_name: str, species_ids, dex_to_ids, aliases_by_id, id_region):
    """
    Rules:
    - Exact match to species aliases (no arbitrary substrings).
    - Allow a small set of cosmetic trailing suffixes: 'male','female','m','f','shiny'
      (and common 2-suffix combos like 'shinymale', 'shinyf', etc.).
    - If filename contains a region token (hisui/alola/...), only consider ids with that region.
    - Else (no region token): only consider ids with no region (base forms).
    - In the dex-number branch, still require an alias match (never number-only).
    """
    def _norm(s: str) -> str:
        import re
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    # Normalize filename bits
    region_hint = _extract_region_from_name(base_name)          # 'hisui' or None
    name_no_dex = _strip_leading_dex(base_name)                 # 'growlithe_hisui'
    bn = _norm(name_no_dex)                                     # e.g., 'venusaurmale'

    # candidates by region bucket
    if region_hint:
        candidates = [sid for sid in species_ids if id_region.get(sid) == region_hint]
    else:
        candidates = [sid for sid in species_ids if id_region.get(sid) is None]
    if not candidates:
        return None

    # small whitelist of cosmetic suffixes we tolerate at the end of the filename
    SUFF = ("male", "female", "m", "f", "shiny")

    def _alias_matches(a: str, bn: str) -> bool:
        # exact
        if a == bn:
            return True
        # a + one suffix
        for s1 in SUFF:
            if bn == a + s1:
                return True
        # a + two suffixes (e.g., shinymale, malef, etc.)
        for s1 in SUFF:
            for s2 in SUFF:
                if bn == a + s1 + s2:
                    return True
        return False

    # 1) dex-number branch (still require alias match)
    dn = _parse_leading_dexnum(base_name)
    if dn is not None and dn in dex_to_ids:
        cand_dn = [sid for sid in dex_to_ids[dn] if sid in candidates]
        best, best_score = None, -1
        for sid in cand_dn:
            for alias in aliases_by_id.get(sid, []):
                a = _norm(alias)
                if not a or not _alias_matches(a, bn):
                    continue
                # scoring: prefer exact over suffixed; then by alias length
                exact = (a == bn)
                score = (1000 if exact else 0) + len(a)
                if score > best_score:
                    best, best_score = sid, score
        if best:
            return best
        # reject pure number without a matching alias
        return None

    # 2) alias-only branch
    best, best_score = None, -1
    for sid in candidates:
        for alias in aliases_by_id.get(sid, []):
            a = _norm(alias)
            if not a or not _alias_matches(a, bn):
                continue
            exact = (a == bn)
            score = (1000 if exact else 0) + len(a)
            # prefer non-hero/gmax/mega if ambiguous
            sid_suffix = sid.split("_")[-1] if "_" in sid else None
            if sid_suffix in NON_REGIONAL_SUFFIXES and sid_suffix not in bn:
                score -= 500
            if score > best_score:
                best, best_score = sid, score
    return best


def _is_shiny_from_filename(base_name: str) -> bool:
    s = base_name.lower()
    return ("shiny" in s) or s.endswith("_s") or "-s" in s

def _save_zip_png(z, name: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with z.open(name) as f_in, open(out_path, "wb") as f_out:
        f_out.write(f_in.read())

def _save_fs_png(src_path: Path, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(src_path, "rb") as f_in, open(out_path, "wb") as f_out:
        f_out.write(f_in.read())

def collect_sprites(species_dict):
    """
    Returns { species_id: { "normal": [paths...], "shiny": [paths...] } }
    Writes extracted files under ./sprites/<namespace>/file.png
    Priority: resourcepacks override mods.
    """
    sprites = defaultdict(lambda: {"normal": [], "shiny": []})

    # indexes
    species_ids = set(species_dict.keys())
    dex_to_ids = defaultdict(list)            # int -> [species ids]
    aliases_by_id = defaultdict(list)         # id -> [alias strings]
    id_region = {}                            # id -> region suffix (e.g., "hisui") or None

    for sid, js in species_dict.items():
        dn = js.get("nationalPokedexNumber")
        if isinstance(dn, int):
            dex_to_ids[dn].append(sid)

        # detect if this id is a regional form from its id suffix
        sid_parts = sid.split("_")
        region = sid_parts[-1] if sid_parts and sid_parts[-1] in REGIONAL_KEYS else None
        id_region[sid] = region

        display_name = js.get("name") or sid
        al = set()

        # Always include the exact id and its collapsed variant
        al.add(sid)                           # e.g., "growlithe_hisui" or "growlithe"
        al.add(sid.replace("_", ""))

        # Include display name slug(s)
        dn_slug = _norm(display_name)
        if dn_slug:
            al.add(re.sub(r"[^a-z0-9]+", "_", display_name.lower()).strip("_"))
            al.add(dn_slug)

        if region:
            base_id = "_".join(sid_parts[:-1])
            base = base_id
            reg = region

            # Base-first canonical
            al.add(f"{base}_{reg}")
            al.add(f"{base}{reg}")

            # Region-first canonical (e.g., "hisui_growlithe")
            al.add(f"{reg}_{base}")
            al.add(f"{reg}{base}")

            # Adjective synonyms for the region (e.g., "alolan", "hisuian")
            for adj, canon in FORM_SYNONYMS.items():
                if canon == reg:
                    # base-first with adjective
                    al.add(f"{base}_{adj}")
                    al.add(f"{base}{adj}")
                    # adjective-first
                    al.add(f"{adj}_{base}")
                al.add(f"{adj}{base}")

        aliases_by_id[sid] = [a for a in al if a]


    def _register_png(rel_path: Path, sid: str, shiny: bool):
        key = "shiny" if shiny else "normal"
        rel = rel_path.as_posix()
        if rel not in sprites[sid][key]:
            sprites[sid][key].append(rel)

    # 1) resourcepacks
    for kind, pack in iter_resourcepacks():
        if kind == "dir":
            for p in pack.rglob("assets/*/textures/**/*.png"):
                path_str = str(p)
                if not _is_pokemon_sprite_path(path_str): continue
                ns = _assets_namespace(path_str)
                base = p.stem
                sid = _match_species_from_filename(base, species_ids, dex_to_ids, aliases_by_id, id_region)
                if not sid: continue
                shiny = _is_shiny_from_filename(base)
                out_rel = Path("out/sprites") / ns / p.name
                out_abs = ROOT / out_rel
                try:
                    _save_fs_png(p, out_abs)
                    _register_png(out_rel, sid, shiny)
                except Exception:
                    pass
        else:
            try:
                with zipfile.ZipFile(pack) as z:
                    for name in z.namelist():
                        if not _is_pokemon_sprite_path(name): continue
                        ns = _assets_namespace(name)
                        base = Path(name).stem
                        sid = _match_species_from_filename(base, species_ids, dex_to_ids, aliases_by_id, id_region)
                        if not sid: continue
                        shiny = _is_shiny_from_filename(base)
                        out_rel = Path("out/sprites") / ns / Path(name).name
                        out_abs = ROOT / out_rel
                        try:
                            _save_zip_png(z, name, out_abs)
                            _register_png(out_rel, sid, shiny)
                        except Exception:
                            pass
            except Exception:
                pass

    # 2) mods (jars)
    for jar in iter_mod_jars():
        try:
            with zipfile.ZipFile(jar) as z:
                for name in z.namelist():
                    if not _is_pokemon_sprite_path(name): continue
                    ns = _assets_namespace(name)
                    base = Path(name).stem
                    sid = _match_species_from_filename(base, species_ids, dex_to_ids, aliases_by_id, id_region)
                    if not sid: continue
                    shiny = _is_shiny_from_filename(base)
                    out_rel = Path("out/sprites") / ns / Path(name).name
                    out_abs = ROOT / out_rel
                    if out_abs.exists():
                        _register_png(out_rel, sid, shiny)
                        continue
                    try:
                        _save_zip_png(z, name, out_abs)
                        _register_png(out_rel, sid, shiny)
                    except Exception:
                        pass
        except Exception:
            pass

    return sprites




# ------------------------- Main build -------------------------

def main():
    species, species_sources = collect_species()


    def _sources_for(mon_id: str):
        if mon_id in species_sources:
            return species_sources[mon_id]
        base = mon_id.split("_", 1)[0]
        return species_sources.get(base, [])

    print(f"Total Species: {len(species)}")
    species_full = expand_species_with_forms(species)  # NEW: add form entries
    print(f"Total Expanded Species: {len(species_full)}")
    spawns_by_species = collect_spawns()

    # Sprites (after species are known)
    sprites_map = collect_sprites(species_full)
    SPRITES_OUT.write_text(json.dumps({"images": sprites_map}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {SPRITES_OUT} with sprites for {len(sprites_map)} species")


    # Reference datasets
    preset_map = collect_presets()
    biome_tag_map = collect_biome_tags()

    # Resolved biome tags + all concrete biomes
    resolved_biome_map = { tag: resolve_biome_selectors(values, biome_tag_map) for tag, values in biome_tag_map.items() }
    all_biomes = sorted({ b for lst in resolved_biome_map.values() for b in lst if ":" in b and not b.startswith("#") })

    # Block tags (NEW) + resolved + inventory
    block_tag_map = collect_block_tags()
    resolved_block_map = { tag: resolve_block_selectors(values, block_tag_map) for tag, values in block_tag_map.items() }
    all_blocks = sorted({ b for lst in resolved_block_map.values() for b in lst if ":" in b and not b.startswith("#") })

    # Enrich presets with resolved blocks under a "resolved" key
    enriched_presets = {}
    for name, base in preset_map.items():
        resolved_section = {
            "conditions": _resolved_blocks_subset(base.get("conditions", {}), block_tag_map),
            "anticonditions": _resolved_blocks_subset(base.get("anticonditions", {}), block_tag_map),
        }
        enriched_presets[name] = { **base, "resolved": resolved_section }

    # Build per-mon JSON files + a LEAN dex index
    dex_index = []
    _added_ids = set()

    items_to_mons = defaultdict(lambda: {})  # item_id -> { mon_id: {id,name,percentage,quantityRange} }


    for sid, sdata in species_full.items():
        if sid in _added_ids:
            continue
        if _filter_species(sid):
            continue
        _added_ids.add(sid)

        base_id = sdata.get("variantOf")
        raw_spawns_list = spawns_by_species.get(sid, [])
        if not raw_spawns_list and base_id:
            raw_spawns_list = spawns_by_species.get(base_id, [])

        # NEW: extract spawn-sourced drops
        spawn_drop_objs = []
        for raw in raw_spawns_list:
            for s in raw.get("spawns", []):
                extracted = _extract_drops_from_spawn(s)
                if extracted:
                    spawn_drop_objs.append(extracted)

        # NEW: merge species-level drops with spawn-level drops
        merged_drops = _merge_drops(sdata.get("drops") or {}, spawn_drop_objs)

        # --- aggregate drops for the global index (using merged drops now) ---
        for ent in merged_drops.get("entries", []):
            item = (ent.get("item") or "").strip().lower()
            if not item:
                continue
            prev = items_to_mons[item].get(sid)
            curr = {
                "id": sid,
                "name": sdata.get("name", sid),
                "percentage": ent.get("percentage"),
                "quantityRange": ent.get("quantityRange"),
                # You *can* keep biome metadata here if you want later filtering:
                # "biomes": ent.get("biomes"),
            }
            if ent.get("biomes"):
                curr["biomes"] = ent["biomes"]
            if ent.get("excludeBiomes"):
                curr["exclusiveBiomes"] = ent["excludeBiomes"]
            if not prev or (curr["percentage"] is not None and prev.get("percentage") is None):
                items_to_mons[item][sid] = curr

        # keep your spawn flattening (for the UI spawn tab), unchanged:
        spawn_entries = []
        for raw in raw_spawns_list:
            flattened = flatten_spawn_entry_linked(raw, block_tag_map)
            if flattened == []:
                continue
            spawn_entries.append(flattened)
        
        no_spawns = []
        if len(spawn_entries) == 0:
            no_spawns.append(sid)

        # Optionally include sprite refs
        images = {}
        if isinstance(sprites_map, dict):
            images = sprites_map.get(sid) or (sprites_map.get(base_id) if base_id else {}) or {}

        mon = {
            "id": sid,
            "dexnum": sdata.get("nationalPokedexNumber", ""),
            "name": sdata.get("name", sid),
            "primaryType": sdata.get("primaryType", ""),
            "secondaryType": sdata.get("secondaryType", ""),
            "maleRatio": sdata.get("maleRatio", ""),
            "labels": sdata.get("labels", []),
            "abilities": sdata.get("abilities", []),
            "eggGroups": sdata.get("eggGroups", []),
            "baseStats": sdata.get("baseStats", {}),
            "evYield": sdata.get("evYield", {}),
            "experienceGroup": sdata.get("experienceGroup", ""),
            "catchRate": sdata.get("catchRate", ""),
            # ⟵ NEW: assign merged drops here
            "drops": merged_drops,
            "moves": sdata.get("moves", []),
            "forms": [f.get("name") for f in sdata.get("forms", [])] if isinstance(sdata.get("forms"), list) else [],
            "types": sdata.get("types", []),
            "evolutions": sdata.get("evolutions", []),
            "spawns": spawn_entries,
            "implemented": sdata.get("implemented", False),
            "images": images,
            "speciesSources": _sources_for(sid)
        }

        # Write one file per mon (unchanged)
        (MONS_DIR / f"{sid}.json").write_text(
            json.dumps(mon, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Keep the lean dex index as-is...
        dex_index.append({
            "id": mon["id"],
            "name": mon["name"],
            "dexnum": mon["dexnum"],
            "primaryType": mon["primaryType"],
            "secondaryType": mon["secondaryType"],
            "spawnCount": len(spawn_entries)
        })
    
    DEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    DEX_OUT.write_text(json.dumps(dex_index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {DEX_OUT} with {len(dex_index)} entries")

    # turn { item: {monId: {...}} } into { items: [{ item, mons: [...] }, ...] }
    drops_index = {
        "items": [
            {
                "item": item,
                "mons": sorted(list(mdict.values()), key=lambda m: (m["name"], m["id"]))
            }
            for item, mdict in sorted(items_to_mons.items(), key=lambda kv: kv[0])
        ]
    }

    DROPS_OUT.parent.mkdir(parents=True, exist_ok=True)
    DROPS_OUT.write_text(json.dumps(drops_index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {DROPS_OUT} with {len(drops_index['items'])} items")

    # Write the unchanged reference files
    PRESETS_OUT.write_text(json.dumps(enriched_presets, ensure_ascii=False, indent=2), encoding="utf-8")
    BIOMES_OUT.write_text(json.dumps({
        "tags": biome_tag_map,
        "resolved": resolved_biome_map,
        "all_biomes": all_biomes
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    BLOCKS_OUT.write_text(json.dumps({
        "tags": block_tag_map,
        "resolved": resolved_block_map,
        "all_blocks": all_blocks
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Build a sources map aligned to FINAL ids in the lean index
    src_out = {}
    for entry in dex_index:
        sid = entry["id"]
        if sid in species_sources:
            src_out[sid] = species_sources[sid]
        else:
            base = sid.split("_", 1)[0]
            if base in species_sources:
                src_out[sid] = species_sources[base]
            else:
                src_out[sid] = []

    SPECIES_SOURCES_OUT.write_text(json.dumps(src_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {SPECIES_SOURCES_OUT} with {len(src_out)} species")

    print(f"Wrote per-mon files to {MONS_DIR}")
    print(f"Wrote {PRESETS_OUT} with {len(enriched_presets)} presets (with resolved blocks)")
    print(f"Wrote {BIOMES_OUT} with {len(biome_tag_map)} biome tags and {len(all_biomes)} concrete biomes")
    print(f"Wrote {BLOCKS_OUT} with {len(block_tag_map)} block tags and {len(all_blocks)} concrete blocks")


if __name__ == "__main__":
    main()
