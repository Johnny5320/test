// 用官方 @vue/compiler-dom 编译 #app 模板，输出精确错误位置（浏览器 runtime 编译同源）
const fs = require('fs');
const path = require('path');
const { compile } = require(path.join(process.env.NODE_WS || 'C:/Users/谢/.workbuddy/binaries/node/workspace', 'node_modules', '@vue/compiler-dom'));

const file = process.argv[2] || path.join(__dirname, '..', 'judicial-system', 'frontend', 'index_v2.html');
const html = fs.readFileSync(file, 'utf8');

const startTag = html.indexOf('<div id="app"');
const startInner = html.indexOf('>', startTag) + 1;
let depth = 1;
const re = /<div\b|<\/div>/g;
re.lastIndex = startInner;
let m, endInner = -1;
while ((m = re.exec(html))) {
  if (m[0] === '</div>') { depth--; if (depth === 0) { endInner = m.index; break; } }
  else depth++;
}
const template = html.slice(startInner, endInner);
console.log('file =', path.basename(file), '| template length =', template.length);

const errors = [];
try {
  compile(template, {
    onError(e) { errors.push(e); },
  });
} catch (e) { errors.push(e); }

if (errors.length) {
  for (const e of errors) {
    console.log('TEMPLATE_ERROR:', e.message);
    if (e.loc && e.loc.start) {
      const off = e.loc.start.offset;
      // 折算成整个 html 文件的行号
      const lineNo = html.slice(0, startInner + off).split('\n').length;
      console.log('  html line ~', lineNo);
      console.log('  near:', JSON.stringify(template.slice(Math.max(0, off - 100), off + 150)));
    }
  }
  process.exit(2);
}
console.log('TEMPLATE_COMPILE_OK');
