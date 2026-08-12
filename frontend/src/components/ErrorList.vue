<script setup>
defineProps({ errors: { type: Array, default: () => [] } });
</script>

<template>
  <div v-if="errors.length" class="error-box">
    <strong>{{ errors.length }} 个项目处理失败或被跳过</strong>
    <ul>
      <li v-for="error in errors" :key="error">{{ error }}</li>
    </ul>
  </div>
</template>
