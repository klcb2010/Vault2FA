#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def patch(relative, old, new):
    path = ROOT / relative
    source = path.read_text(encoding="utf-8")
    if new in source:
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"[mod] anchor mismatch in {relative}: {count}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")

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

site_filter = """function siteFilterPatternMatches(hostname, pattern){
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
    if(/^https?:\\/\\//i.test(url)) currentSiteHostname = new URL(url).hostname.toLowerCase();
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
patch("popup/popup.js", "function render(){\n", site_filter + "function render(){\n")
patch("popup/popup.js",
    "  empty.style.display = visibleAccounts.length ? 'none' : 'flex';\n  const frag = document.createDocumentFragment();",
    `  empty.style.display = visibleAccounts.length ? 'none' : 'flex';
  const emptyTitle = byId('emptyTitle');
  const emptySub = byId('emptySub');
  if(siteFilterEnabled && accounts.length && !visibleAccounts.length && !q){
    const siteNames = [...new Set(accounts.map(a => String(a.issuer || a.label || '').trim()).filter(Boolean))];
    const shownSites = siteNames.slice(0, 5);
    const siteSummary = shownSites.join('、') + (siteNames.length > shownSites.length ? ' 等' : '');
    emptyTitle.textContent = t('noWebsiteMatchTitle');
    emptySub.textContent = tFmt('noWebsiteMatchSub', { sites: siteSummary || '—' });
  } else {
    emptyTitle.textContent = t('noAccountsYet');
    setMultilineText(emptySub, t('emptySub'));
  }
  const frag = document.createDocumentFragment();`)
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
    '''      <button class="settings-menu-item" type="button" data-settings-section="site-filter">
        <span class="settings-menu-label" id="settingSiteFilterTitle">当前网站验证码</span>
        <img class="settings-menu-chevron" src="../icons/enter.svg" alt="" aria-hidden="true" />
      </button>
      <button class="settings-menu-item" type="button" data-settings-section="permission">''')
patch("popup/popup.html",
    '    <div class="settings-section" data-settings-panel="permission">\n',
    '''    <div class="settings-section" data-settings-panel="site-filter">
    <div class="fg sync-toggle-row">
      <label class="toggle-wrap">
        <input type="checkbox" id="siteFilterEnabled" />
        <span id="siteFilterEnabledText">仅当前网站验证码</span>
      </label>
      <div class="fhint" id="siteFilterEnabledHint">根据当前网站自动匹配账号发行方或自定义域名规则。</div>
    </div>
    </div>
    <div class="settings-section" data-settings-panel="permission">
''')

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

# Keep the new UI strings available after future upstream syncs.
patch("locales/zh-CN.lang",
    "siteFilterEnabledText=仅显示当前网站匹配的验证码",
    "siteFilterEnabledText=仅当前网站验证码")
patch("locales/zh-CN.lang",
    "siteFilterEnabledHint=根据当前网站自动匹配账号发行方或自定义域名规则",
    "siteFilterEnabledHint=仅显示与当前网页匹配的已录入验证码\\nnoWebsiteMatchTitle=当前网站没有匹配的验证码\\nnoWebsiteMatchSub=已录入验证码的站点：{sites}")
patch("locales/zh-CN.lang",
    "settingPermissionTitle=权限\n",
    "settingPermissionTitle=权限\nsettingSiteFilterTitle=当前网站验证码\nsiteFilterEnabledText=仅当前网站验证码\nsiteFilterEnabledHint=仅显示与当前网页匹配的已录入验证码\nnoWebsiteMatchTitle=当前网站没有匹配的验证码\nnoWebsiteMatchSub=已录入验证码的站点：{sites}\n")
patch("locales/zh-CN.lang",
    "permissionSavedToast=权限设置已保存\n",
    "permissionSavedToast=权限设置已保存\nautofillSuccess=已自动填入验证码\nnoOtpInput=当前网页没有可填入的输入框\nnoOtpInputCopied=未找到输入框，验证码已复制\nnoActiveTab=无法获取当前网页\n")
patch("locales/en-US.lang",
    "siteFilterEnabledText=Only show codes for the current website",
    "siteFilterEnabledText=Only current website codes")
patch("locales/en-US.lang",
    "siteFilterEnabledHint=Match accounts automatically using the current website and issuer or custom domain rules.",
    "siteFilterEnabledHint=Only show saved codes matching the current website.\\nnoWebsiteMatchTitle=No verification codes match this website\\nnoWebsiteMatchSub=Sites with saved verification codes: {sites}")
patch("locales/en-US.lang",
    "settingPermissionTitle=Permission\n",
    "settingPermissionTitle=Permission\nsettingSiteFilterTitle=Current Website Codes\nsiteFilterEnabledText=Only current website codes\nsiteFilterEnabledHint=Only show saved codes matching the current website.\nnoWebsiteMatchTitle=No verification codes match this website\nnoWebsiteMatchSub=Sites with saved verification codes: {sites}\n")
patch("locales/en-US.lang",
    "permissionSavedToast=Permission Settings saved\n",
    "permissionSavedToast=Permission Settings saved\nautofillSuccess=Verification code filled automatically\nnoOtpInput=No suitable input field found on the current page\nnoOtpInputCopied=No input field found; code copied instead\nnoActiveTab=Unable to access the current tab\n")

print("[mod] Firefox ID, Chinese default, current-site OTP filter and click-to-fill installed")
