<script setup>
import { ref } from 'vue'
import AppHeader from './components/AppHeader.vue'
import TestView from './views/TestView.vue'
import PatientInfoView from './views/PatientInfoView.vue'
import HistoryView from './views/HistoryView.vue'
import ProfileView from './views/ProfileView.vue'


const activeView = ref('test')
</script>

<template>
  <AppHeader :active-view="activeView" @change-view="activeView = $event" />
  <main class="main">
    <TestView v-show="activeView === 'test'" />
    <PatientInfoView v-show="activeView === 'patient'" />
    <HistoryView v-show="activeView === 'history'" />
    <ProfileView v-show="activeView === 'profile'" />
  </main>

</template>
<style scoped>
.main {
  flex: 1;
  padding: 18px 30px 28px;
  overflow-x: hidden;
}

@media (max-width: 1200px) {
  .main {
    padding: 16px 20px 24px;
  }
}
</style>
