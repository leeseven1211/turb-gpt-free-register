// CJS legacy regression suites can mount the real Vue source without a build.
// This loader transforms source syntax only; production components and hooks run unchanged.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createRequire} = require('node:module');
const frontendRoot = path.join(__dirname, '../frontend');
const frontendRequire = createRequire(path.join(frontendRoot, 'package.json'));

function createVueHarness() {
  const {JSDOM} = frontendRequire('jsdom');
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {url: 'http://localhost/', pretendToBeVisual: true});
  const prior = new Map();
  function install(name, value) {
    prior.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, {configurable: true, writable: true, value});
  }
  for (const name of ['window', 'document', 'navigator', 'Document', 'Element', 'HTMLElement', 'HTMLDialogElement', 'HTMLInputElement', 'SVGElement', 'Node', 'NodeFilter', 'Event', 'MouseEvent', 'KeyboardEvent', 'CustomEvent', 'MutationObserver', 'DOMException', 'getComputedStyle', 'localStorage']) {
    install(name, name === 'window' ? dom.window : dom.window[name]);
  }
  install('ResizeObserver', class {observe() {} unobserve() {} disconnect() {}});
  dom.window.matchMedia = () => ({matches: false, addEventListener() {}, removeEventListener() {}});
  install('requestAnimationFrame', callback => dom.window.requestAnimationFrame(callback));
  install('cancelAnimationFrame', handle => dom.window.cancelAnimationFrame(handle));
  const {parse, compileScript} = frontendRequire('@vue/compiler-sfc');
  const ts = frontendRequire('typescript');
  const cache = new Map();
  function sourceModule(filename) {
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = {exports: {}}; cache.set(filename, module);
    if (filename.endsWith('.json')) {module.exports = JSON.parse(fs.readFileSync(filename, 'utf8')); return module.exports;}
    if (filename.endsWith('.css')) return module.exports;
    let source = fs.readFileSync(filename, 'utf8');
    if (filename.endsWith('.vue')) {
      const {descriptor, errors} = parse(source, {filename});
      if (errors.length) throw errors[0];
      source = compileScript(descriptor, {
        id: filename, inlineTemplate: true,
        fs: {
          fileExists: candidate => fs.existsSync(candidate),
          readFile: candidate => fs.readFileSync(candidate, 'utf8'),
        },
      }).content;
    }
    const output = ts.transpileModule(source, {fileName: filename, reportDiagnostics: true,
      compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true, resolveJsonModule: true}});
    if (output.diagnostics?.length) throw new Error(ts.formatDiagnostics(output.diagnostics, {getCanonicalFileName: x => x, getCurrentDirectory: () => frontendRoot, getNewLine: () => '\n'}));
    function relativeRequire(specifier) {
      if (!specifier.startsWith('.')) return frontendRequire(specifier);
      const base = path.resolve(path.dirname(filename), specifier);
      const resolved = ['', '.ts', '.vue', '.json', '.js'].map(ext => base + ext).find(candidate => fs.existsSync(candidate));
      if (!resolved) throw new Error(`Cannot resolve ${specifier} from ${filename}`);
      return sourceModule(resolved);
    }
    vm.runInThisContext(`(function(require,module,exports,__filename,__dirname){${output.outputText}\n})`, {filename})(relativeRequire, module, module.exports, filename, path.dirname(filename));
    return module.exports;
  }
  const {mount} = frontendRequire('@vue/test-utils');
  const {nextTick} = frontendRequire('vue');
  const wrappers = [];
  return {
    document: dom.window.document,
    load: relativePath => sourceModule(path.join(frontendRoot, relativePath)),
    mount(component, options) {const wrapper = mount(component, {attachTo: dom.window.document.body, ...options}); wrappers.push(wrapper); return wrapper;},
    nextTick,
    cleanup() {wrappers.splice(0).forEach(wrapper => wrapper.unmount()); dom.window.localStorage.clear(); dom.window.document.body.replaceChildren();},
    close() {this.cleanup(); dom.window.close(); for (const [name, descriptor] of prior) {if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name];}},
  };
}
module.exports = {createVueHarness};
