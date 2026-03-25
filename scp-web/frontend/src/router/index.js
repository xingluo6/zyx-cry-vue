import { createRouter, createWebHistory } from 'vue-router'
import SingleCryptoView   from '@/views/SingleCryptoView.vue'
import CombinedCryptoView from '@/views/CombinedCryptoView.vue'
import BatchView          from '@/views/BatchView.vue'
import DashboardView      from '@/views/DashboardView.vue'
import ImageLibraryView   from '@/views/ImageLibraryView.vue'
import ExperimentView     from '@/views/ExperimentView.vue'

const routes = [
  { path: '/',           name: 'Single',     component: SingleCryptoView   },
  { path: '/combined',   name: 'Combined',   component: CombinedCryptoView },
  { path: '/library',    name: 'Library',    component: ImageLibraryView   },
  { path: '/batch',      name: 'Batch',      component: BatchView          },
  { path: '/dashboard',  name: 'Dashboard',  component: DashboardView      },
  { path: '/experiment', name: 'Experiment', component: ExperimentView     },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
