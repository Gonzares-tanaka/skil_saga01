// Explicit suspend only. Normal GUILD saves keep their existing localStorage key.
// A readwrite transaction compares and consumes one record atomically across tabs.
(() => {
  const database = 'skill_seekers_suspend_v1';
  const storeName = 'checkpoint';
  window.sparkSuspendStore = {
    start(operation, payload) {
      const job = { done: false, result: null, error: '' };
      let db = null, tx = null, reason = '', timer;
      const finish = (result, error = '') => {
        if (job.done) return;
        job.result = result; job.error = error; job.done = true;
        clearTimeout(timer);
        if (db) db.close();
      };
      timer = setTimeout(() => {
        reason = '中断用の保存領域が応答しません';
        if (tx) {
          // If commit already won, abort throws and oncomplete is queued.
          // Let that event report success; never call a committed consume a
          // failure after its checkpoint has already been deleted.
          try { tx.abort(); } catch (_) { /* Completion/abort will settle the job. */ }
          return;
        }
        finish(null, reason);
      }, 10000);
      try {
        if (!['exists', 'read', 'write', 'consume'].includes(operation)) throw new Error('operation');
        const request = indexedDB.open(database, 1);
        request.onupgradeneeded = () => request.result.createObjectStore(storeName);
        request.onerror = () => finish(null, '中断用の保存領域を開けません');
        request.onblocked = () => finish(null, '別のタブが中断用の保存領域を使用中です');
        request.onsuccess = () => {
          db = request.result;
          if (job.done) { db.close(); return; }
          try {
            tx = db.transaction(storeName, ['write', 'consume'].includes(operation) ? 'readwrite' : 'readonly');
            const store = tx.objectStore(storeName);
            let result = true;
            tx.oncomplete = () => finish(result);
            tx.onerror = () => { reason ||= '中断データを処理できません'; };
            tx.onabort = () => finish(null, reason || '中断データを処理できません');
            if (operation === 'write') {
              if (typeof payload !== 'string') throw new Error('payload');
              store.put(payload, 'current');
            } else {
              const read = store.get('current');
              read.onsuccess = () => {
                try {
                  const raw = read.result;
                  if (operation === 'exists') result = typeof raw === 'string';
                  else if (typeof raw !== 'string') {
                    reason = '中断データがありません'; tx.abort();
                  } else if (operation === 'read') result = raw;
                  else if (raw !== payload) {
                    reason = '中断データが変更されました'; tx.abort();
                  } else store.delete('current');
                } catch (_) {
                  reason = '中断データを消去できません';
                  try { tx.abort(); } catch (_) { finish(null, reason); }
                }
              };
            }
          } catch (_) {
            if (tx) { try { tx.abort(); } catch (_) {} }
            finish(null, '中断データを処理できません');
          }
        };
      } catch (_) { finish(null, '中断用の保存領域を使用できません'); }
      return job;
    }
  };
})();
