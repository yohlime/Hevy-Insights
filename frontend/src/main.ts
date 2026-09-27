import "./style.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import { QueryCache, QueryClient, VueQueryPlugin } from "@tanstack/vue-query"
import App from "./App.vue"
import router from "./router"
import i18n from "./locales"

function statusOf(error: unknown): number | undefined {
  return (error as { response?: { status?: number } })?.response?.status
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      // Session expired / not authenticated: drop cached data and go to login.
      if (statusOf(error) === 401) {
        queryClient.clear()
        router.push("/login")
      }
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      // Retry transient/server errors once, but never retry client errors (4xx).
      retry: (failureCount, error) => {
        const status = statusOf(error)
        if (status !== undefined && status >= 400 && status < 500) return false
        return failureCount < 1
      },
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
