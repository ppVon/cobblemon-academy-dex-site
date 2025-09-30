import { computed } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { flatSpawns } from "../utils/helpers.js";

export default {
  props: ["dex", "presets", "route"],
  setup(props) {
    const name = computed(() => props.route.param || "");
    const preset = computed(() => props.presets[name.value] || null);
    const speciesUsing = computed(() =>
      props.dex.filter((sp) =>
        flatSpawns(sp).some((d) => (d.presets || []).includes(name.value))
      )
    );
    const allNames = computed(() => Object.keys(props.presets || {}).sort());
    const back = () =>
      history.length > 1 ? history.back() : (location.hash = "#/preset");
    return { name, preset, speciesUsing, allNames, back };
  },
  template: `
    <section>
      <div v-if="!name">
        <h2 class="text-xl font-semibold mb-3">Presets</h2>
        <div class="flex flex-wrap gap-2">
          <a v-for="p in allNames" :key="p" :href="'#/preset/'+encodeURIComponent(p)" class="px-2 py-1 rounded-lg bg-indigo-100 text-indigo-700 hover:underline">{{ p }}</a>
        </div>
      </div>
      <div v-else>
        <button class="text-sm text-indigo-700 hover:underline" @click="back">← Back</button>
        <h2 class="text-xl font-semibold mt-2">Preset: {{ name }}</h2>
        <div v-if="preset" class="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div class="rounded-lg border p-2"><h3 class="font-semibold mb-1">Contexts</h3><div class="flex flex-wrap gap-1"><span v-for="c in (preset.contexts||[])" :key="c" class="px-2 py-0.5 rounded-full bg-slate-200">{{ c }}</span></div></div>
          <div class="rounded-lg border p-2 md:col-span-2"><h3 class="font-semibold mb-1">Conditions</h3><pre class="text-xs whitespace-pre-wrap">{{ JSON.stringify(preset.conditions, null, 2) }}</pre></div>
          <div class="rounded-lg border p-2 md:col-span-3"><h3 class="font-semibold mb-1">Anti-conditions</h3><pre class="text-xs whitespace-pre-wrap">{{ JSON.stringify(preset.anticonditions, null, 2) }}</pre></div>
        </div>
      </div>
    </section>
  `,
};
