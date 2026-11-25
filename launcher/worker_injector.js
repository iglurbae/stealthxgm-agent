#!/usr/bin/env node
/**
 * worker_injector.js — CDP worker injector untuk StealthXGM (F6, 2026-11-08).
 *
 * v4 (2026-11-08, F7 attempt 1/3 service worker): RESUME-BEFORE-EVALUATE
 *   di handleAttached. Bukti F7: SW target 350E0863 ter-pause
 *   (waitingForDebugger=true) lalu Runtime.evaluate TIMEOUT 10 detik —
 *   Runtime belum responsif selama worker ter-pause di startup. Perbaikan:
 *   runIfWaitingForDebugger DULU, jeda 150ms (Runtime init), baru inject,
 *   lalu resume lagi best-effort. Trade-off jujur: script top-level SW
 *   sempat jalan beberapa ms tanpa spoof, tapi patch prototype mendarat
 *   sebelum event handler apa pun (install/activate/message) dieksekusi —
 *   handler membaca navigator.* saat event, bukan saat load.
 *   Ini perbaikan umum (semua worker), bukan khusus CreepJS.
 *
 * v3 (2026-11-08): service worker TERBUKTI macet + tidak ter-inject.
 *   Bukti: probe swtest.js — target service_worker ADA di /json/list
 *   (2C7E602E) tapi registrasi tanpa active/installing/waiting, page
 *   hang di `serviceWorker.ready`; Chromium polos: worker yang sama
 *   aktif normal dan merespons. Injector TIDAK pernah log inject untuk
 *   target itu (hanya 2 service worker ekstensi internal Chrome saat
 *   startup). Penyebab paling mungkin: service worker ter-pause oleh
 *   page-session autoAttach (waitForDebuggerOnStart) tapi event
 *   attachedToTarget-nya tidak sampai ke browser session, DAN
 *   Target.targetCreated untuk service worker bisa terlewat (race —
 *   target sudah ada sebelum handler siap). Perbaikan v3:
 *     (a) POLLING Target.getTargets tiap 2 detik — tangkap worker /
 *         shared_worker / service_worker yang belum di-injectedWorkers,
 *         apapun jalur event-nya (menutup race targetCreated).
 *     (b) explicitWorker SELALU memanggil Runtime.runIfWaitingForDebugger
 *         setelah inject (best-effort) — resume worker yang ter-pause;
 *         no-op bila tidak ter-pause. Sebelumnya resume hanya dari
 *         jalur (1), jadi worker yang ter-pause tapi lolos dari (1)
 *         macet selamanya.
 *   Ini perbaikan umum (semua worker), bukan khusus CreepJS.
 *
 *  Service worker dihitung datanya saat menerima message (bukan saat
 *  start), jadi explicit attach punya jendela install→activate untuk
 *  inject. Shared worker + dedicated worker dihitung saat start —
 *  jalur (1) yang menjamin pause sebelum eksekusi.
 *
 *  Worker JS punya guard idempotent (Symbol.for("sxgw")), jadi inject
 *  ganda via kedua jalur aman. Daemon TIDAK memakai browser-level
 *  autoAttach (supaya tidak me-pause page dan tidak balapan dengan
 *  Playwright di level browser).
 *
 * Node >= 22 punya global WebSocket (tidak butuh dependency).
 * Log ke stdout (launcher mengarahkan ke worker_injector.log).
 * Keluar sendiri bila browser mati (watchdog /json/version).
 *
 * Dipakai oleh launcher.py (spawn setelah injector daemon). Bukan untuk
 * dijalankan manual.
 *
 * Usage:
 *   node worker_injector.js --port 19222 --js-file /path/worker_inject.js \
 *       --ready-file /path/worker_ready.json
 */
'use strict';
const fs = require('fs');
const http = require('http');

function log(msg) {
  try {
    process.stdout.write(`[${new Date().toISOString()}] [worker-injector] ${msg}\n`);
  } catch (e) { /* ignore */ }
}

function parseArgs() {
  const a = { port: 0, jsFile: '', readyFile: '' };
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--port') a.port = parseInt(argv[i + 1], 10);
    else if (argv[i] === '--js-file') a.jsFile = argv[i + 1];
    else if (argv[i] === '--ready-file') a.readyFile = argv[i + 1];
  }
  if (!a.port || !a.jsFile || !a.readyFile) {
    console.error('usage: worker_injector.js --port <n> --js-file <f> --ready-file <f>');
    process.exit(2);
  }
  return a;
}

function httpGetJson(port, path) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port, path, timeout: 5000 }, (res) => {
      let data = '';
      res.on('data', (c) => { data += c; });
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error('bad json from ' + path + ': ' + e.message)); }
      });
    });
    req.on('timeout', () => { req.destroy(new Error('timeout ' + path)); });
    req.on('error', reject);
  });
}

function isWorkerType(t) {
  return t === 'worker' || t === 'shared_worker' || t === 'service_worker';
}

async function main() {
  const args = parseArgs();
  const workerJs = fs.readFileSync(args.jsFile, 'utf8');
  log(`start v4: port ${args.port}, js ${args.jsFile} (${workerJs.length} char)`);

  // Tunggu debug port + ambil browser WebSocket URL.
  let wsUrl = '';
  for (let i = 0; i < 100; i++) {
    try {
      const v = await httpGetJson(args.port, '/json/version');
      if (v && v.webSocketDebuggerUrl) { wsUrl = v.webSocketDebuggerUrl; break; }
    } catch (e) { /* belum siap */ }
    await new Promise((r) => setTimeout(r, 300));
  }
  if (!wsUrl) { log('browser webSocketDebuggerUrl tidak ketemu — keluar'); process.exit(1); }

  const ws = new WebSocket(wsUrl);
  let msgId = 0;
  const pending = new Map();
  const injectedWorkers = new Set(); // targetId worker yang sudah di-inject
  const pageSessions = new Map(); // page targetId -> page sessionId
  const attachingPages = new Set(); // page targetId yang sedang di-attach
  let ready = false;

  function send(method, params, sessionId) {
    return new Promise((resolve, reject) => {
      const id = ++msgId;
      pending.set(id, { resolve, reject });
      const m = { id, method, params: params || {} };
      if (sessionId) m.sessionId = sessionId;
      try { ws.send(JSON.stringify(m)); }
      catch (e) { pending.delete(id); reject(e); }
      setTimeout(() => {
        if (pending.has(id)) { pending.delete(id); reject(new Error('cdp timeout ' + method)); }
      }, 10000);
    });
  }

  // Inject worker JS ke sebuah worker session. Return true bila evaluasi
  // jalan tanpa exception. Idempotent (worker JS punya guard sxgw).
  async function injectWorker(sessionId, targetId, type) {
    if (injectedWorkers.has(targetId)) return true;
    injectedWorkers.add(targetId);
    try {
      const r = await send('Runtime.evaluate', { expression: workerJs, awaitPromise: false, returnByValue: false }, sessionId);
      if (r && r.exceptionDetails) {
        log(`worker ${type} ${targetId.slice(0, 8)}… evaluate EXCEPTION: ${JSON.stringify(r.exceptionDetails).slice(0, 300)}`);
        return false;
      }
      log(`worker ${type} injected (target ${targetId.slice(0, 8)}…)`);
      return true;
    } catch (e) {
      log(`worker ${type} inject error: ${e.message}`);
      return false;
    }
  }

  // Jalur (1): attach ke page + pasang autoAttach di page session.
  async function armPage(pageTargetId) {
    if (pageSessions.has(pageTargetId) || attachingPages.has(pageTargetId)) return;
    attachingPages.add(pageTargetId);
    try {
      const { sessionId } = await send('Target.attachToTarget', { targetId: pageTargetId, flatten: true });
      pageSessions.set(pageTargetId, sessionId);
      await send('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: true, flatten: true }, sessionId);
      log(`page ${pageTargetId.slice(0, 8)}… armed (page-session autoAttach)`);
    } catch (e) {
      log(`armPage ${pageTargetId.slice(0, 8)}… gagal: ${e.message}`);
    } finally {
      attachingPages.delete(pageTargetId);
    }
  }

  // Jalur (2): explicit attach ke worker + inject + resume (v3: resume
  // SELALU dipanggil best-effort — worker yang ter-pause tapi lolos
  // dari jalur (1) macet selamanya bila tidak di-resume di sini).
  async function explicitWorker(targetId, type) {
    if (injectedWorkers.has(targetId)) return;
    try {
      const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
      const ok = await injectWorker(sessionId, targetId, type + ' (explicit)');
      if (ok) {
        await send('Runtime.runIfWaitingForDebugger', {}, sessionId).catch(() => {});
      }
    } catch (e) {
      log(`explicitWorker ${type} ${targetId.slice(0, 8)}… gagal: ${e.message}`);
    }
  }

  // Jalur (3) v3: polling Target.getTargets — tangkap worker yang
  // terlewat dari targetCreated/attachedToTarget (race). Idempotent
  // via injectedWorkers; target yang sudah mati dibersihkan oleh
  // targetDestroyed.
  async function pollWorkers() {
    try {
      const { targetInfos } = await send('Target.getTargets', {});
      for (const ti of (targetInfos || [])) {
        if (isWorkerType(ti.type) && !injectedWorkers.has(ti.targetId)) {
          explicitWorker(ti.targetId, ti.type + ' (poll)');
        }
      }
    } catch (e) { /* browser mungkin mati — watchdog yang urus */ }
  }

  // attachedToTarget — datang dari page session (worker ter-pause) atau
  // browser session. Bila worker: inject lalu resume bila ter-pause.
  async function handleAttached(sessionId, targetInfo, waitingForDebugger) {
    const type = (targetInfo && targetInfo.type) || '';
    const targetId = (targetInfo && targetInfo.targetId) || '';
    if (!isWorkerType(type)) return; // page/non-worker: bukan urusan kita
    try {
      // v4: resume DULU bila ter-pause — Runtime.evaluate timeout bila
      // worker masih ter-pause di startup (terbukti SW 350E0863, F7).
      if (waitingForDebugger) {
        await send('Runtime.runIfWaitingForDebugger', {}, sessionId).catch(() => {});
        await new Promise((r) => setTimeout(r, 150));
        log(`worker ${type} resumed-before-inject (target ${targetId.slice(0, 8)}…)`);
      }
      await injectWorker(sessionId, targetId, type);
      await send('Runtime.runIfWaitingForDebugger', {}, sessionId).catch(() => {});
    } catch (e) {
      log(`handleAttached ${type} error: ${e.message}`);
    }
  }

  ws.onopen = async () => {
    log('cdp terhubung');
    try {
      // Discovery dulu (tanpa browser-level autoAttach — lihat header).
      await send('Target.setDiscoverTargets', { discover: true });
      log('discover aktif');
      // Tangkap page yang sudah ada sebelum daemon start.
      const { targetInfos } = await send('Target.getTargets', {});
      const pages = (targetInfos || []).filter((t) => t.type === 'page');
      log(`getTargets: ${pages.length} page sudah ada`);
      for (const p of pages) {
        // Jangan await satu-satu terlalu lama; armPage cepat.
        await armPage(p.targetId);
      }
      fs.writeFileSync(args.readyFile, JSON.stringify({ ready: true, at: new Date().toISOString(), js_length: workerJs.length, version: 4 }));
      ready = true;
      log('ready (v4)');
      // v3: polling penangkap worker yang terlewat event (tiap 2 detik).
      setInterval(() => { pollWorkers().catch(() => {}); }, 2000);
    } catch (e) {
      log(`setup gagal: ${e.message} — keluar`);
      process.exit(1);
    }
  };

  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) p.reject(new Error(msg.error.message || JSON.stringify(msg.error)));
      else p.resolve(msg.result || {});
      return;
    }
    if (msg.method === 'Target.attachedToTarget' && msg.params) {
      handleAttached(msg.params.sessionId, msg.params.targetInfo, !!msg.params.waitingForDebugger);
      return;
    }
    if (msg.method === 'Target.targetCreated' && msg.params && msg.params.targetInfo) {
      const ti = msg.params.targetInfo;
      if (ti.type === 'page') {
        armPage(ti.targetId);
      } else if (isWorkerType(ti.type)) {
        explicitWorker(ti.targetId, ti.type);
      }
      return;
    }
    if (msg.method === 'Target.targetDestroyed' && msg.params) {
      const tid = msg.params.targetId;
      injectedWorkers.delete(tid);
      pageSessions.delete(tid);
      return;
    }
    if (msg.method === 'Target.detachedFromTarget' && msg.params) {
      // Session page/worker lepas — biarkan map dibersihkan targetDestroyed.
      return;
    }
  };

  ws.onerror = (e) => { log(`websocket error: ${e.message || e.type || 'unknown'}`); };
  ws.onclose = () => {
    log('websocket tutup — keluar');
    process.exit(ready ? 0 : 1);
  };

  // Watchdog: keluar bila browser mati (supaya tidak jadi proses yatim).
  const watchdog = setInterval(async () => {
    try { await httpGetJson(args.port, '/json/version'); }
    catch (e) {
      log('browser mati (watchdog) — keluar');
      clearInterval(watchdog);
      try { ws.close(); } catch (e2) { /* ignore */ }
      process.exit(0);
    }
  }, 5000);

  process.on('SIGTERM', () => {
    log('SIGTERM — keluar');
    clearInterval(watchdog);
    try { ws.close(); } catch (e) { /* ignore */ }
    process.exit(0);
  });
  process.on('SIGINT', () => {
    log('SIGINT — keluar');
    clearInterval(watchdog);
    try { ws.close(); } catch (e) { /* ignore */ }
    process.exit(0);
  });
}

main().catch((e) => { log(`fatal: ${e.message}`); process.exit(1); });
