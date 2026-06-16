<script setup>
import { ref } from 'vue'
import AppHeader from './components/AppHeader.vue'
import TestView from './views/TestView.vue'
import UserInfoView from './views/UserInfoView.vue'
import HistoryView from './views/HistoryView.vue'
import ProfileView from './views/ProfileView.vue'


const activeView = ref('test')


</script>

<template>
  <AppHeader
  :active-view="activeView"
  @change-view="activeView=$event"
  />
  <main class="main">
    <TestView v-if="activeView === 'test'" />
    <UserInfoView v-else-if="activeView === 'user'" />
    <HistoryView v-else-if="activeView === 'history'" />
    <ProfileView v-else-if="activeView === 'profile'" />
  </main>

</template>
<style scoped>

.main {
  flex: 1;
  padding: 16px 28px 24px;
  overflow-x: hidden;
}

</style>