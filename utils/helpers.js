export const REGION_SYNONYMS = {
  alola: "alola",
  alolan: "alola",
  galar: "galar",
  galarian: "galar",
  hisui: "hisui",
  hisuian: "hisui",
  paldea: "paldea",
  paldean: "paldea",
  kanto: "kanto",
  kantonian: "kanto",
};

export const asList = (x) => (Array.isArray(x) ? x : x != null ? [x] : []);
export const flatSpawns = (sp) =>
  asList(sp.spawns).flatMap((a) => (Array.isArray(a) ? a : [a]));

export const splitMove = (m) => {
  const s = String(m).trim();
  const [head, tail = ""] = s.split(":", 2);
  const h = head.trim();
  const isAllDigits =
    h.length > 0 && [...h].every((ch) => ch >= "0" && ch <= "9");
  if (isAllDigits)
    return { kind: "level", name: `${parseInt(h, 10)} ${tail.trim()}` };
  const k = h.toLowerCase();
  if (k === "egg" || k === "tm" || k === "tutor")
    return { kind: k, name: tail.trim() };
  if (!s.includes(":")) return { kind: "other", name: s };
  return { kind: "other", name: tail.trim() || s };
};

export const groupMoves = (list) => {
  const out = { level: [], egg: [], tm: [], tutor: [], other: [] };
  for (const m of list || []) {
    const { kind, name } = splitMove(m);
    if (out[kind]) out[kind].push(name);
    else out.other.push(name || String(m));
  }
  out.level.sort((a, b) => {
    const la = parseInt(String(a), 10),
      lb = parseInt(String(b), 10);
    if (!isNaN(la) && !isNaN(lb) && la !== lb) return la - lb;
    return String(a).localeCompare(String(b));
  });
  return out;
};

// works with a ref OR a plain object
export const spriteFrom = (spritesMaybeRef, id, shiny = false) => {
  const root = spritesMaybeRef && (spritesMaybeRef.value || spritesMaybeRef);
  const m = root?.images?.[id];
  const arr = shiny ? m?.shiny || [] : m?.normal || [];
  return arr && arr[0] ? arr[0] : null;
};

const _norm = (s) =>
  String(s || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");

export const normalizeResultId = (result, dex) => {
  if (!result) return "";
  let s = String(result).toLowerCase().trim();
  s = s
    .replace(/mega\s*=\s*true/g, "")
    .replace(/\s+/g, " ")
    .trim();
  const tokens = s
    .split(/[^a-z0-9]+/g)
    .filter(Boolean)
    .map((t) => REGION_SYNONYMS[t] || t);
  if (!tokens.length) return "";
  let candidate = tokens[0];
  const last = tokens[tokens.length - 1];
  if (REGION_SYNONYMS[last])
    candidate = `${tokens[0]}_${REGION_SYNONYMS[last]}`;
  if (dex.some((d) => d.id === candidate)) return candidate;
  const nameHit = dex.find((d) => _norm(d.name) === _norm(result));
  if (nameHit) return nameHit.id;
  const base = tokens[0];
  const alt = dex.find((d) => d.id === base || d.id.startsWith(base + "_"));
  return alt ? alt.id : candidate;
};

export const evolRequirementLabel = (req) => {
  if (!req || typeof req !== "object") return "";
  const v = req.variant || "";
  if (v === "level") {
    const min = req.minLevel ?? req.level ?? "?";
    const time = req.timeRange ? ` @ ${req.timeRange}` : "";
    return `Level ${min}${time}`;
  }
  if (v === "has_move") return `Know ${req.move || "a move"}`;
  if (v === "has_move_type") return `Know ${req.type || "a type"} move`;
  if (v === "held_item")
    return `Hold ${req.item || req.itemCondition || "item"}`;
  if (v === "weather") return `${req.weather || "weather"}`;
  if (v === "friendship") return `Friendship ${req.min || req.amount || ""}`;
  if (v === "time_range") return `Time ${req.range}`;
  return v.replace(/_/g, " ");
};

export const parseRoute = () => {
  const hash = location.hash.replace(/^#\/?/, "").trim();
  const [view = "dex", param = ""] = hash.split("/");
  return { view: view.toLowerCase(), param: decodeURIComponent(param) };
};
