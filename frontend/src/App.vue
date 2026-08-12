<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import Dashboard from "./components/Dashboard.vue";
import DuplicateFiles from "./components/DuplicateFiles.vue";
import EmptyDirectories from "./components/EmptyDirectories.vue";

const route = ref(window.location.hash.slice(1) || "/");

function updateRoute() {
  route.value = window.location.hash.slice(1) || "/";
}

onMounted(() => window.addEventListener("hashchange", updateRoute));
onBeforeUnmount(() => window.removeEventListener("hashchange", updateRoute));

const currentComponent = computed(() => {
  if (route.value === "/empty-directories") return EmptyDirectories;
  if (route.value === "/duplicates") return DuplicateFiles;
  return Dashboard;
});
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <a class="brand" href="#/">
        <span class="brand-mark">N</span>
        <span>NAS Toolbox</span>
      </a>
      <span class="connection-badge"><i></i> NAS 文件工具</span>
    </header>

    <main class="container">
      <component :is="currentComponent" />
    </main>

    <footer>NAS Toolbox · 轻量、可控的 NAS 文件工具</footer>
  </div>
</template>
