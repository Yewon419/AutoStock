<script setup lang="ts">
defineProps<{ ticker: string }>()
</script>

<template>
  <RouterLink :to="`/market/${ticker}`" class="stock-link">
    <slot>{{ ticker }}</slot>
  </RouterLink>
</template>

<style scoped>
.stock-link {
  color: inherit;
  text-decoration: none;
  cursor: pointer;
  transition: color 0.12s ease;
}
.stock-link:hover {
  color: #60a5fa;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.stock-link:focus-visible {
  outline: 2px solid #60a5fa;
  outline-offset: 2px;
  border-radius: 2px;
}
</style>
