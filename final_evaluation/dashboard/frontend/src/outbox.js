// A local recovery buffer for in-progress drafts, keyed by participant + study + task +
// material/rubric hash. The SERVER is the authority (PROTOCOL.md section 10) -- this
// exists only so a closed tab, a crashed browser, or a dropped connection does not lose
// what someone typed before the next successful autosave. It never stores session
// tokens or access codes, and is cleared on logout (see App.jsx's logout handler).
const DB_NAME = 'fe_outbox'
const STORE = 'drafts'

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'key' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function keyFor(participantId, assignmentId) {
  return `${participantId}:${assignmentId}`
}

export async function saveLocalDraft(participantId, assignmentId, payload) {
  try {
    const db = await openDb()
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).put({ key: keyFor(participantId, assignmentId), payload, savedAt: Date.now() })
      tx.oncomplete = resolve
      tx.onerror = () => reject(tx.error)
    })
  } catch {
    // IndexedDB unavailable (private mode, storage blocked) -- the server autosave still
    // works; this is only the extra local recovery buffer, so failing quietly is correct.
  }
}

export async function loadLocalDraft(participantId, assignmentId) {
  try {
    const db = await openDb()
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly')
      const req = tx.objectStore(STORE).get(keyFor(participantId, assignmentId))
      req.onsuccess = () => resolve(req.result ? req.result.payload : null)
      req.onerror = () => reject(req.error)
    })
  } catch {
    return null
  }
}

export async function clearLocalDraft(participantId, assignmentId) {
  try {
    const db = await openDb()
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).delete(keyFor(participantId, assignmentId))
      tx.oncomplete = resolve
      tx.onerror = () => reject(tx.error)
    })
  } catch { /* see saveLocalDraft */ }
}

// Called on logout: remove every locally-buffered draft for THIS participant only, so a
// shared machine cannot show the next person who logs in a prior participant's draft.
export async function clearAllForParticipant(participantId) {
  try {
    const db = await openDb()
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.openCursor()
      req.onsuccess = () => {
        const cursor = req.result
        if (!cursor) return
        if (String(cursor.value.key).startsWith(`${participantId}:`)) cursor.delete()
        cursor.continue()
      }
      tx.oncomplete = resolve
      tx.onerror = () => reject(tx.error)
    })
  } catch { /* see saveLocalDraft */ }
}
