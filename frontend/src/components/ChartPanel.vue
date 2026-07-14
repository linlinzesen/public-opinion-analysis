<template>
  <section class="panel">
    <div class="panel__header">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="subtitle">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </div>
    <div class="panel__body" :style="{ minHeight }">
      <slot />
    </div>
  </section>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  },
  minHeight: {
    type: String,
    default: '320px'
  }
})
</script>
