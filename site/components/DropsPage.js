import {
  ref,
  computed,
  onMounted,
} from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { spriteFrom } from "../utils/helpers.js"; // <- adjust path if your utils live elsewhere

export default {
  name: "DropsPage",
  props: {
    dropItems: { type: Array, default: () => [] }, // [{ item, mons:[{id,name,percentage,quantityRange,biomes,excludeBiomes}] }]
    sprites: { type: Object, default: () => ({ images: {} }) }, // NEW
    route: { type: Object, default: () => ({}) },
  },
  setup(props) {
    const q = ref("");
    const page = ref(1);
    const pageSize = ref(25);

    const normalizeItemName = (id) => {
      if (!id) return "";
      const parts = id.split(":");
      const name = parts.length > 1 ? parts[1] : parts[0];
      return name.replace(/_/g, " ");
    };

    const needle = computed(() => q.value.trim().toLowerCase());

    const filtered = computed(() => {
      const n = needle.value;
      if (!n) return props.dropItems;
      return props.dropItems.filter((it) => {
        const simple = normalizeItemName(it.item).toLowerCase();
        return (
          it.item.toLowerCase().includes(n) || simple.includes(n)
          /*
          ||
          it.mons?.some?.((m) =>
            (m.name || m.id || "").toLowerCase().includes(n)
          )
          */
        );
      });
    });

    const normalized = computed(() =>
      filtered.value.map((it) => {
        const rows = (it.mons || []).slice().sort((a, b) => {
          const ap = a.percentage ?? -1;
          const bp = b.percentage ?? -1;
          if (ap !== bp) return bp - ap;
          return (a.name || a.id).localeCompare(b.name || b.id);
        });
        return { ...it, mons: rows };
      })
    );

    const totalPages = computed(() =>
      Math.max(1, Math.ceil(normalized.value.length / pageSize.value))
    );

    const paged = computed(() => {
      const start = (page.value - 1) * pageSize.value;
      return normalized.value.slice(start, start + pageSize.value);
    });

    const goMon = (id) =>
      id && (location.hash = "#/mon/" + encodeURIComponent(id));
    const sprite = (id) => spriteFrom(props.sprites, id); // NEW

    onMounted(() => {
      console.log("[DropsPage] items at mount:", props.dropItems.length);
    });

    const fmtBiomes = (m) => {
      const inc =
        Array.isArray(m.biomes) && m.biomes.length
          ? `in ${m.biomes.join(", ")}`
          : "";
      const exc =
        Array.isArray(m.excludeBiomes) && m.excludeBiomes.length
          ? `not in ${m.excludeBiomes.join(", ")}`
          : "";
      return [inc, exc].filter(Boolean).join(" — ");
    };

    const hasBiomeInfo = (it) =>
      (it.mons || []).some(
        (m) =>
          (m.biomes && m.biomes.length) ||
          (m.excludeBiomes && m.excludeBiomes.length)
      );

    const highlight = (text) => {
      const n = needle.value;
      if (!n) return text;
      const re = new RegExp(
        `(${n.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&")})`,
        "ig"
      );
      return String(text).replace(
        re,
        "<mark class='bg-yellow-200 text-black rounded px-0.5'>$1</mark>"
      );
    };

    return {
      q,
      page,
      pageSize,
      totalPages,
      paged,
      goMon,
      fmtBiomes,
      hasBiomeInfo,
      highlight,
      sprite,
      normalizeItemName,
    };
  },
  template: `
    <section class="space-y-4">
      <!-- Controls -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
        <input v-model="q" type="search" placeholder="Search item or mon…"
               class="rounded-xl border-slate-300 focus:border-indigo-500 focus:ring-indigo-500" />
        <div class="text-sm text-slate-600 md:col-span-2 md:justify-self-end md:text-right">
          Showing {{ paged.length }} of {{ totalPages * pageSize }} (page {{ page }} / {{ totalPages }})
        </div>
      </div>

      <!-- Pagination -->
      <div class="flex items-center gap-2 text-sm">
        <button @click="page = Math.max(1, page-1)" :disabled="page===1"
                class="px-2 py-1 rounded-lg ring-1 ring-slate-300 disabled:opacity-40">Prev</button>
        <select v-model.number="page" class="rounded-lg ring-1 ring-slate-300 px-2 py-1">
          <option v-for="p in totalPages" :key="p" :value="p">{{ p }}</option>
        </select>
        <button @click="page = Math.min(totalPages, page+1)" :disabled="page===totalPages"
                class="px-2 py-1 rounded-lg ring-1 ring-slate-300 disabled:opacity-40">Next</button>

        <div class="ml-auto flex items-center gap-2">
          <span>Per page</span>
          <select v-model.number="pageSize" class="rounded-lg ring-1 ring-slate-300 px-2 py-1">
            <option :value="10">10</option>
            <option :value="25">25</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </div>
      </div>

      <!-- Items -->
      <ul class="space-y-4">
        <li v-for="it in paged" :key="it.item" class="rounded-2xl ring-1 ring-slate-200 overflow-hidden">
          <div class="px-4 py-3 border-b">
            <h3 class="font-semibold">
                <span v-html="highlight(normalizeItemName(it.item))"></span>
                <span class="ml-2 text-slate-500 text-sm" v-html="'(' + it.item + ')'"></span>
            </h3>
           </div>

          <!-- Responsive table wrapper -->
          <div class="overflow-x-auto">
            <table class="min-w-full text-sm">
              <thead class="">
                <tr class="[&>th]:px-4 [&>th]:py-2 text-left">
                  <th style="width: 36%">Mon</th> <!-- wider to fit sprite + names -->
                  <th style="width: 12%">Rate</th>
                  <th style="width: 14%">Range</th>
                  <th v-if="hasBiomeInfo(it)">Biomes</th>
                  <th style="width: 12%">Link</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="m in (it.mons || [])" :key="m.id" class="[&>td]:px-4 [&>td]:py-2">
                  <!-- Mon cell with sprite -->
                  <td class="flex items-center gap-3">
                    <img v-if="sprite(m.id)" :src="sprite(m.id)" loading="lazy" class="h-8 w-8 shrink-0 rounded bg-slate-100 ring-1 ring-slate-200" alt="" />
                    <div>
                      <div class="font-medium" v-html="highlight(m.name || m.id)"></div>
                      <div class="text-xs text-slate-500" v-if="m.id && m.name && m.name !== m.id">{{ m.id }}</div>
                    </div>
                  </td>

                  <td>
                    <span v-if="m.percentage != null">{{ m.percentage }}%</span>
                    <span v-else class="text-slate-400">—</span>
                  </td>

                  <td>
                    <span v-if="m.quantityRange">{{ m.quantityRange }}</span>
                    <span v-else class="text-slate-400">—</span>
                  </td>

                  <td v-if="hasBiomeInfo(it)" class="text-slate-600">
                    <div v-if="m.biomes && m.biomes.length" class="whitespace-pre-wrap">
                      in {{ m.biomes.join(", ") }}
                    </div>
                    <div v-if="m.excludeBiomes && m.excludeBiomes.length" class="text-slate-500 whitespace-pre-wrap">
                      not in {{ m.excludeBiomes.join(", ") }}
                    </div>
                  </td>

                  <td>
                    <button @click="goMon(m.id)"
                      class="px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 ring-1 ring-slate-300">
                      Open
                    </button>
                  </td>
                </tr>

                <tr v-if="(it.mons || []).length === 0">
                  <td colspan="5" class="px-4 py-6 text-center text-slate-500">No matching mons</td>
                </tr>
              </tbody>
            </table>
          </div>
        </li>
      </ul>
    </section>
  `,
};
