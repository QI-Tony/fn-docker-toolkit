<script setup>
defineProps({
  message: { type: String, default: "" },
  kind: { type: String, default: "info" },
});
</script>

<template>
  <div v-if="message" class="status" :class="kind" role="status">
    <span v-if="kind === 'info'" class="spinner"></span>
    {{ message }}
  </div>
</template>
