import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../views/HomePage.vue'
import BaseModelPage from '../views/BaseModelPage.vue'
import DesignPatentPage from '../views/DesignPatentPage.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomePage
  },
  {
    path: '/base',
    name: 'base',
    component: BaseModelPage
  },
  {
    path: '/design',
    name: 'design',
    component: DesignPatentPage
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
