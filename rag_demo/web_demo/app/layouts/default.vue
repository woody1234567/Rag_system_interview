<template>
  <div class="min-h-screen flex flex-col bg-(--ui-bg)">
    <AppNavbar />
    
    <main class="flex-1 py-10">
      <UContainer>
        <slot />
      </UContainer>
    </main>

    <AppFooter />
  </div>
</template>

<style>
/* Custom transitions or global styles can go here */
body {
  @apply antialiased text-(--ui-text);
}
</style>
