<script setup>
import { ref, computed, watch } from 'vue'
import AppHeader from './components/AppHeader.vue'
import TestView from './views/TestView.vue'
import PatientInfoView from './views/PatientInfoView.vue'
import HistoryView from './views/HistoryView.vue'
import ProfileView from './views/ProfileView.vue'


const activeView = ref('patient')

const patientName = ref(localStorage.getItem('patientName') || '')
const patientGender = ref(localStorage.getItem('patientGender') || 'MALE')
const patientAge = ref(localStorage.getItem('patientAge') || '')
watch(patientName, value => {
  localStorage.setItem('patientName', value)
})

watch(patientGender, value => {
  localStorage.setItem('patientGender', value)
})

watch(patientAge, value => {
  localStorage.setItem('patientAge', value)
})
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
  padding: 16px 28px 24px;
  overflow-x: hidden;
}
</style>