import { ref, watch } from 'vue'

/** Eenvoudig vs technisch. Module-level so every component reads the same flag
 *  without prop drilling — the toggle lives in the header, the things it hides
 *  live five levels down. Persisted because a technical visitor who flips it on
 *  should not have to flip it again after every reload. */
const STORAGE_KEY = 'normnet.expert'

const expert = ref(readStored())

watch(expert, (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
  } catch {
    // Private-mode Safari throws on write. The toggle still works for this
    // session; only persistence is lost.
  }
})

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function useViewMode() {
  return { expert }
}
