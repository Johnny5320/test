// 真实执行内联脚本（mock Vue/ElementPlus/fetch 等），抓 setup 顶层运行时错误（如 TDZ）
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const file = process.argv[2] || path.join(__dirname, '..', 'judicial-system', 'frontend', 'index_v2.html');
const html = fs.readFileSync(file, 'utf8');
const m = [...html.matchAll(/<script(?![^>]*src)[^>]*>([\s\S]*?)<\/script>/g)];
const code = m[m.length - 1][1];

let setupError = null;
let mountCalled = false;

function mockRef(v) { return { value: v }; }
function mockReactive(o) { return o; }
function mockComputed(fn) { const r = { get value() { try { return fn(); } catch (e) { return undefined; } } }; return r; }

const sandbox = {
  console,
  setTimeout, clearTimeout, setInterval, clearInterval,
  URLSearchParams, URL,
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  fetch: () => new Promise(() => {}), // 永不 resolve，setup 顶层不 await 所以无碍
  document: {
    createElement: () => ({ style: {}, click: () => {}, set href(v) {}, set download(v) {} }),
    getElementById: () => null,
    addEventListener: () => {},
    removeEventListener: () => {},
  },
  navigator: { userAgent: 'node' },
  location: { href: '', reload: () => {} },
  Vue: {
    createApp(opts) {
      // 真实执行 setup
      try { opts.setup(); } catch (e) { setupError = e; }
      return { use() { return this; }, mount() { mountCalled = true; return this; } };
    },
    ref: mockRef, reactive: mockReactive, computed: mockComputed,
    onMounted: () => {}, onUnmounted: () => {}, nextTick: (f) => f && f(),
    watch: () => {},
  },
  ElementPlus: new Proxy({}, { get: (t, k) => (k === Symbol.toPrimitive ? undefined : Object.assign(() => {}, { success: () => {}, warning: () => {}, error: () => {}, info: () => {}, confirm: () => Promise.resolve() })) }),
  ElementPlusLocaleZhCn: {},
  echarts: { init: () => ({ setOption: () => {}, resize: () => {}, dispose: () => {} }) },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

try {
  new vm.Script(code, { filename: 'inline.js' }).runInContext(sandbox);
} catch (e) {
  console.log('TOP_LEVEL_ERROR:', e.constructor.name + ':', e.message);
  console.log(e.stack.split('\n').slice(0, 5).join('\n'));
  process.exit(2);
}
if (setupError) {
  console.log('SETUP_ERROR:', setupError.constructor.name + ':', setupError.message);
  console.log(setupError.stack.split('\n').slice(0, 6).join('\n'));
  process.exit(3);
}
console.log('SETUP_RUNTIME_OK (mount called:', mountCalled + ')');
