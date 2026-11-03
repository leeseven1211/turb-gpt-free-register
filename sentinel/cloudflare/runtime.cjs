"use strict";

// Focused, original DOM bridge for the optional experiment. jsdom is a DOM
// implementation, NOT the security boundary: the launcher requires OS isolation.
const vm = require("node:vm");
const {JSDOM, VirtualConsole, CookieJar} = require("jsdom");
const inputLimit = 2 * 1024 * 1024;
const pending = new Map();
const documents = [];
const jar = new CookieJar();
const serverCookieKeys = new Set();
let input = "";
let nextId = 0;
let started = false;
let done = false;
let failed = false;

function emit(value) {
  process.stdout.write(JSON.stringify(value) + "\n");
}
function finish() {
  if (done) return;
  done = true;
  emit({type: "done", ok: !failed});
  for (const dom of documents) dom.window.close();
  process.exit(0);
}
function define(target, name, value) {
  Object.defineProperty(target, name, {value, configurable: true, writable: true});
}
function cookies(values, url, snapshot = false) {
  if (!Array.isArray(values)) return;
  const host = new URL(url).hostname;
  const present = new Set();
  const key = cookie => `${cookie.domain}\0${cookie.path}\0${cookie.key}`;
  for (const item of values) {
    if (!item || item.httpOnly || item.httponly || typeof item.name !== "string" ||
        typeof item.value !== "string" || !/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(item.name) ||
        /[;\r\n]/.test(item.value)) continue;
    const domain = String(item.domain || host).replace(/^\./, "").toLowerCase();
    const path = String(item.path || "/");
    if (!path.startsWith("/") || /[;\r\n]/.test(path) ||
        (host !== domain && (item.hostOnly || !host.endsWith("." + domain)))) continue;
    let cookie = `${item.name}=${item.value}; Path=${path}`;
    if (!item.hostOnly) cookie += `; Domain=${domain}`;
    if (item.secure) cookie += "; Secure";
    try {
      const stored = jar.setCookieSync(cookie, url);
      present.add(key(stored)); serverCookieKeys.add(key(stored));
    } catch (_) { /* Ignore out-of-origin cookies. */ }
  }
  if (snapshot) {
    // The bridge snapshot is complete only for this URL's visible scopes.
    // Preserve cookies belonging to other paths/origins and DOM-local writes.
    for (const stored of jar.getCookiesSync(url)) {
      if (serverCookieKeys.has(key(stored)) && !present.has(key(stored))) {
        jar.store.removeCookie(stored.domain, stored.path, stored.key, () => {});
      }
    }
  }
}
function request(win, kind, method, url, body, headers = {}) {
  if (done || ++nextId > 12) return Promise.reject(new Error("request limit"));
  const id = nextId;
  const absolute = new URL(String(url), win.location.href).href;
  const normalized = {};
  for (const [name, value] of Object.entries(headers)) normalized[String(name)] = String(value);
  const result = new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
  emit({type: "request", id, request: {kind, method: String(method).toUpperCase(),
    url: absolute, headers: normalized, body: body == null ? null : String(body)}});
  return result.then(reply => {
    cookies(reply.cookies, reply.url || absolute, true);
    const bytes = Buffer.from(reply.body, "base64");
    return {...reply, bytes, text: bytes.toString("utf8")};
  });
}
function dispatchMessage(target, source, origin, data, targetOrigin) {
  if (targetOrigin !== "*" && targetOrigin !== target.location.origin) return;
  const copy = structuredClone(data);
  setTimeout(() => {
    if (!done) target.dispatchEvent(new target.MessageEvent("message", {data: copy, source, origin}));
  }, 0);
}

async function createDocument(html, url, profile, frame = null, parent = null) {
  const dom = new JSDOM(html, {url, runScripts: "outside-only", pretendToBeVisual: true,
    virtualConsole: new VirtualConsole(), cookieJar: jar});
  documents.push(dom);
  const win = dom.window;
  const context = dom.getInternalVMContext();
  // jsdom emits its native lifecycle while bridge-backed classic scripts are
  // still loading. Release one synthetic event only after those scripts finish.
  win.document.addEventListener("DOMContentLoaded", event => {
    if (event.isTrusted) event.stopImmediatePropagation();
  }, true);
  win.addEventListener("load", event => {
    if (event.isTrusted) event.stopImmediatePropagation();
  }, true);
  const seenScripts = new WeakSet();
  const seenFrames = new WeakMap();
  define(win.navigator, "userAgent", profile.userAgent || "");
  const identity = profile.browserIdentity || {};
  define(win.navigator, "platform", identity.platform || identity.navigator_platform || "MacIntel");
  define(win.navigator, "language", identity.locale || identity.navigator_language || "en-US");
  define(win.navigator, "languages", identity.languages || identity.navigator_languages ||
    [identity.locale || identity.navigator_language || "en-US"]);
  if (parent) {
    const facade = {postMessage(data, targetOrigin = "/") {
      dispatchMessage(parent, win, win.location.origin, data, targetOrigin === "/" ? win.location.origin : String(targetOrigin));
    }};
    define(win, "parent", facade);
    define(win, "postMessage", (data, targetOrigin = "/") =>
      dispatchMessage(win, facade, parent.location.origin, data, targetOrigin === "/" ? parent.location.origin : String(targetOrigin)));
    define(frame, "contentWindow", win);
    define(frame, "contentDocument", win.document);
  } else {
    define(win, "postMessage", (data, targetOrigin = "/") =>
      dispatchMessage(win, win, win.location.origin, data, targetOrigin === "/" ? win.location.origin : String(targetOrigin)));
  }
  define(win, "fetch", async (target, options = {}) => {
    const reply = await request(win, "fetch", options.method || "GET", target,
      options.body, options.headers);
    const headers = new Map(Object.entries(reply.headers || {}).map(([k, v]) => [k.toLowerCase(), String(v)]));
    return {status: reply.status, ok: reply.status >= 200 && reply.status < 300,
      url: reply.url, headers: {get: key => headers.get(String(key).toLowerCase()) || null,
        entries: () => headers.entries(), [Symbol.iterator]: () => headers.entries()},
      text: async () => reply.text, json: async () => JSON.parse(reply.text),
      arrayBuffer: async () => Uint8Array.from(reply.bytes).buffer};
  });
  class BridgeXHR extends win.EventTarget {
    constructor() {
      super(); this.readyState = 0; this.status = 0; this.response = "";
      this.responseText = ""; this.responseType = ""; this.headers = {}; this.aborted = false;
    }
    event(name) {
      const event = new win.Event(name);
      if (typeof this[`on${name}`] === "function") this[`on${name}`](event);
      this.dispatchEvent(event);
    }
    open(method, url, async = true) {
      if (!async) throw new Error("synchronous XHR is unsupported");
      this.method = method; this.url = url; this.readyState = 1; this.event("readystatechange");
    }
    setRequestHeader(name, value) { this.headers[String(name)] = String(value); }
    getResponseHeader(name) {
      const key = Object.keys(this.replyHeaders || {}).find(k => k.toLowerCase() === String(name).toLowerCase());
      return key ? this.replyHeaders[key] : null;
    }
    getAllResponseHeaders() { return Object.entries(this.replyHeaders || {}).map(([k,v]) => `${k}: ${v}`).join("\r\n"); }
    abort() { this.aborted = true; this.event("abort"); }
    send(body = null) {
      request(win, "xhr", this.method, this.url, body, this.headers).then(reply => {
        if (this.aborted) return;
        this.status = reply.status; this.responseURL = reply.url; this.replyHeaders = reply.headers;
        this.responseText = reply.text;
        if (this.responseType === "arraybuffer") this.response = Uint8Array.from(reply.bytes).buffer;
        else if (this.responseType === "json") {
          try { this.response = JSON.parse(reply.text); } catch (_) { this.response = null; }
        } else this.response = reply.text;
        this.readyState = 4;
        for (const name of ["readystatechange", "load", "loadend"]) this.event(name);
      }).catch(() => { this.event("error"); this.event("loadend"); });
    }
  }
  define(win, "XMLHttpRequest", BridgeXHR);

  function evaluate(source, node) {
    define(win.document, "currentScript", node);
    try { new vm.Script(source).runInContext(context, {timeout: 1000}); }
    catch (_) { failed = true; }
    finally { define(win.document, "currentScript", null); }
  }
  async function loadScript(node) {
    if (seenScripts.has(node)) return;
    seenScripts.add(node);
    const type = (node.type || "").toLowerCase();
    if (type && !["text/javascript", "application/javascript"].includes(type)) return;
    if (node.src) {
      const reply = await request(win, "script", "GET", node.src, null);
      if (reply.status < 200 || reply.status >= 300) throw new Error("script rejected");
      evaluate(reply.text, node);
      node.dispatchEvent(new win.Event("load"));
    } else evaluate(node.textContent || "", node);
  }
  async function loadFrame(node) {
    const src = node.src;
    if (!src || src === "about:blank" || seenFrames.get(node) === src) return;
    seenFrames.set(node, src);
    const reply = await request(win, "iframe", "GET", src, null);
    if (reply.status < 200 || reply.status >= 300) throw new Error("iframe rejected");
    await createDocument(reply.text, reply.url || src, profile, node, win);
    node.dispatchEvent(new win.Event("load"));
  }
  function inserted(node) {
    if (!node || node.nodeType !== 1) return;
    if (node.localName === "script") loadScript(node).catch(() => { failed = true; });
    if (node.localName === "iframe") loadFrame(node).catch(() => { failed = true; });
    for (const child of node.querySelectorAll("script,iframe")) inserted(child);
  }
  const observer = new win.MutationObserver(records => {
    for (const record of records) {
      if (record.type === "attributes") inserted(record.target);
      else for (const node of record.addedNodes) inserted(node);
    }
  });
  observer.observe(win.document, {subtree: true, childList: true, attributes: true, attributeFilter: ["src"]});
  win.addEventListener("error", () => { failed = true; });
  for (const node of win.document.querySelectorAll("script,iframe")) {
    if (node.localName === "script") await loadScript(node);
    else loadFrame(node).catch(() => { failed = true; });
  }
  win.document.dispatchEvent(new win.Event("DOMContentLoaded", {bubbles: true}));
  win.dispatchEvent(new win.Event("load"));
  return dom;
}

process.on("uncaughtException", () => { failed = true; finish(); });
process.on("unhandledRejection", () => { failed = true; });
process.stdin.setEncoding("utf8");
process.stdin.on("data", chunk => {
  input += chunk;
  if (Buffer.byteLength(input) > inputLimit) process.exit(2);
  let index;
  while ((index = input.indexOf("\n")) !== -1) {
    const line = input.slice(0, index); input = input.slice(index + 1);
    let message;
    try { message = JSON.parse(line); } catch (_) { process.exit(2); }
    if (!started) {
      if (message.type !== "init" || typeof message.payload?.html !== "string") process.exit(2);
      if (Number(process.versions.node.split(".")[0]) < 20) process.exit(2);
      started = true;
      const profile = message.payload;
      cookies(profile.cookies, profile.url);
      setTimeout(finish, profile.waitMs);
      createDocument(profile.html, profile.url, profile).catch(() => { failed = true; finish(); });
    } else {
      if (message.type !== "response" || !pending.has(message.id)) process.exit(2);
      pending.get(message.id).resolve(message.response);
      pending.delete(message.id);
    }
  }
});
process.stdin.on("end", () => process.exit(2));
