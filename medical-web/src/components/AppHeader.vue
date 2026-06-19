<script setup>
defineProps({
    activeView: String
})

const emit = defineEmits(['change-view'])

const menus = [
    { key: 'test', label: '影像检测' },
    { key: 'patient', label: '患者信息' },
    { key: 'history', label: '检测记录' },
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
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}

.brand {
  font-weight: 700;
  color: #111827;
}

.nav {
  display: flex;
  gap: 4px;
}

button {
  min-width: 88px;
  height: 36px;
  padding: 0 12px;
  border: 1px solid transparent;
  background: transparent;
  color: #374151;
  cursor: pointer;
}

button:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

button.active {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #93c5fd;
}
</style>
