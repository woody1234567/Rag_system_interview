<template>
  <footer class="border-t border-(--ui-border) py-8 bg-(--ui-bg)">
    <div class="container mx-auto px-4 md:px-8">
      <div class="flex flex-col md:flex-row justify-between items-center gap-4">
        <div class="text-sm text-(--ui-text-muted)">
          &copy; {{ new Date().getFullYear() }} studywithwoody. All rights reserved.
        </div>
        <div class="flex items-center gap-4">
          <ULink to="https://studywithwoody.site" class="text-sm text-(--ui-text-muted) hover:text-(--ui-primary)">more about studywithwoody</ULink>
        </div>
      </div>
    </div>
  </footer>
</template>
