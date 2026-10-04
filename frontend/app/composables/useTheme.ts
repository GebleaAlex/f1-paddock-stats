// Light/dark theme: follows the OS until the visitor picks one, which is remembered in localStorage.
export type ThemeMode = 'light' | 'dark'

const mode = ref<ThemeMode>('light')
let started = false

function systemMode(): ThemeMode {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function stored(): ThemeMode | null {
  try {
    const v = localStorage.getItem('theme')
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

export function useTheme() {
  if (import.meta.client && !started) {
    started = true
    mode.value = stored() ?? systemMode()
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (!stored()) mode.value = systemMode()
    })
  }
  function toggle() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = mode.value
    try {
      localStorage.setItem('theme', mode.value)
    } catch {
      /* private mode: the choice lasts for this page only */
    }
  }
  return { mode: readonly(mode), toggle }
}

/** A computed chart option that is rebuilt when the theme changes (chart colours are read from CSS tokens). */
export function useChartOption<T>(build: () => T) {
  const { mode } = useTheme()
  return computed(() => {
    void mode.value
    return build()
  })
}
