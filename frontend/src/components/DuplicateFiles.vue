<script setup>
import { computed, ref } from "vue";
import { formatBytes, postJson } from "../api";
import ErrorList from "./ErrorList.vue";
import StatusMessage from "./StatusMessage.vue";
import ToolHeader from "./ToolHeader.vue";

const path = ref("");
const scanning = ref(false);
const deleting = ref(false);
const result = ref(null);
const scanToken = ref("");
const selections = ref({});
const errors = ref([]);
const status = ref({ message: "", kind: "info" });

const deletableCount = computed(() =>
  result.value?.groups.reduce((total, group) => total + group.files.length - 1, 0) || 0,
);

async function scan() {
  scanning.value = true;
  result.value = null;
  scanToken.value = "";
  selections.value = {};
  errors.value = [];
  status.value = { message: "正在统计文件并计算候选文件 MD5…", kind: "info" };
  try {
    const data = await postJson("api/duplicates/scan", { path: path.value });
    result.value = data;
    scanToken.value = data.scan_token;
    errors.value = data.errors;
    selections.value = Object.fromEntries(
      data.groups.map((group) => [group.id, group.files[0]]),
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
  const confirmed = window.confirm(
    `将保留每组所选文件，并删除其余 ${deletableCount.value} 个副本。确定继续吗？删除前会重新验证内容。`,
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
    description="先按大小筛选候选，再以流式 MD5 验证内容。"
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
      <p class="hint">大目录扫描可能需要一些时间。扫描不会自动删除任何文件。</p>
    </form>
  </section>

  <StatusMessage :message="status.message" :kind="status.kind" />

  <section v-if="result" class="results-panel">
    <div class="stats">
      <div class="stat-card"><strong>{{ result.scanned_files }}</strong><span>扫描文件</span></div>
      <div class="stat-card"><strong>{{ result.duplicate_groups }}</strong><span>重复文件组</span></div>
      <div class="stat-card"><strong>{{ result.duplicate_files }}</strong><span>可删除副本</span></div>
      <div class="stat-card"><strong>{{ formatBytes(result.reclaimable_bytes) }}</strong><span>预计可释放</span></div>
    </div>

    <ErrorList :errors="errors" />

    <div class="result-title results-toolbar">
      <div>
        <h2>重复文件组</h2>
        <p>{{ result.groups.length ? "每组请选择一个要保留的文件。" : "没有发现重复文件。" }}</p>
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
        <h3>重复组 {{ groupIndex + 1 }}</h3>
        <span>{{ formatBytes(group.size) }} · MD5 {{ group.md5 }}</span>
      </div>
      <label v-for="file in group.files" :key="file" class="file-choice">
        <input v-model="selections[group.id]" type="radio" :name="group.id" :value="file" />
        <span>{{ file }}</span>
      </label>
    </section>
  </section>
</template>
