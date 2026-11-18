// SPDX-License-Identifier: MIT
'use strict';

const SYNC_SETTINGS_KEY = 'syncSettings';
const WEBDAV_CREDENTIALS_KEY = 'webdavCredentials';
const WEBDAV_FILENAME = 'vault2fa-backup.json';
const WEBDAV_AUTO_UPLOAD_ALARM = 'vault2fa-webdav-auto-upload';

const defaultSyncSettings = {
  enabled: false,
  lastUploadedAt: null,
  lastDownloadedAt: null,
  connected: false,
};

let webdavUploadDebounceTimer = null;
let webdavUploadPending = false;
let webdavUploadPromise = null;

async function scheduleWebdavUploadAfterLocalChange(){
  const settings = await getSyncSettings();
  if(!settings.enabled || !settings.connected) return;
  webdavUploadPending = true;
  if(webdavUploadDebounceTimer) clearTimeout(webdavUploadDebounceTimer);
  webdavUploadDebounceTimer = setTimeout(() => {
    runScheduledWebdavUpload().catch(() => {});
  }, 900);
  // The alarm wakes the Firefox background context if it is suspended before the debounce timer fires.
  if(browser.alarms && browser.alarms.create){
    try {
      await browser.alarms.create(WEBDAV_AUTO_UPLOAD_ALARM, { delayInMinutes: 0.5 });
    } catch(err) {
      await appendDebugInfo('Unable to schedule WebDAV upload alarm', {
        error: err && err.message ? err.message : String(err),
      });
    }
  }
}

async function runScheduledWebdavUpload(){
  if(webdavUploadDebounceTimer){
    clearTimeout(webdavUploadDebounceTimer);
    webdavUploadDebounceTimer = null;
  }
  if(browser.alarms && browser.alarms.clear){
    try { await browser.alarms.clear(WEBDAV_AUTO_UPLOAD_ALARM); } catch (_) {}
  }
  const settings = await getSyncSettings();
  if(!settings.enabled || !settings.connected){
    webdavUploadPending = false;
    return;
  }
  if(webdavUploadPromise){
    webdavUploadPending = true;
    return;
  }
  webdavUploadPending = false;
  try {
    await uploadToSync();
  } catch(err) {
    await appendDebugInfo('WebDAV change-triggered upload failed', {
      error: err && err.message ? err.message : String(err),
    });
  }
}

async function getSyncSettings(){
  const result = await browser.storage.local.get(SYNC_SETTINGS_KEY);
  const credentials = await getWebdavCredentials();
  return Object.assign({}, defaultSyncSettings, result[SYNC_SETTINGS_KEY] || {}, {
    url: credentials && credentials.url || '',
    username: credentials && credentials.username || '',
    connected: !!credentials,
  });
}

async function setSyncSettings(next){
  const merged = Object.assign({}, await getSyncSettings(), next || {});
  await browser.storage.local.set({ [SYNC_SETTINGS_KEY]: merged });
  return merged;
}

async function getWebdavCredentials(){
  const result = await browser.storage.local.get(WEBDAV_CREDENTIALS_KEY);
  return result[WEBDAV_CREDENTIALS_KEY] || null;
}

function normalizeWebdavUrl(value){
  let url;
  try { url = new URL(String(value || '').trim()); }
  catch (_) { throw new Error('请输入有效的 WebDAV 服务器地址。'); }
  if(!['http:', 'https:'].includes(url.protocol)) throw new Error('WebDAV 地址必须使用 HTTP 或 HTTPS。');
  if(url.username || url.password || url.search || url.hash) throw new Error('服务器地址中不能包含用户名、密码、查询参数或片段。');
  url.pathname = url.pathname.replace(/\/+$/, '') + '/';
  return url.toString();
}

function getWebdavFileUrl(baseUrl){
  return new URL(WEBDAV_FILENAME, baseUrl).toString();
}

function webdavAuthHeader(credentials){
  return 'Basic ' + btoa(unescape(encodeURIComponent(credentials.username + ':' + credentials.password)));
}

async function webdavFetch(url, credentials, options = {}){
  const headers = Object.assign({}, options.headers || {}, { Authorization: webdavAuthHeader(credentials) });
  const response = await fetch(url, Object.assign({ cache: 'no-store', credentials: 'omit' }, options, { headers }));
  if(!response.ok){
    const detail = response.status === 401 || response.status === 403
      ? 'WebDAV 用户名或密码错误，或当前账号没有访问权限。'
      : 'WebDAV 请求失败（HTTP ' + response.status + '）。';
    throw new Error(detail);
  }
  return response;
}

async function loginWebdav(settings){
  const baseUrl = normalizeWebdavUrl(settings && settings.url);
  const username = String(settings && settings.username || '').trim();
  const password = String(settings && settings.password || '');
  if(!username || !password) throw new Error('请输入 WebDAV 用户名和密码。');
  const credentials = { url: baseUrl, username, password };
  await webdavFetch(baseUrl, credentials, { method: 'PROPFIND', headers: { Depth: '0' } });
  await browser.storage.local.set({ [WEBDAV_CREDENTIALS_KEY]: credentials });
  const sync = await setSyncSettings({ connected: true });
  return { success: true, settings: sync, url: baseUrl, username };
}

async function logoutWebdav(){
  await browser.storage.local.remove(WEBDAV_CREDENTIALS_KEY);
  const settings = await setSyncSettings({ connected: false, enabled: false });
  if(webdavUploadDebounceTimer){
    clearTimeout(webdavUploadDebounceTimer);
    webdavUploadDebounceTimer = null;
  }
  webdavUploadPending = false;
  if(browser.alarms && browser.alarms.clear){
    try { await browser.alarms.clear(WEBDAV_AUTO_UPLOAD_ALARM); } catch (_) {}
  }
  return { success: true, settings };
}

async function requireWebdavCredentials(){
  const credentials = await getWebdavCredentials();
  if(!credentials || !credentials.url || !credentials.username || !credentials.password){
    throw new Error('请先登录 WebDAV 服务器。');
  }
  return credentials;
}

async function buildEncryptedBackup(){
  const vault = await getVaultSettings();
  if(!vault.encryptionEnabled) throw new Error('请先开启本地保险库加密，再使用 WebDAV 同步。');
  const payload = await getEncryptedPayload();
  if(!payload || !payload.iv || !payload.data) throw new Error('未找到已加密的保险库数据。');
  return {
    format: 'vault2fa-webdav',
    version: 1,
    updatedAt: Date.now(),
    mode: 'encryptedPayload',
    payload,
  };
}

async function performWebdavUpload(){
  const credentials = await requireWebdavCredentials();
  const backup = await buildEncryptedBackup();
  const response = await webdavFetch(getWebdavFileUrl(credentials.url), credentials, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify(backup),
  });
  const updatedAt = backup.updatedAt;
  await setSyncSettings({ lastUploadedAt: updatedAt, connected: true });
  const result = { success: true, updatedAt, mode: 'encryptedPayload' };
  await appendDebugInfo('WebDAV upload completed', { updatedAt, mode: result.mode, status: response.status });
  return result;
}

function uploadToSync(){
  if(webdavUploadPromise) return webdavUploadPromise;
  webdavUploadPromise = performWebdavUpload().finally(() => {
    webdavUploadPromise = null;
    if(webdavUploadPending) scheduleWebdavUploadAfterLocalChange().catch(() => {});
  });
  return webdavUploadPromise;
}

async function downloadFromSync(options = {}){
  const credentials = await requireWebdavCredentials();
  if(webdavUploadDebounceTimer){
    clearTimeout(webdavUploadDebounceTimer);
    webdavUploadDebounceTimer = null;
  }
  webdavUploadPending = false;
  if(browser.alarms && browser.alarms.clear){
    try { await browser.alarms.clear(WEBDAV_AUTO_UPLOAD_ALARM); } catch (_) {}
  }
  if(webdavUploadPromise){
    try { await webdavUploadPromise; } catch (_) {}
  }
  webdavUploadPending = false;
  const response = await webdavFetch(getWebdavFileUrl(credentials.url), credentials, { method: 'GET' });
  let backup;
  try { backup = await response.json(); }
  catch (_) { throw new Error('WebDAV 备份文件不是有效的 JSON。'); }
  if(!backup || backup.format !== 'vault2fa-webdav' || backup.version !== 1 ||
     backup.mode !== 'encryptedPayload' || !backup.payload ||
     !backup.payload.iv || !backup.payload.data){
    throw new Error('WebDAV 备份文件格式无效或不受支持。');
  }
  const encryptedPayload = backup.payload;
  const containsEncryptedHeader = hasPayloadHeaderFields(encryptedPayload);
  if(options.apply === false){
    return { success: true, updatedAt: backup.updatedAt || null, count: 0, mode: 'encryptedPayload', containsEncryptedHeader, requiresEncryptedConfirmation: true };
  }
  if(!options.allowEncrypted){
    const err = new Error('下载的数据为加密保险库，请确认覆盖本地数据。');
    err.code = 'NEED_ENCRYPTED_CONFIRM';
    throw err;
  }
  await setEncryptedPayload(encryptedPayload);
  await clearPlainAccounts();
  webdavUploadPending = false;
  await persistSessionUnlockState(null);
  await clearVaultAutoLockAlarm();
  await setVaultSettings({ encryptionEnabled: true, salt: null, lastUnlockedAt: null });
  await setSyncSettings({ lastDownloadedAt: Date.now(), connected: true });
  await appendDebugInfo('WebDAV download applied', { updatedAt: backup.updatedAt || null, mode: 'encryptedPayload' });
  return { success: true, accounts: [], updatedAt: backup.updatedAt || null, count: 0, mode: 'encryptedPayload', containsEncryptedHeader, appliedEncryptedPayload: true };
}
