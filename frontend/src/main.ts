import "./style.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query"
import App from "./App.vue"
import router from "./router"
import i18n from "./locales"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.use(i18n)
app.use(VueQueryPlugin, { queryClient })
app.mount("#app")
