import {
  inject,
  ref,
  computed,
  onMounted,
  watch,
} from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import {
  groupMoves,
  flatSpawns,
  spriteFrom,
  normalizeResultId,
  evolRequirementLabel,
} from "../utils/helpers.js";

export default {
  // keep props so DexList/route/sprites still flow in
  props: ["dex", "sprites", "route"],
  setup(props) {
    // NEW: per-mon loader + cache from main.js (provided via provide/inject)
    const getMon = inject("getMon"); // async (id) -> full mon json
    const monCache = inject("monCache"); // Map(), optional but useful

    const mon = ref(null);
    const loadingMon = ref(true);
    const loadErr = ref(null);

    const currentId = () =>
      (props.route?.params && props.route.params.id) ||
      props.route?.param ||
      null;

    const load = async () => {
      const id = currentId();
      if (!id) {
        mon.value = null;
        loadingMon.value = false;
        loadErr.value = null;
        return;
      }
      loadingMon.value = true;
      loadErr.value = null;
      try {
        mon.value = await getMon(id);
      } catch (e) {
        mon.value = null;
        loadErr.value = e?.message || String(e);
      } finally {
        loadingMon.value = false;
      }
    };

    const back = () =>
      history.length > 1 ? history.back() : (location.hash = "#/dex");
    const goPreset = (p) =>
      (location.hash = `#/preset/${encodeURIComponent(p)}`);
    const goBiome = (t) => (location.hash = `#/biome/${encodeURIComponent(t)}`);
    const goMon = (id) =>
      id && (location.hash = "#/mon/" + encodeURIComponent(id));

    const sprite = (id) => spriteFrom(props.sprites, id);
    const reqLabel = evolRequirementLabel;

    // Use your index (props.dex) for evolution target lookup (id → name),
    // while sprites come from spriteFrom and full data stays in mon.value
    const evolutions = computed(() => {
      const m = mon.value;
      if (!m) return [];
      return (m.evolutions || []).map((ev) => {
        const tid = normalizeResultId(ev.result, props.dex);
        const target = props.dex.find((x) => x.id === tid) || null; // index has {id,name,...}
        return {
          ...ev,
          _targetId: tid,
          _target: target,
          _sprite: tid ? sprite(tid) : null,
        };
      });
    });

    // Small helpers for labels
    const titleize = (s) =>
      String(s || "")
        .split("_")
        .join(" ");
    const ratioText = (r) => (r == null || r === "" ? "" : String(r));

    onMounted(load);
    watch(
      () => props.route && (props.route.params?.id ?? props.route.param),
      load
    );

    const isBiomeReq = (req) =>
      req?.variant === "biome" &&
      (req.biome || req.biomeCondition || req.biomeAnticondition);

    const biomeId = (req) =>
      req.biome || req.biomeCondition || req.biomeAnticondition || "";

    const biomeReal = (req) => {
      const biome = biomeId(req);
      const [mod, tag] = biome.split(":");
      const splits = tag.split("/");
      const last_segment = splits[splits.length - 1];
      return mod + ":" + last_segment;
    };

    const biomeHref = (req) => `#/biome/${encodeURIComponent(biomeReal(req))}`;

    const biomeShort = (req) => {
      const id = biomeId(req);
      return id.includes(":") ? id.split(":")[1] : id;
    };

    const biomePrefix = (req) => (req.biomeAnticondition ? "Not in" : "In");

    // For non-interactive labels (everything that's not a biome chip)
    const evolRequirementText = (req) => {
      if (!req || typeof req !== "object") return "";
      switch (req.variant) {
        case "level": {
          const min = req.minLevel ?? req.level ?? "?";
          const time = req.timeRange ? ` @ ${req.timeRange}` : "";
          return `Level ${min}${time}`;
        }
        case "has_move":
          return `Know ${req.move || "a move"}`;
        case "has_move_type":
          return `Know ${req.type || "a type"} move`;
        case "held_item":
          return `Hold ${req.item || req.itemCondition || "item"}`;
        case "weather":
          return `${req.weather || "weather"}`;
        case "friendship":
          return `Friendship ${req.min || req.amount || ""}`;
        case "time_range":
          return `Time ${req.range}`;
        default:
          return String(req.variant || "").replace(/_/g, " ");
      }
    };

    return {
      mon,
      loadingMon,
      loadErr,
      back,
      goPreset,
      goBiome,
      goMon,
      groupMoves,
      flatSpawns,
      sprite,
      evolutions,
      reqLabel,
      titleize,
      ratioText,
      isBiomeReq,
      evolRequirementText,
      evolRequirementLabel,
      biomeHref,
      biomePrefix,
      biomeShort,
    };
  },

  template: `
    <section v-if="loadingMon" class="space-y-4">
      <button class="text-sm text-indigo-700 hover:underline" @click="back">← Back</button>
      <p class="text-slate-600">Loading…</p>
    </section>

    <section v-else-if="mon" class="space-y-4">
      <button class="text-sm text-indigo-700 hover:underline" @click="back">← Back</button>

      <header class="flex items-start gap-3">
        <img v-if="sprite(mon.id)" :src="sprite(mon.id)" class="h-16 w-16 rounded bg-slate-100 ring-1 ring-slate-200" alt="" />
        <div>
          <h2 class="text-2xl font-bold">#{{ mon.dexnum }} — {{ mon.name }}</h2>
          <div class="mt-1 text-sm text-slate-600 flex flex-wrap gap-2">
            <span v-if="mon.primaryType" class="px-2 py-0.5 rounded-full bg-slate-200">{{ mon.primaryType }}</span>
            <span v-if="mon.secondaryType" class="px-2 py-0.5 rounded-full bg-slate-200">{{ mon.secondaryType }}</span>
            <span v-if="mon.maleRatio!=null && mon.maleRatio!==''" class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">♂/♀ {{ ratioText(mon.maleRatio) }}</span>
            <span v-for="lab in (mon.labels||[])"
                  :key="lab"
                  class="px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
              {{ lab }}
            </span>
          </div>
          <div class="mt-1 text-xs text-slate-500 flex gap-3">
            <span v-if="mon.experienceGroup">XP Group: {{ titleize(mon.experienceGroup) }}</span>
            <span v-if="mon.catchRate!=='' && mon.catchRate!=null">Catch Rate: {{ mon.catchRate }}</span>
          </div>
        </div>
      </header>

      <!-- Quick info grid -->
      <section class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        <div class="rounded-lg border p-2">
          <h4 class="font-semibold mb-1">Abilities</h4>
          <div class="flex flex-wrap gap-1">
            <span v-for="ab in (mon.abilities||[])" :key="ab" class="px-2 py-0.5 rounded-full bg-slate-200">{{ ab }}</span>
          </div>
        </div>
        <div class="rounded-lg border p-2">
          <h4 class="font-semibold mb-1">Egg Groups</h4>
          <div class="flex flex-wrap gap-1">
            <span v-for="eg in (mon.eggGroups||[])" :key="eg" class="px-2 py-0.5 rounded-full bg-slate-200">{{ eg }}</span>
          </div>
        </div>

        <div class="rounded-lg border p-2">
          <h4 class="font-semibold mb-1">Base Stats</h4>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-1">
            <div v-for="(v,k) in (mon.baseStats||{})" :key="k" class="flex justify-between">
              <span class="capitalize">{{ titleize(k) }}</span>
              <span class="font-mono">{{ v }}</span>
            </div>
          </div>
        </div>

        <div class="rounded-lg border p-2">
          <h4 class="font-semibold mb-1">EV Yield</h4>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-1">
            <div v-for="(v,k) in (mon.evYield||{})" :key="k" class="flex justify-between">
              <span class="capitalize">{{ titleize(k) }}</span>
              <span class="font-mono">{{ v }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Drops -->
      <section v-if="mon.drops && (mon.drops.entries?.length || mon.drops.amount!=null)" class="rounded-lg border p-2 text-sm">
        <h4 class="font-semibold mb-1">Drops</h4>
        <div v-if="mon.drops.amount!=null" class="text-slate-600">Avg amount: {{ mon.drops.amount }}</div>
        <ul v-if="mon.drops.entries?.length" class="mt-1 list-disc list-inside">
          <li v-for="d in mon.drops.entries" :key="d.item">
            {{ d.item }}
            <span v-if="d.quantityRange"> — {{ d.quantityRange }}</span>
            <span v-if="d.percentage!=null"> — {{ d.percentage }}%</span>
            <span v-if="d.biomes && d.biomes.length" class="text-xs text-slate-600">— in {{ d.biomes.join(', ') }}</span>
            <span v-if="d.excludeBiomes && d.excludeBiomes.length" class="text-xs text-slate-600">— not in {{ d.excludeBiomes.join(', ') }}</span>
          </li>
        </ul>
      </section>

      <!-- Moves -->
      <details class="rounded-lg border p-2">
        <summary class="cursor-pointer font-semibold">Moves</summary>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mt-2">
          <div>
            <h5 class="font-semibold mb-1">Level-up</h5>
            <ul class="list-disc list-inside">
              <li v-for="m in groupMoves(mon.moves).level" :key="'lvl-'+m">{{ m }}</li>
            </ul>
          </div>
          <div>
            <h5 class="font-semibold mb-1">Egg</h5>
            <ul class="list-disc list-inside">
              <li v-for="m in groupMoves(mon.moves).egg" :key="'egg-'+m">{{ m }}</li>
            </ul>
          </div>
          <div>
            <h5 class="font-semibold mb-1">TM</h5>
            <ul class="list-disc list-inside">
              <li v-for="m in groupMoves(mon.moves).tm" :key="'tm-'+m">{{ m }}</li>
            </ul>
          </div>
          <div>
            <h5 class="font-semibold mb-1">Tutor</h5>
            <ul class="list-disc list-inside">
              <li v-for="m in groupMoves(mon.moves).tutor" :key="'tutor-'+m">{{ m }}</li>
            </ul>
          </div>
        </div>
      </details>

      <!-- Evolutions -->
      <section v-if="evolutions.length" class="space-y-2">
        <h4 class="font-semibold">Evolutions</h4>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <a v-for="(e,i) in evolutions"
            :key="i"
            :href="e._targetId ? '#/mon/'+encodeURIComponent(e._targetId) : '#/dex'"
            @click.prevent="goMon(e._targetId)"
            class="rounded-lg border p-2 bg-white hover:shadow transition">
            <div class="flex items-center gap-3">
              <img v-if="e._sprite" :src="e._sprite" class="h-10 w-10 rounded bg-slate-100 ring-1 ring-slate-200" alt="" />
              <div class="flex-1">
                <div class="font-semibold">{{ e._target?.name || e.result }}</div>
                <div class="text-xs text-slate-600">
                  {{ e.variant }}<span v-if="e.requiredContext"> • {{ e.requiredContext }}</span>
                </div>

                <!-- requirements (chips) -->
                <div class="mt-1 flex flex-wrap gap-1">
                  <template
                    v-for="r in (Array.isArray(e.requirements) ? e.requirements : [e.requirements]).filter(Boolean)"
                    :key="JSON.stringify(r)"
                  >
                    <!-- biome: clickable chip that doesn't bubble to parent -->
                    <a
                      v-if="isBiomeReq(r)"
                      :href="biomeHref(r)"
                      @click.stop
                      class="px-2 py-0.5 rounded-full hover:underline"
                      :class="r.biomeAnticondition ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'"
                    >
                      {{ biomePrefix(r) }} {{ biomeShort(r) }}
                    </a>

                    <!-- everything else: plain text chip -->
                    <span
                      v-else
                      class="px-2 py-0.5 rounded-full bg-slate-200 text-slate-800"
                    >
                      {{ evolRequirementText(r) }}
                    </span>
                  </template>
                </div>
              </div>
            </div>
          </a>
        </div>
      </section>

      <!-- Spawns -->
      <section class="space-y-2">
        <h4 class="font-semibold">Spawns</h4>

        <div
          v-for="(d, i) in flatSpawns(mon)"
          :key="i"
          class="rounded-lg border p-2 text-sm"
        >
          <div class="flex flex-col items-end mb-2 mt-1">
            <span v-if="d.source" class="text-s text-slate-500 break-all">{{ d.source }}</span>
          </div>
          <div class="flex flex-wrap gap-2 items-center justify-between">
            <!-- chips: presets / contexts / times -->
            <div class="flex flex-wrap gap-1">
              <a
                v-for="p in (d.presets || [])"
                :key="p"
                @click.prevent="goPreset(p)"
                :href="'#/preset/' + encodeURIComponent(p)"
                class="px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 hover:underline"
              >
                {{ p }}
              </a>
              <span
                v-for="c in (d.contexts || [])"
                :key="c"
                class="px-2 py-0.5 rounded-full bg-slate-200"
              >
                {{ c }}
              </span>
              <span
                v-for="t in (d.times || [])"
                :key="t"
                class="px-2 py-0.5 rounded-full bg-slate-200"
              >
                {{ t }}
              </span>
            </div>

            <!-- right side: rarity (top) + source (below) -->
            <div class="flex flex-col items-end">
              <span class="text-md text-slate-600">{{ d.rarity || '—' }}</span>
            </div>
          </div>

          <!-- biome tags -->
          <div class="mt-4 flex flex-wrap gap-1 items-center justify-between">
            <div class="flex flex-wrap gap-1">
              <a
                v-for="b in ((d.biomeTags && d.biomeTags.include) || [])"
                :key="'i' + b"
                @click.prevent="goBiome(b)"
                :href="'#/biome/' + encodeURIComponent(b)"
                class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 hover:underline"
              >
                {{ b }}
              </a>
              <a
                v-for="b in ((d.biomeTags && d.biomeTags.exclude) || [])"
                :key="'e' + b"
                @click.prevent="goBiome(b)"
                :href="'#/biome/' + encodeURIComponent(b)"
                class="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 hover:underline"
              >
                not {{ b }}
              </a>
            </div>

          </div>
          <div class="mt-1 flex flex-wrap gap-1 items-center justify-between">
            <div v-if="d.keyItem" class="mt-2 flex flex-wrap">
              <span class="px-3 py-0.5 rounded-full bg-red-700">item:{{ d.keyItem }}</span>
            </div>
          </div>
        </div>
      </section>

      <details class="rounded-lg border p-2">
        <summary class="cursor-pointer font-semibold">Sources</summary>
        <ul class="list-disc list-inside">
          <li v-for="(source, i) in mon.speciesSources" :key="i">
            {{ source }}
          </li>
        </ul>
      </details>
    </section>

    
    <section v-else>
      <button class="text-sm text-indigo-700 hover:underline" @click="back">← Back</button>
      <p v-if="loadErr" class="text-rose-700 mt-2">Failed to load: {{ loadErr }}</p>
      <p v-else class="text-slate-600">Not found. <a class="text-indigo-700 hover:underline" href="#/dex">Back to dex</a>.</p>
    </section>
  `,
};
