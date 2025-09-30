import { computed } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { flatSpawns } from "../utils/helpers.js";

export default {
  props: ["dex", "biomes", "route"],
  setup(props) {
    const tag = computed(() => props.route.param || "");
    const allTags = computed(() => Object.keys(props.biomes.tags || {}).sort());
    const resolved = computed(
      () => (props.biomes.resolved || {})[tag.value] || []
    );
    const rawVals = computed(() => (props.biomes.tags || {})[tag.value] || []);
    const usedBy = computed(() =>
      props.dex.filter((sp) =>
        flatSpawns(sp).some(
          (d) =>
            (d.biomeTags?.include || []).includes(tag.value) ||
            (d.biomeTags?.exclude || []).includes(tag.value)
        )
      )
    );
    const back = () =>
      history.length > 1 ? history.back() : (location.hash = "#/biome");
    return { tag, allTags, resolved, rawVals, usedBy, back };
  },
  template: `
    <section>
      <div v-if="!tag">
        <h2 class="text-xl font-semibold mb-3">Biome Tags</h2>
        <div class="flex flex-wrap gap-2">
          <a v-for="b in allTags" :key="b" :href="'#/biome/'+encodeURIComponent(b)" class="px-2 py-1 rounded-lg bg-emerald-100 text-emerald-700 hover:underline">{{ b }}</a>
        </div>
      </div>
      <div v-else>
        <button class="text-sm text-indigo-700 hover:underline" @click="back">← Back</button>
        <h2 class="text-xl font-semibold mt-2">Biome tag: {{ tag }}</h2>
        <div class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div class="rounded-lg border p-2"><h3 class="font-semibold mb-1">Raw values</h3><pre class="text-xs whitespace-pre-wrap">{{ JSON.stringify(rawVals, null, 2) }}</pre></div>
          <div class="rounded-lg border p-2"><h3 class="font-semibold mb-1">Resolved biomes</h3><pre class="text-xs whitespace-pre-wrap">{{ JSON.stringify(resolved, null, 2) }}</pre></div>
        </div>
      </div>
    </section>
  `,
};
