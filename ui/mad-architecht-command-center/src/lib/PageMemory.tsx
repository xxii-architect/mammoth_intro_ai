import { createContext, useCallback, useContext, useMemo, useRef, useSyncExternalStore } from 'react'
import type { Dispatch, ReactNode, SetStateAction } from 'react'

type Entry = { value: unknown; listeners: Set<() => void> }
type Store = Map<string, Entry>
const PageMemory = createContext<Store | null>(null)

export function PageMemoryProvider({ owner, children }: { owner: string; children: ReactNode }) {
  const store = useMemo<Store>(() => new Map(), [owner])
  return <PageMemory.Provider value={store}>{children}</PageMemory.Provider>
}

export function useForgetPageMemory() {
  const store = useContext(PageMemory)
  return useCallback((prefixes: string[]) => {
    if (!store) return
    for (const key of store.keys()) {
      if (prefixes.some(prefix => key.startsWith(prefix))) store.delete(key)
    }
  }, [store])
}

/** Tab-lifetime memory only. Unmounted pages stop their effects, not their data. */
export function usePageMemory<T>(key: string, initial: T | (() => T)): [T, Dispatch<SetStateAction<T>>] {
  const shared = useContext(PageMemory)
  const fallback = useRef<Store>(new Map())
  const store = shared || fallback.current
  if (!store.has(key)) {
    store.set(key, { value: typeof initial === 'function' ? (initial as () => T)() : initial, listeners: new Set() })
  }
  const entry = store.get(key)!
  const subscribe = useCallback((listener: () => void) => {
    entry.listeners.add(listener)
    return () => { entry.listeners.delete(listener) }
  }, [entry])
  const read = useCallback(() => entry.value as T, [entry])
  const value = useSyncExternalStore(subscribe, read, read)
  const update = useCallback<Dispatch<SetStateAction<T>>>(next => {
    entry.value = typeof next === 'function' ? (next as (previous: T) => T)(entry.value as T) : next
    entry.listeners.forEach(listener => listener())
  }, [entry])
  return [value, update]
}
