<script setup>
defineProps({ icon: String, title: String, description: String });
</script>

<template>
  <a class="back-link" href="#/">← 返回工具箱</a>
  <section class="page-heading">
    <span class="tool-icon large">{{ icon }}</span>
    <div>
      <h1>{{ title }}</h1>
      <p>{{ description }}</p>
    </div>
  </section>
</template>
