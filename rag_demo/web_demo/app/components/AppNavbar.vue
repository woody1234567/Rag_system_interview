<script setup lang="ts">
const items = [{
  label: 'Home',
  to: '/',
  icon: 'i-lucide-house'
}]
</script>

<template>
  <nav class="border-b border-(--ui-border) h-16 flex items-center px-4 md:px-8 bg-(--ui-bg)">
    <div class="container mx-auto flex items-center justify-between">
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-bold bg-linear-to-r from-blue-600 to-teal-500 bg-clip-text text-transparent">
          RAG System Demo
        </h1>
        <UNavigationMenu :items="items" orientation="horizontal" variant="pill" />
      </div>
      
      <div class="flex items-center gap-2">
        <UColorModeButton />
        <UButton
          to="https://github.com/woody1234567/Rag_system_interview"
          target="_blank"
          icon="i-simple-icons-github"
          variant="ghost"
          color="neutral"
        />
      </div>
    </div>
  </nav>
</template>
