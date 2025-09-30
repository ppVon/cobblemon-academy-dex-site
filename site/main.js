import {
  createApp,
  ref,
  reactive,
  computed,
  onMounted,
  provide, // ⟵ add
} from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import DexList from "./components/DexList.js";
import MonPage from "./components/MonPage.js";
import PresetPage from "./components/PresetPage.js";
import BiomePage from "./components/BiomePage.js";
import DropsPage from "./components/DropsPage.js";
import { parseRoute } from "./utils/helpers.js";

createApp({
  components: { DexList, MonPage, PresetPage, BiomePage, DropsPage },
  setup() {
    const dex = ref([]); // now a lean index
    const presets = ref({});
    const biomes = ref({ tags: {}, resolved: {}, all_biomes: [] });
    const sprites = ref({ images: {} });
    const dropsIndex = ref({ items: [] });
    const dropItems = computed(() => dropsIndex.value?.items ?? []);
    const loading = ref(true);
    const error = ref(null);
    const route = reactive(parseRoute());

    // NEW: simple per-mon cache + loader
    const monCache = reactive(new Map());
    const fetchJson = async (url) => {
      const r = await fetch(url);
      if (!r.ok) throw new Error("Failed to load " + url);
      return r.json();
    };
    const getMon = async (id) => {
      if (monCache.has(id)) return monCache.get(id);
      const data = await fetchJson(`./out/mons/${id}.json`);
      monCache.set(id, data);
      return data;
    };

    const currentView = computed(() => {
      const v = route.view;
      if (v === "mon") return "MonPage";
      if (v === "preset" || v === "presets") return "PresetPage";
      if (v === "biome" || v === "biomes") return "BiomePage";
      if (v === "drops") return "DropsPage";
      return "DexList";
    });

    const loadAll = async () => {
      try {
        const [d, p, b, s, di] = await Promise.all([
          fetchJson("./out/dex.json"), // ⟵ moved to /out
          fetchJson("./out/presets.json").catch(() => ({})), // ⟵ moved to /out
          fetchJson("./out/biomes.json").catch(() => ({
            tags: {},
            resolved: {},
            all_biomes: [],
          })), // ⟵ moved to /out
          fetchJson("./out/sprites.json").catch(() => ({ images: {} })), // ⟵ moved to /out
          fetchJson("./out/drops_index.json").catch(() => ({ items: [] })), // NEW
        ]);
        dex.value = d;
        presets.value = p;
        biomes.value = b;
        sprites.value = s;
        dropsIndex.value = di; // NEW
        console.log("[main] dropsIndex loaded:", dropsIndex.value.items.length);
      } catch (e) {
        error.value = String(e.message || e);
      } finally {
        loading.value = false;
      }
    };

    // make loader available to children (MonPage)
    provide("getMon", getMon);
    provide("monCache", monCache);

    onMounted(async () => {
      await loadAll();
      // optional: prefetch current mon if landing directly on a mon route
      if (route.view === "mon" && route.params?.id) {
        getMon(route.params.id).catch(() => {});
      }
      window.addEventListener("hashchange", () => {
        Object.assign(route, parseRoute());
        if (route.view === "mon" && route.params?.id) {
          getMon(route.params.id).catch(() => {});
        }
      });
    });

    return {
      dex,
      presets,
      biomes,
      sprites,
      dropsIndex,
      dropItems,
      loading,
      error,
      route,
      currentView,
      // optionally expose to components via props if you prefer props over provide/inject:
      getMon,
      monCache,
    };
  },
}).mount("#app");
