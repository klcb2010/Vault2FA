#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def patch(relative, old, new):
    path = ROOT / relative
    source = path.read_text(encoding="utf-8")
    if new in source:
        return
    if source.count(old) != 1:
        raise SystemExit(f"[mod] anchor mismatch in {relative}: {source.count(old)}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")

patch("popup/popup.html",
    '    <div class="settings-section" data-settings-panel="permission">\n',
    '''    <div class="settings-section" data-settings-panel="permission">
    <div class="fg sync-toggle-row">
      <label class="toggle-wrap">
        <input type="checkbox" id="siteFilterEnabled" />
        <span id="siteFilterEnabledText">仅显示当前网站匹配的验证码</span>
      </label>
      <div class="fhint" id="siteFilterEnabledHint">开启后，仅显示域名规则与当前活动网站匹配的账号</div>
    </div>
''')

patch("popup/popup.js",
    "let featureSettings = { autofillEnabled:true, rightclickEnabled:true, rightclickAutofillEnabled:true };",
    "let featureSettings = { autofillEnabled:true, rightclickEnabled:true, rightclickAutofillEnabled:true };\nlet siteFilterEnabled = false;\nlet currentSiteHostname = '';")

patch("popup/popup.js", "function render(){\n", """function siteFilterPatternMatches(hostname, pattern){
  const host = normalizeAutofillPattern(hostname);
  const rule = normalizeAutofillPattern(pattern);
  if(!host || !rule) return false;
  if(rule.startsWith('*.')){
    const base = rule.slice(2);
    return !!base && (host === base || host.endsWith('.' + base));
  }
  return host === rule;
}
function accountMatchesCurrentSite(account){
  if(!currentSiteHostname || !Array.isArray(account.autofillPatterns)) return false;
  return account.autofillPatterns.some(pattern => siteFilterPatternMatches(currentSiteHostname, pattern));
}
async function initSiteFilter(){
  const saved = await browser.storage.local.get('siteFilterEnabled');
  siteFilterEnabled = !!(saved && saved.siteFilterEnabled);
  try {
    const tabs = await browser.tabs.query({ active:true, currentWindow:true });
    const url = String(tabs && tabs[0] && tabs[0].url || '');
    if(/^https?:\\/\\//i.test(url)) currentSiteHostname = new URL(url).hostname.toLowerCase();
  } catch (_) {
    currentSiteHostname = '';
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
function render(){
""")

patch("popup/popup.js",
    "  visibleAccounts = accounts\n    .filter(a => (a.issuer||'').toLowerCase().includes(q) || (a.label||'').toLowerCase().includes(q))\n",
    "  visibleAccounts = accounts\n    .filter(a => !siteFilterEnabled || accountMatchesCurrentSite(a))\n    .filter(a => (a.issuer||'').toLowerCase().includes(q) || (a.label||'').toLowerCase().includes(q))\n")

patch("popup/popup.js",
    "byId('search').addEventListener('input', render);\n",
    "byId('search').addEventListener('input', render);\ninitSiteFilter().catch(err => console.error('[Vault2FA mod] filter init failed', err));\n")

patch("manifest.json",
    '"id": "vault2fa@example.com"',
    '"id": "vault2fa-klcb@example.com"')

print("[mod] current-site OTP filter and fork-specific Gecko ID injected")
