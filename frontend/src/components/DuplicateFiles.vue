<script setup>
import { computed, ref } from "vue";
import { formatBytes, postJson } from "../api";
import ErrorList from "./ErrorList.vue";
import StatusMessage from "./StatusMessage.vue";
import ToolHeader from "./ToolHeader.vue";

const strategies = [
  {
    value: "exact",
    title: "精确文件重复",
    description: "先按大小筛选，再计算流式 MD5；仅识别字节完全相同的文件。",
    badge: "最安全",
  },
  {
    value: "audio_pcm",
    title: "PCM 音频内容",
    description: "忽略 WAV/FLAC 容器标签，对解码后的音频内容计算 SHA-256。",
    badge: "高可信",
  },
  {
    value: "audio_similar",
    title: "相似音频",
    description: "使用 Chromaprint 查找可能是同一首歌的不同编码或母带版本。",
    badge: "人工确认",
  },
  {
    value: "filename",
    title: "同名文件",
    description: "忽略文件名大小写，查找不同目录下名称相同的文件。",
    badge: "人工确认",
  },
];

const path = ref("");
const strategy = ref("exact");
const scanning = ref(false);
const deleting = ref(false);
const result = ref(null);
const scanToken = ref("");
const selections = ref({});
const errors = ref([]);
const status = ref({ message: "", kind: "info" });

const selectedStrategy = computed(() =>
  strategies.find((item) => item.value === strategy.value),
);

const deletableCount = computed(() =>
  result.value?.groups.reduce(
    (total, group) => total + group.files.length - 1,
    0,
  ) || 0,
);

const selectedReclaimableBytes = computed(() =>
  result.value?.groups.reduce((total, group) => {
    const keepPath = selections.value[group.id];
    return (
      total +
      group.files.reduce(
        (groupTotal, file) =>
          groupTotal + (file.path === keepPath ? 0 : file.size),
        0,
      )
    );
  }, 0) || 0,
);

function scanMessage() {
  if (strategy.value === "audio_pcm") return "正在分析音频参数并计算 PCM 哈希…";
  if (strategy.value === "audio_similar") return "正在生成 Chromaprint 音频指纹…";
  if (strategy.value === "filename") return "正在查找不同目录中的同名文件…";
  return "正在按文件大小筛选并计算候选文件 MD5…";
}

async function scan() {
  scanning.value = true;
  result.value = null;
  scanToken.value = "";
  selections.value = {};
  errors.value = [];
  status.value = { message: scanMessage(), kind: "info" };
  try {
    const data = await postJson("api/duplicates/scan", {
      path: path.value,
      strategy: strategy.value,
    });
    result.value = data;
    scanToken.value = data.scan_token;
    errors.value = data.errors;
    selections.value = Object.fromEntries(
      data.groups.map((group) => [group.id, group.files[0].path]),
    );
    status.value = { message: "", kind: "info" };
  } catch (error) {
    status.value = { message: error.message, kind: "error" };
  } finally {
    scanning.value = false;
  }
}

async function removeDuplicates() {
  if (!scanToken.value || !result.value) return;
  const reviewWarning = ["audio_similar", "filename"].includes(result.value.strategy)
    ? "\n\n注意：该策略不能证明文件内容完全相同，请确认每一组的保留文件。"
    : "";
  const confirmed = window.confirm(
    `将保留每组所选文件，并删除其余 ${deletableCount.value} 个文件，预计释放 ${formatBytes(selectedReclaimableBytes.value)}。确定继续吗？删除前会重新验证文件。${reviewWarning}`,
  );
  if (!confirmed) return;

  deleting.value = true;
  status.value = { message: "正在重新验证文件并删除副本…", kind: "info" };
  try {
    const data = await postJson("api/duplicates/delete", {
      scan_token: scanToken.value,
      selections: result.value.groups.map((group) => ({
        group_id: group.id,
        keep_path: selections.value[group.id],
      })),
    });
    scanToken.value = "";
    errors.value = data.errors;
    status.value = {
      message: `已删除 ${data.deleted_count} 个文件，释放 ${formatBytes(data.reclaimed_bytes)}。`,
      kind: "success",
    };
  } catch (error) {
    status.value = { message: error.message, kind: "error" };
  } finally {
    deleting.value = false;
  }
}
</script>

<template>
  <ToolHeader
    icon="≡"
    title="重复文件检测"
    description="按文件内容、音频内容、听感或文件名选择扫描策略。"
  />

  <section class="panel">
    <form @submit.prevent="scan">
      <label for="duplicate-path">扫描目录</label>
      <div class="input-row">
        <input
          id="duplicate-path"
          v-model.trim="path"
          type="text"
          placeholder="/mnt/photos"
          autocomplete="off"
          required
        />
        <button class="button primary" type="submit" :disabled="scanning || deleting">
          {{ scanning ? "扫描中…" : "开始扫描" }}
        </button>
      </div>

      <fieldset class="strategy-fieldset">
        <legend>检测策略</legend>
        <div class="strategy-grid">
          <label
            v-for="item in strategies"
            :key="item.value"
            class="strategy-option"
            :class="{ selected: strategy === item.value }"
          >
            <input v-model="strategy" type="radio" name="strategy" :value="item.value" />
            <span class="strategy-copy">
              <span class="strategy-title">
                {{ item.title }}
                <small>{{ item.badge }}</small>
              </span>
              <span>{{ item.description }}</span>
            </span>
          </label>
        </div>
      </fieldset>

      <p class="hint">
        {{ selectedStrategy.description }} 大目录和音频策略可能需要较长时间；扫描不会自动删除文件。
      </p>
    </form>
  </section>

  <StatusMessage :message="status.message" :kind="status.kind" />

  <section v-if="result" class="results-panel">
    <div
      v-if="['audio_similar', 'filename'].includes(result.strategy)"
      class="review-warning"
    >
      <strong>需要人工确认</strong>
      此结果只代表音频相似或文件名相同，不代表内容完全一致。不同专辑、母带和同名文件可能都应保留。
    </div>

    <div class="stats">
      <div class="stat-card"><strong>{{ result.scanned_files }}</strong><span>扫描文件</span></div>
      <div class="stat-card"><strong>{{ result.duplicate_groups }}</strong><span>匹配文件组</span></div>
      <div class="stat-card"><strong>{{ result.duplicate_files }}</strong><span>可选文件</span></div>
      <div class="stat-card"><strong>{{ formatBytes(selectedReclaimableBytes) }}</strong><span>按当前选择可释放</span></div>
    </div>

    <p class="analysis-summary">
      检测方式：<strong>{{ result.strategy_label }}</strong> · 深度分析 {{ result.analyzed_files }} 个文件
    </p>

    <ErrorList :errors="errors" />

    <div class="result-title results-toolbar">
      <div>
        <h2>匹配文件组</h2>
        <p>{{ result.groups.length ? "每组请选择一个要保留的文件。" : "没有发现匹配文件。" }}</p>
      </div>
      <button
        v-if="scanToken && result.groups.length"
        class="button danger"
        type="button"
        :disabled="deleting"
        @click="removeDuplicates"
      >
        {{ deleting ? "删除中…" : "确认删除其余文件" }}
      </button>
    </div>

    <section
      v-for="(group, groupIndex) in result.groups"
      :key="group.id"
      class="duplicate-group panel"
    >
      <div class="group-heading">
        <div>
          <h3>匹配组 {{ groupIndex + 1 }}</h3>
          <span class="confidence" :class="group.confidence">
            {{ group.confidence === "exact" ? "精确一致" : group.confidence === "high" ? "高可信" : "人工确认" }}
          </span>
        </div>
        <span>{{ group.detail }}</span>
      </div>
      <label v-for="file in group.files" :key="file.path" class="file-choice">
        <input
          v-model="selections[group.id]"
          type="radio"
          :name="group.id"
          :value="file.path"
        />
        <span class="file-path">{{ file.path }}</span>
        <small>{{ formatBytes(file.size) }}</small>
      </label>
    </section>
  </section>
</template>
