import {
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  watch,
} from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { spriteFrom } from "../utils/helpers.js";

export default {
  props: ["dex", "sprites"],
  setup(props) {
    const q = ref("");
    const type = ref("");
    const noSpawnsOnly = ref(false); // hidden filter flag

    const types = computed(() => {
      const set = new Set();
      for (const sp of props.dex) {
        if (sp.primaryType) set.add(sp.primaryType);
        if (sp.secondaryType) set.add(sp.secondaryType);
      }
      return [...set].sort((a, b) => a.localeCompare(b));
    });

    // --- Hidden URL param support: #/<path>?nos=1
    const parseNosFromHash = () => {
      const hash = location.hash.startsWith("#")
        ? location.hash.slice(1)
        : location.hash;
      const [, qs = ""] = hash.split("?");
      const sp = new URLSearchParams(qs);
      const v = (sp.get("nos") || "").toLowerCase();
      return v === "1" || v === "true" || v === "yes";
    };
    const setHashParam = (key, value) => {
      const hash = location.hash.startsWith("#")
        ? location.hash.slice(1)
        : location.hash;
      const [path, qs = ""] = hash.split("?");
      const sp = new URLSearchParams(qs);
      if (!value) sp.delete(key);
      else sp.set(key, "1");
      const qstr = sp.toString();
      location.hash = `#${path}${qstr ? "?" + qstr : ""}`;
    };

    // initialize from hash (optional)
    onMounted(() => {
      try {
        noSpawnsOnly.value = parseNosFromHash();
      } catch {}
    });
    // keep URL in sync (optional)
    watch(noSpawnsOnly, (v) => setHashParam("nos", v), { flush: "post" });

    // --- Keyboard toggle: press "N"
    let keyHandler = null;
    onMounted(() => {
      keyHandler = (e) => {
        const tag = (document.activeElement?.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea" || e.isComposing) return;
        if (
          e.key?.toLowerCase() === "n" &&
          !e.metaKey &&
          !e.ctrlKey &&
          !e.altKey
        ) {
          noSpawnsOnly.value = !noSpawnsOnly.value;
        }
      };
      window.addEventListener("keydown", keyHandler);
    });
    onBeforeUnmount(() => {
      if (keyHandler) window.removeEventListener("keydown", keyHandler);
    });

    const filtered = computed(() =>
      props.dex
        .filter((sp) =>
          (sp.name || sp.id).toLowerCase().includes(q.value.toLowerCase())
        )
        .filter(
          (sp) =>
            !type.value ||
            sp.primaryType === type.value ||
            sp.secondaryType === type.value
        )
        .filter((sp) => !noSpawnsOnly.value || (sp.spawnCount ?? 0) === 0)
        .sort((a, b) => (a.dexnum ?? 9999) - (b.dexnum ?? 9999))
    );

    const goto = (sp) => (location.hash = `#/mon/${encodeURIComponent(sp.id)}`);
    const sprite = (id) => spriteFrom(props.sprites, id);

    return { q, type, types, noSpawnsOnly, filtered, goto, sprite };
  },
  template: `
    <section class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <input v-model="q" type="search" placeholder="Search name…" class="rounded-xl border-slate-300 focus:border-indigo-500 focus:ring-indigo-500" />
        <select v-model="type" class="rounded-xl border-slate-300">
          <option value="">Any type</option>
          <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
        </select>

        <!-- Hidden toggle: Alt-click the counter, or press "N" -->
        <div
          class="text-sm text-slate-600 md:justify-self-end md:text-right select-none"
          @click.alt="noSpawnsOnly = !noSpawnsOnly"
          :title="'Alt-click to toggle No Spawns • Press N. Currently: ' + (noSpawnsOnly ? 'ON' : 'OFF')"
          aria-live="polite"
        >
          {{ filtered.length }} / {{ dex.length }} shown
          <span v-if="noSpawnsOnly" class="ml-2 inline-block px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 align-middle">
            No spawns
          </span>
        </div>
      </div>

      <ul class="divide-y divide-slate-200 bg-white rounded-2xl ring-1 ring-slate-200">
        <li
          v-for="sp in filtered"
          :key="sp.id"
          class="p-3 flex items-center gap-3 hover:bg-slate-50 cursor-pointer"
          @click="goto(sp)"
        >
          <img v-if="sprite(sp.id)" :src="sprite(sp.id)" loading="lazy" class="h-8 w-8 shrink-0 rounded bg-slate-100 ring-1 ring-slate-200" alt="" />
          <div class="w-16 text-slate-500 font-mono">#{{ sp.dexnum ?? '—' }}</div>
          <div class="flex-1">
            <div class="font-semibold">{{ sp.name }}</div>
            <div class="text-sm text-slate-600 flex gap-2">
              <span v-if="sp.primaryType" class="px-2 py-0.5 rounded-full bg-slate-200">{{ sp.primaryType }}</span>
              <span v-if="sp.secondaryType" class="px-2 py-0.5 rounded-full bg-slate-200">{{ sp.secondaryType }}</span>
              <span class="px-2 py-0.5 rounded-full" :class="(sp.spawnCount ?? 0) === 0 ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'">
                spawns {{ sp.spawnCount ?? 0 }}
              </span>
            </div>
          </div>
          <span class="text-indigo-700 text-sm">View →</span>
        </li>
      </ul>
    </section>
  `,
};
