<script setup>
defineProps({
    activeView: String
})

const emit = defineEmits(['change-view'])

const menus = [
    { key: 'test', label: '影像检测' },
    { key: 'patient', label: '患者信息' },
    { key: 'history', label: '操作记录' },
    { key: 'profile', label: '个人中心' }
]


</script>



<template>
    <header class="header">
        <div class="brand">医学影像分类原型</div>
        <nav class="nav">
            <button v-for="menu in menus" :key="menu.key" :class="{ active: activeView === menu.key }"
                @click="$emit('change-view', menu.key)">
                {{ menu.label }}
            </button>
        </nav>
    </header>


</template>


<style scoped>
.header {
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 30px;
  border-bottom: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: var(--shadow-sm);
}

.brand {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
}

.nav {
  display: flex;
  gap: 6px;
}

button {
  min-width: 92px;
  height: 38px;
  padding: 0 14px;
  border: 1px solid transparent;
  background: transparent;
  color: #334155;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease;
}

button:hover {
  background: var(--color-surface-soft);
  border-color: var(--color-border);
}

button.active {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-color: var(--color-primary-border);
  font-weight: 600;
}

@media (max-width: 1200px) {
  .header {
    padding: 0 20px;
  }

  button {
    min-width: 80px;
    padding: 0 10px;
  }
}
</style>
