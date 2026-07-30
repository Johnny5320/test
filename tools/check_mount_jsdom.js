// jsdom + 真实 vue/element-plus 完整加载页面，复现浏览器挂载过程，抓渲染期错误
const path = require('path');
const { JSDOM, VirtualConsole } = require(path.join('C:/Users/谢', 'node_modules', 'jsdom'));

const vc = new VirtualConsole();
const errors = [];
vc.on('jsdomError', (e) => errors.push('JSDOM_ERROR: ' + e.message + (e.detail ? ' | ' + (e.detail.message || e.detail) : '')));
vc.on('error', (...a) => errors.push('CONSOLE_ERROR: ' + a.map(String).join(' ')));
vc.on('warn', (...a) => { const s = a.map(String).join(' '); if (s.includes('[Vue')) errors.push('VUE_WARN: ' + s); });
vc.on('log', () => {});

(async () => {
  const dom = await JSDOM.fromURL('http://127.0.0.1:8000/', {
    resources: 'usable',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole: vc,
  });
  // 等脚本执行 + 挂载
  await new Promise((r) => setTimeout(r, 8000));
  const doc = dom.window.document;
  const app = doc.getElementById('app');
  const rawMustache = app && /\{\{[^}]+\}\}/.test(app.innerHTML.slice(0, 3000));
  console.log('scripts loaded:', [...doc.querySelectorAll('script[src]')].map((s) => s.src.split('/').pop()).join(','));
  console.log('Vue global:', typeof dom.window.Vue, '| ElementPlus:', typeof dom.window.ElementPlus, '| echarts:', typeof dom.window.echarts);
  console.log('app children:', app ? app.children.length : 'NO #app', '| raw mustache visible:', rawMustache);
  if (errors.length) {
    console.log('--- captured errors (first 10) ---');
    errors.slice(0, 10).forEach((e) => console.log(e.slice(0, 500)));
  } else {
    console.log('no errors captured');
  }
  dom.window.close();
  process.exit(rawMustache ? 2 : 0);
})().catch((e) => { console.log('FATAL:', e.message); process.exit(1); });
