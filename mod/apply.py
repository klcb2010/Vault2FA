#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def patch(relative, old, new):
    path = ROOT / relative
    source = path.read_text(encoding="utf-8")
    if new and new in source:
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"[mod] anchor mismatch in {relative}: {count}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")

# Footer sync badge, extension version link, and locked-pill placement.
patch("popup/popup.html",
    '<div class="sync-badge" id="syncBadge"><div class="sync-dot" id="syncDot"></div><span id="syncBadgeText">Local only</span></div>',
    '<div class="sync-badge" id="syncBadge"><span id="syncBadgeText">Local only</span><span class="sync-version-label" id="permissionVersionLabel">版本：</span><a class="sync-version-link" id="permissionVersionLink" href="https://addons.mozilla.org/zh-CN/developers/addon/2d26ddb08f7841948d04/versions" target="_blank" rel="noopener noreferrer"></a></div>')
patch("popup/popup.js",
    "tf('permissionVersionLabel', 'Current version:')",
    "tf('permissionVersionLabel', '版本：')")
patch("popup/popup.js",
    "tf('permissionVersionLinkTitle', 'View add-on versions')",
    "tf('permissionVersionLinkTitle', '查看扩展版本')")
# Apply footer styles as a single idempotent override. Upstream CSS may already
# contain earlier local edits, so do not depend on fragile upstream anchors.
css_path = ROOT / "popup/popup.css"
css_source = css_path.read_text(encoding="utf-8")
if "/* Vault2FA local footer overrides */" not in css_source:
    css_source += """
/* Vault2FA local footer overrides */
.sync-badge {
  display:flex; align-items:center; gap:4px; padding:6px 13px;
  border-radius:var(--rs); background:var(--accent); color:#000;
  font-family:inherit; font-size:12px; font-weight:600; white-space:nowrap;
}
.sync-badge.offline, .sync-badge.syncing { color:#000; }
.sync-badge.offline .sync-dot, .sync-badge.syncing .sync-dot { background:#000; }
.vault-pill { left:calc(50% + 58px); }
.sync-version-label { margin-left:6px; color:inherit; font:inherit; white-space:nowrap; }
.sync-version-link { color:inherit; font:inherit; text-decoration:underline; text-underline-offset:2px; white-space:nowrap; }
.sync-version-link:hover { opacity:.8; }
"""
    css_path.write_text(css_source, encoding="utf-8")

# Remove the editable-field context menu entry; retain image QR scanning.
patch("background/context-menu.js",
    """    if(featureSettings.rightclickAutofillEnabled !== false){
      browser.contextMenus.create({
        id: AUTOFILL_CONTEXT_MENU_ID,
        title: getContextMenuTitle(language, 'openAutofillPopup'),
        contexts: ['editable'],
      });
    }
""",
    "    // Vault2FA mod: editable-field context menu intentionally removed.\n")

# Import/export all extension settings, including WebDAV credentials.
patch("popup/popup.html",
    '    <div class="err" id="vaultErr"></div>',
    '''    <div class="err" id="vaultErr"></div>''')
# Put import and export as separate first-level actions in the settings menu.
patch("popup/popup.html",
    '''      </button>
      <label class="settings-menu-item site-filter-menu-item">''',
    '''      </button>
      <button class="settings-menu-item" id="btnImportAllSettings" type="button" title="导入将覆盖对应设置，不会覆盖验证码账号和本地加密密钥。">
        <span class="settings-menu-label">导入全部设置</span>
      </button>
      <button class="settings-menu-item" id="btnExportAllSettings" type="button" title="导出文件包含 WebDAV 用户名和密码明文，请妥善保管。">
        <span class="settings-menu-label">导出全部设置</span>
      </button>
      <label class="settings-menu-item site-filter-menu-item">''')
patch("popup/popup.html",
    '    <div class="settings-section" data-settings-panel="security">',
    '''    <input id="importAllSettingsFile" type="file" accept="application/json,.json" style="display:none" />
    <div class="err" id="allSettingsErr"></div>
    <div class="settings-section" data-settings-panel="security">''')

# Migrate installations that inherited the old English default once.
patch("popup/popup.js",
    "  const prefs = await browser.storage.local.get(['uiLanguage','uiTheme']);",
    """  const prefs = await browser.storage.local.get(['uiLanguage','uiTheme','uiLanguageMigrationV1']);
  if(!prefs.uiLanguageMigrationV1){
    if(!prefs.uiLanguage || prefs.uiLanguage === 'en-US'){
      prefs.uiLanguage = 'zh-CN';
      await browser.storage.local.set({ uiLanguage:'zh-CN', uiLanguageMigrationV1:true });
    } else {
      await browser.storage.local.set({ uiLanguageMigrationV1:true });
    }
  }""")

patch("popup/popup.js",
    "byId('btnLockVault').addEventListener('click', async () => {",
    r'''async function exportAllSettings(){
  const keys = [
    'uiLanguage','uiTheme','siteFilterEnabled','accountSettings',
    'featureSettings','syncSettings','webdavCredentials','vaultSettings','debugSettings'
  ];
  const stored = await browser.storage.local.get(keys);
  const settings = {
    uiLanguage: stored.uiLanguage || 'zh-CN',
    uiTheme: stored.uiTheme || 'auto',
    siteFilterEnabled: stored.siteFilterEnabled !== false,
    accountSettings: stored.accountSettings || {},
    featureSettings: stored.featureSettings || {},
    syncSettings: {
      enabled: !!(stored.syncSettings && stored.syncSettings.enabled),
      lastUploadedAt: stored.syncSettings && stored.syncSettings.lastUploadedAt || null,
      lastDownloadedAt: stored.syncSettings && stored.syncSettings.lastDownloadedAt || null,
    },
    webdavCredentials: stored.webdavCredentials || null,
    vaultSettings: {
      autoLockEnabled: !!(stored.vaultSettings && stored.vaultSettings.autoLockEnabled),
      autoLockMinutes: Number(stored.vaultSettings && stored.vaultSettings.autoLockMinutes || 15),
    },
    debugSettings: stored.debugSettings || { enabled:false },
  };
  const payload = {
    format: 'vault2fa-settings',
    version: 1,
    exportedAt: new Date().toISOString(),
    settings,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type:'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'Vault2FA-settings.json';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function importAllSettingsFile(file){
  const errEl = byId('allSettingsErr');
  errEl.style.display = 'none';
  try {
    const parsed = JSON.parse(await file.text());
    if(!parsed || parsed.format !== 'vault2fa-settings' || parsed.version !== 1 || !parsed.settings){
      throw new Error('设置文件格式无效或版本不受支持。');
    }
    const incoming = parsed.settings;
    if(!window.confirm('导入将覆盖当前扩展设置，包括 WebDAV 用户名和密码，但不会覆盖验证码账号和本地加密密钥。继续吗？')) return;
    const current = await browser.storage.local.get(['vaultSettings']);
    const currentVault = current.vaultSettings || {};
    const credentials = incoming.webdavCredentials;
    if(credentials && (!credentials.url || !credentials.username || !credentials.password)){
      throw new Error('设置文件中的 WebDAV 凭据不完整。');
    }
    const sync = incoming.syncSettings || {};
    const encryptionEnabled = !!currentVault.encryptionEnabled;
    const restoredSyncEnabled = !!sync.enabled && !!credentials && encryptionEnabled;
    const values = {
      uiLanguage: typeof incoming.uiLanguage === 'string' ? incoming.uiLanguage : 'zh-CN',
      uiTheme: ['auto','light','dark'].includes(incoming.uiTheme) ? incoming.uiTheme : 'auto',
      siteFilterEnabled: incoming.siteFilterEnabled !== false,
      accountSettings: incoming.accountSettings && typeof incoming.accountSettings === 'object' ? incoming.accountSettings : {},
      featureSettings: incoming.featureSettings && typeof incoming.featureSettings === 'object' ? incoming.featureSettings : {},
      syncSettings: {
        enabled: restoredSyncEnabled,
        connected: !!credentials,
        lastUploadedAt: sync.lastUploadedAt || null,
        lastDownloadedAt: sync.lastDownloadedAt || null,
      },
      vaultSettings: Object.assign({}, currentVault, {
        autoLockEnabled: !!(incoming.vaultSettings && incoming.vaultSettings.autoLockEnabled),
        autoLockMinutes: Math.max(1, parseInt(incoming.vaultSettings && incoming.vaultSettings.autoLockMinutes, 10) || 15),
      }),
      debugSettings: incoming.debugSettings && typeof incoming.debugSettings === 'object'
        ? { enabled: !!incoming.debugSettings.enabled } : { enabled:false },
    };
    if(credentials) values.webdavCredentials = credentials;
    await browser.storage.local.set(values);
    if(!credentials) await browser.storage.local.remove('webdavCredentials');
    await sendMessage({ action:'saveVaultTimerSettings', settings:values.vaultSettings });
    if(sync.enabled && !restoredSyncEnabled){
      toast('设置已导入；由于当前保险库未加密或缺少 WebDAV 凭据，自动同步保持关闭。');
    } else {
      toast('全部设置已导入。');
    }
    window.location.reload();
  } catch(err){
    errEl.textContent = err && err.message ? err.message : String(err);
    errEl.style.display = 'block';
  }
}

byId('btnExportAllSettings').addEventListener('click', async () => {
  if(!guardVaultUnlocked()) return;
  try { await exportAllSettings(); }
  catch(err){
    const el = byId('allSettingsErr'); el.textContent = err.message; el.style.display = 'block';
  }
});
byId('btnImportAllSettings').addEventListener('click', () => {
  if(!guardVaultUnlocked()) return;
  byId('importAllSettingsFile').click();
});
byId('importAllSettingsFile').addEventListener('change', async event => {
  const file = event.target.files && event.target.files[0];
  event.target.value = '';
  if(file) await importAllSettingsFile(file);
});

byId('btnLockVault').addEventListener('click', async () => {''')

# Surface the real startup exception in the popup instead of a generic message.
patch("popup/popup.js",
    "  toast(t('popupLoadFailed'));",
    "  toast(t('popupLoadFailed') + ': ' + (err && err.message ? err.message : String(err)));")

# Firefox fork identity and Chinese first-run language.
patch("manifest.json",
    '"id": "vault2fa@example.com"',
    '"id": "vault2fa-klcb@example.com"')
patch("locales/i18n.js",
    "const DEFAULT_LOCALE_ID = 'en-US';",
    "const DEFAULT_LOCALE_ID = 'zh-CN';")
patch("popup/popup.js",
    "let uiLanguage = 'en-US';",
    "let uiLanguage = 'zh-CN';")
patch("popup/popup.js",
    "  const fallbackLocale = availableLanguages[0] ? availableLanguages[0].localeId : DEFAULT_LOCALE_ID;",
    "  const fallbackLocale = DEFAULT_LOCALE_ID;")

# Current-site matching and one-click fill from the popup.
patch("popup/popup.js",
    "let featureSettings = { autofillEnabled:true, rightclickEnabled:true, rightclickAutofillEnabled:true };",
    "let featureSettings = { autofillEnabled:true, rightclickEnabled:true, rightclickAutofillEnabled:true };\nlet siteFilterEnabled = true;\nlet currentSiteHostname = '';\nlet currentSiteTabId = null;")

site_filter = r"""function siteFilterPatternMatches(hostname, pattern){
  const host = normalizeAutofillPattern(hostname);
  const rule = normalizeAutofillPattern(pattern);
  if(!host || !rule) return false;
  if(rule.startsWith('*.')){
    const base = rule.slice(2);
    return !!base && (host === base || host.endsWith('.' + base));
  }
  return host === rule;
}
const SERVICE_HOST_ALIASES = {
  github:['github'], google:['google'], cloudflare:['cloudflare'], meta:['meta','facebook'],
  facebook:['facebook'], microsoft:['microsoft','live','outlook'], amazon:['amazon'],
  apple:['apple','icloud'], discord:['discord'], dropbox:['dropbox'], paypal:['paypal'],
  twitter:['twitter','x.com'], x:['x.com','twitter'], linkedin:['linkedin'], reddit:['reddit'],
  steam:['steampowered','steamcommunity'], twitch:['twitch'], yahoo:['yahoo'],
  proton:['proton','protonmail'], bitbucket:['bitbucket'], gitlab:['gitlab']
};
function accountMatchesCurrentSite(account){
  if(!currentSiteHostname) return false;
  const patterns = Array.isArray(account.autofillPatterns) ? account.autofillPatterns : [];
  if(patterns.some(pattern => siteFilterPatternMatches(currentSiteHostname, pattern))) return true;
  const issuer = String(account.issuer || account.label || '').toLowerCase();
  const hostParts = currentSiteHostname.split('.');
  for(const [service, aliases] of Object.entries(SERVICE_HOST_ALIASES)){
    if(issuer.includes(service) && aliases.some(alias => hostParts.some(part => part.includes(alias)))) return true;
  }
  const normalizedIssuer = issuer.replace(/[^a-z0-9]/g, '');
  const genericHostParts = new Set(['www','com','net','org','edu','gov','mil','int','co','uk','us','ca','au','cn','jp','de','fr','io','app','dev','info','biz']);
  return hostParts.some(part => {
    const token = part.replace(/[^a-z0-9]/g, '');
    return token.length > 2 && !genericHostParts.has(token) && normalizedIssuer.includes(token);
  });
}
async function initSiteFilter(){
  const saved = await browser.storage.local.get('siteFilterEnabled');
  siteFilterEnabled = saved && saved.siteFilterEnabled != null ? !!saved.siteFilterEnabled : true;
  try {
    const tabs = await browser.tabs.query({ active:true, currentWindow:true });
    const tab = tabs && tabs[0];
    currentSiteTabId = tab && typeof tab.id === 'number' ? tab.id : null;
    const url = String(tab && tab.url || '');
    if(/^https?:\/\//i.test(url)) currentSiteHostname = new URL(url).hostname.toLowerCase();
  } catch (_) {
    currentSiteHostname = '';
    currentSiteTabId = null;
  }
  const checkbox = byId('siteFilterEnabled');
  if(checkbox){
    checkbox.checked = siteFilterEnabled;
    checkbox.addEventListener('change', async () => {
      siteFilterEnabled = checkbox.checked;
      await browser.storage.local.set({ siteFilterEnabled });
      render();
    });
  }
  render();
}
async function fillAccountInActiveTab(account){
  if(!currentSiteTabId) throw new Error(t('noActiveTab'));
  await browser.scripting.insertCSS({
    target:{ tabId:currentSiteTabId, allFrames:false },
    files:['autofill/autofill.css']
  });
  await browser.scripting.executeScript({
    target:{ tabId:currentSiteTabId, allFrames:false },
    files:['third-party/polyfill.min.js','locales/i18n.js','autofill/autofill-content.js']
  });
  const response = await browser.tabs.sendMessage(currentSiteTabId, {
    action:'fillOtpFromPopup',
    accountId:String(account.id || '')
  });
  if(!response || !response.success) throw new Error((response && response.error) || t('noOtpInput'));
  return response;
}
"""
# The current upstream already contains the site-filter implementation.
# Only inject it when syncing from an older upstream revision without these helpers.
popup_js = (ROOT / "popup/popup.js").read_text(encoding="utf-8")
if "function siteFilterPatternMatches(" not in popup_js:
    patch("popup/popup.js", "function render(){\n", site_filter + "function render(){\n")
patch("popup/popup.js",
    "  empty.style.display = visibleAccounts.length ? 'none' : 'flex';\n  const frag = document.createDocumentFragment();",
    """  empty.style.display = visibleAccounts.length ? 'none' : 'flex';
  const emptyTitle = byId('emptyTitle');
  const emptySub = byId('emptySub');
  if(siteFilterEnabled && accounts.length && !visibleAccounts.length && !q){
    const siteNames = [...new Set(accounts.map(a => String(a.issuer || a.label || '').trim()).filter(Boolean))];
    const siteSummary = siteNames.join('、');
    emptyTitle.textContent = t('noWebsiteMatchTitle');
    emptySub.textContent = tFmt('noWebsiteMatchSub', { sites: siteSummary || '—' });
  } else {
    emptyTitle.textContent = t('noAccountsYet');
    setMultilineText(emptySub, t('emptySub'));
  }
  const frag = document.createDocumentFragment();""")

patch("popup/popup.js",
    "  visibleAccounts = accounts\n    .filter(a => (a.issuer||'').toLowerCase().includes(q) || (a.label||'').toLowerCase().includes(q))",
    "  visibleAccounts = accounts\n    .filter(a => !siteFilterEnabled || accountMatchesCurrentSite(a))\n    .filter(a => (a.issuer||'').toLowerCase().includes(q) || (a.label||'').toLowerCase().includes(q))")
patch("popup/popup.js",
    "byId('search').addEventListener('input', render);",
    "byId('search').addEventListener('input', render);\ninitSiteFilter().catch(err => console.error('[Vault2FA mod] filter init failed', err));")

patch("popup/popup.js",
    "  settingDrawerTitle: 'settingDrawerTitle', settingSecurityTitle: 'settingSecurityTitle', settingPermissionTitle: 'settingPermissionTitle',",
    "  settingDrawerTitle: 'settingDrawerTitle', settingSecurityTitle: 'settingSecurityTitle', settingPermissionTitle: 'settingPermissionTitle', settingSiteFilterTitle: 'settingSiteFilterTitle',\n  siteFilterEnabledText: 'siteFilterEnabledText', siteFilterEnabledHint: 'siteFilterEnabledHint',")
patch("popup/popup.js",
    "    settingPermissionTitle: 'Permissions',",
    "    settingPermissionTitle: 'Permissions',\n    settingSiteFilterTitle: 'Current Website Codes',\n    siteFilterEnabledText: 'Only current website codes',\n    noWebsiteMatchTitle: 'No codes match this website',\n    noWebsiteMatchSub: 'Sites with saved codes: {sites}',")

old_click = """  const codeEl = e.target.closest('.otp-code');
  if(codeEl){
    const card = codeEl.closest('.card');
    const acc = accounts.find(a => String(a.id) === card.dataset.id);
    if(!acc) return;
    if(acc.type === 'hotp') await refreshDisplayCodes();
    const info = getDisplayCode(acc);
    navigator.clipboard.writeText((info && info.code) || '').then(() => toast(t('copied')));
  }"""
new_click = """  const codeEl = e.target.closest('.otp-code');
  if(codeEl){
    const card = codeEl.closest('.card');
    const acc = accounts.find(a => String(a.id) === card.dataset.id);
    if(!acc) return;
    if(!guardVaultUnlocked()) return;
    try {
      await fillAccountInActiveTab(acc);
      toast(t('autofillSuccess'));
    } catch(err) {
      if(acc.type === 'hotp') await refreshDisplayCodes();
      const info = getDisplayCode(acc);
      const code = (info && info.code) || '';
      if(code) await navigator.clipboard.writeText(code);
      toast(code ? t('noOtpInputCopied') : (err.message === 'NO_OTP_INPUT' ? t('noOtpInput') : (err.message || t('noOtpInput'))));
    }
  }"""
patch("popup/popup.js", old_click, new_click)

# Put the site filter in its own first-level settings page, next to Permissions.
patch("popup/popup.html",
    '      <button class="settings-menu-item" type="button" data-settings-section="permission">',
    '''      <label class="settings-menu-item site-filter-menu-item">
        <span class="settings-menu-label" id="settingSiteFilterTitle">仅显示当前网站验证码</span>
        <input type="checkbox" id="siteFilterEnabled" class="site-filter-menu-toggle" aria-label="仅显示当前网站验证码" />
      </label>
      <button class="settings-menu-item" type="button" data-settings-section="permission">''')

# Allow a click on an OTP card to fill the currently focused web input.
patch("autofill/autofill-content.js",
    """    browserApi.runtime.onMessage.addListener((message) => {
      if(!message || message.action !== 'openAutofillPopupHere') return false;
      const input = isSupportedTextInput(state.lastContextInput) && state.lastContextInput.isConnected
        ? state.lastContextInput
        : document.activeElement;
      showAutofillForInput(input).catch(() => hideDropdown());
      return false;
    });""",
    """    browserApi.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if(message && message.action === 'fillOtpFromPopup'){
        (async () => {
          const activeInput = document.activeElement;
          const input = isSupportedTextInput(activeInput)
            ? activeInput
            : (isSupportedTextInput(state.lastContextInput) && state.lastContextInput.isConnected ? state.lastContextInput : null);
          if(!isSupportedTextInput(input)) throw new Error('NO_OTP_INPUT');
          const response = await browserApi.runtime.sendMessage({
            action:'generateCodeForAutofillById',
            id:String(message.accountId || ''),
            hostname:window.location.hostname || ''
          });
          if(!response || response.success === false || !response.code) throw new Error((response && response.error) || 'CODE_GENERATION_FAILED');
          input.focus();
          setNativeInputValue(input, response.code);
          fireInputEvents(input);
          return { success:true };
        })().then(sendResponse).catch(err => sendResponse({ success:false, error:err && err.message ? err.message : String(err) }));
        return true;
      }
      if(!message || message.action !== 'openAutofillPopupHere') return false;
      const input = isSupportedTextInput(state.lastContextInput) && state.lastContextInput.isConnected
        ? state.lastContextInput
        : document.activeElement;
      showAutofillForInput(input).catch(() => hideDropdown());
      return false;
    });""")

# Keep local UI strings stable across clean upstream release syncs.
def set_lang_entries(relative, entries):
    path = ROOT / relative
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("[popup]") + 1
    except ValueError:
        raise SystemExit(f"[mod] missing [popup] section in {relative}")
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("[") and lines[i].endswith("]")), len(lines))

    for key, value in entries.items():
        prefix = key + "="
        matches = [i for i in range(start, end) if lines[i].startswith(prefix)]
        if len(matches) > 1:
            raise SystemExit(f"[mod] duplicate locale key in {relative}: {key}")
        line = prefix + value
        if matches:
            lines[matches[0]] = line
        else:
            lines.insert(end, line)
            end += 1

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


set_lang_entries("locales/zh-CN.lang", {
    "permissionVersionLabel": "版本：",
    "permissionVersionLinkTitle": "查看扩展版本",
    "settingSiteFilterTitle": "仅显示当前网站验证码",
    "siteFilterEnabledText": "仅当前网站验证码",
    "siteFilterEnabledHint": "仅显示与当前网页匹配的已录入验证码",
    "noWebsiteMatchTitle": "当前网站没有匹配的验证码",
    "noWebsiteMatchSub": "已录入验证码的站点：{sites}",
    "autofillSuccess": "已自动填入验证码",
    "noOtpInput": "当前网页没有可填入的输入框",
    "noOtpInputCopied": "未找到输入框，验证码已复制",
    "noActiveTab": "无法获取当前网页",
})
set_lang_entries("locales/en-US.lang", {
    "permissionVersionLabel": "Version:",
    "permissionVersionLinkTitle": "View extension versions",
    "settingSiteFilterTitle": "Current Website Codes",
    "siteFilterEnabledText": "Only current website codes",
    "siteFilterEnabledHint": "Only show saved codes matching the current website.",
    "noWebsiteMatchTitle": "No codes match this website",
    "noWebsiteMatchSub": "Sites with saved codes: {sites}",
    "autofillSuccess": "Verification code filled automatically",
    "noOtpInput": "No suitable input field found on the current page",
    "noOtpInputCopied": "No input field found; code copied instead",
    "noActiveTab": "Unable to access the current tab",
})

print("[mod] Firefox ID, Chinese default, current-site OTP filter and click-to-fill installed")
