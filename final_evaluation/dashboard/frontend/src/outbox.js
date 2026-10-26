// Local backup of unsaved drafts. The server stays authoritative.
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
      tx.objectStore(STORE).put({
        key: keyFor(participantId, assignmentId),
        payload,
        savedAt: Date.now(),
      })
      tx.oncomplete = resolve
      tx.onerror = () => reject(tx.error)
    })
  } catch {}
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
  } catch {}
}

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
  } catch {}
}
