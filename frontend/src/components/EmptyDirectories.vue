<script setup>
import { ref } from "vue";
import { postJson } from "../api";
import ErrorList from "./ErrorList.vue";
import StatusMessage from "./StatusMessage.vue";
import ToolHeader from "./ToolHeader.vue";

const path = ref("");
const scanning = ref(false);
const deleting = ref(false);
const hasScanned = ref(false);
const scanToken = ref("");
const directories = ref([]);
const errors = ref([]);
const status = ref({ message: "", kind: "info" });

async function scan() {
  scanning.value = true;
  hasScanned.value = false;
  scanToken.value = "";
  directories.value = [];
  errors.value = [];
  status.value = { message: "正在递归扫描目录…", kind: "info" };
  try {
    const data = await postJson("api/empty-directories/scan", { path: path.value });
    scanToken.value = data.scan_token;
    directories.value = data.directories;
    errors.value = data.errors;
    hasScanned.value = true;
    status.value = { message: "", kind: "info" };
  } catch (error) {
    status.value = { message: error.message, kind: "error" };
  } finally {
    scanning.value = false;
  }
}

async function removeDirectories() {
  if (!scanToken.value) return;
  const confirmed = window.confirm(
    `确定删除扫描结果中的 ${directories.value.length} 个空文件夹吗？扫描根目录永远不会被删除。`,
  );
  if (!confirmed) return;

  deleting.value = true;
  status.value = { message: "正在重新检查并删除空文件夹…", kind: "info" };
  try {
    const data = await postJson("api/empty-directories/delete", {
      scan_token: scanToken.value,
    });
    scanToken.value = "";
    directories.value = data.deleted;
    errors.value = data.errors;
    status.value = {
      message: `已删除 ${data.deleted_count} 个空文件夹。`,
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
    icon="⌫"
    title="删除空文件夹"
    description="递归查找空目录，包括删除子目录后也会变空的父目录。"
  />

  <section class="panel">
    <form @submit.prevent="scan">
      <label for="empty-path">扫描目录</label>
      <div class="input-row">
        <input
          id="empty-path"
          v-model.trim="path"
          type="text"
          placeholder="/mnt/storage/photos"
          autocomplete="off"
          required
        />
        <button class="button primary" type="submit" :disabled="scanning || deleting">
          {{ scanning ? "扫描中…" : "开始扫描" }}
        </button>
      </div>
      <p class="hint">只能访问 ALLOWED_ROOTS 配置的目录；不会跟随 symbolic link。</p>
    </form>
  </section>

  <StatusMessage :message="status.message" :kind="status.kind" />

  <section v-if="hasScanned" class="panel results-panel">
    <div class="result-title">
      <div>
        <h2>扫描结果</h2>
        <p>
          {{ directories.length ? `发现 ${directories.length} 个空文件夹。` : "没有发现空文件夹。" }}
        </p>
      </div>
      <button
        v-if="scanToken && directories.length"
        class="button danger"
        type="button"
        :disabled="deleting"
        @click="removeDirectories"
      >
        {{ deleting ? "删除中…" : "确认删除" }}
      </button>
    </div>

    <ErrorList :errors="errors" />
    <ul v-if="directories.length" class="path-list">
      <li v-for="directory in directories" :key="directory">{{ directory }}</li>
    </ul>
  </section>
</template>
