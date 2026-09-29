/* Uses only an existing Node runtime and its built-in modules. No npm/build step. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../bridges/photoshop_uxp/index.js"), "utf8");
let tests = 0;
function check(name, fn) { fn(); tests += 1; console.log("PASS " + name); }
function readonly(value) {
  if (!value || typeof value !== "object") return value;
  const copy = Array.isArray(value) ? value.map(readonly) :
    Object.fromEntries(Object.entries(value).map(([key, child]) => [key, readonly(child)]));
  return new Proxy(Object.freeze(copy), {
    set() { throw new Error("Document mutation attempted"); },
    deleteProperty() { throw new Error("Document mutation attempted"); }
  });
}
const runtime = {
  host: { name: "photoshop", version: "27.10.0" },
  versions: { uxp: "mock-uxp", plugin: "0.1.0" }
};
function load(app, environment = runtime) {
  const context = {
    module: { exports: {} },
    require(name) {
      if (name === "photoshop") return { app };
      if (name === "uxp") return environment;
      throw new Error("Unexpected module: " + name);
    }
  };
  vm.runInNewContext(source, context);
  return context.module.exports;
}
function request(plugin, operation = "photoshop_get_active_document") {
  return JSON.parse(JSON.stringify(plugin.handleRequest({
    type: "request", protocol_version: 1, id: "test-id", operation
  })));
}
const leaf = (id, name) => ({ id, name, kind: "pixel", layers: null });
const group = { id: 1, name: "表情", kind: "group", layers: [
  leaf(2, "Eyes"), { id: 3, name: "Eyes", kind: "group", layers: [leaf(4, "瞳 🐱")] }
] };
const documentFixture = {
  id: 42, name: "Totolina – 猫 🐾.psd", width: 2048, height: 1024, saved: false,
  layers: [group, leaf(5, "Body")], artboards: [{ id: 1, name: "表情" }]
};
const plugin = load(readonly({ version: "27.10.0", documents: [documentFixture], activeDocument: documentFixture }));
check("actual DOM getters preserve order, nested groups, duplicate names and Unicode", () => {
  const result = request(plugin);
  assert.equal(result.ok, true);
  const doc = result.result.document;
  assert.equal(doc.name, documentFixture.name);
  assert.equal(doc.recursive_layer_count, 5);
  assert.equal(doc.top_level_layer_count, 2);
  assert.deepEqual(doc.layers.map(layer => layer.id), [1, 5]);
  assert.deepEqual(doc.layers[0].children.map(layer => layer.name), ["Eyes", "Eyes"]);
  assert.deepEqual(doc.artboards, [{ id: 1, name: "表情" }]);
  assert.equal(doc.artboard_count, 1);
  assert.equal(doc.saved, false);
  assert.equal(doc.width_px, 2048);
});
check("ping uses current host getter on each request", () => {
  let reads = 0;
  let currentVersion = "27.10.0";
  const dynamic = load({ get version() { throw new Error("Photoshop DOM version must not be read"); } }, {
    ...runtime, host: { name: "photoshop", get version() { reads += 1; return currentVersion; } }
  });
  request(dynamic, "photoshop_ping");
  const before = reads;
  currentVersion = "28.0";
  assert.equal(request(dynamic, "photoshop_ping").result.uxp_version, "mock-uxp");
  assert.ok(reads > before);
  assert.equal(request(dynamic, "photoshop_ping").result.photoshop_version, "28.0");
});
for (const version of ["27.10", "27.10.0", "27.10.0.26", "27.11", "28.0", "27.100", " 27.10.0 "]) {
  check("UXP host version " + version + " is supported without a Photoshop DOM version", () => {
    const reply = request(load({}, { ...runtime, host: { name: "photoshop", version } }), "photoshop_ping");
    assert.equal(reply.ok, true);
    assert.equal(reply.result.photoshop_version, version.trim());
    assert.equal(reply.result.host_version, version.trim());
  });
}
check("ping reads plugin and UXP versions from the runtime", () => {
  const reply = request(load({}, { ...runtime, versions: { uxp: "uxp-9.1.0", plugin: "0.1.7" } }), "photoshop_ping");
  assert.equal(reply.result.host_name, "photoshop");
  assert.equal(reply.result.host_version, "27.10.0");
  assert.equal(reply.result.photoshop_version, "27.10.0");
  assert.equal(reply.result.uxp_version, "uxp-9.1.0");
  assert.equal(reply.result.plugin_version, "0.1.7");
  assert.equal(reply.protocol_version, 1);
});
for (const version of [undefined, null, "", " ", "undefined", "invalid", "27", "27.x", "27.10garbage",
                       "27.10.0oops", "27..10", "27.10.0\nprivate", "9007199254740992.10", 27.10, {}]) {
  check("invalid UXP host version " + JSON.stringify(version) + " returns a structured detection failure", () => {
    const environment = { ...runtime, host: { name: "photoshop", version } };
    const invalid = load({ get documents() { throw new Error("Document must not be read"); } }, environment);
    for (const operation of ["photoshop_ping", "photoshop_get_active_document"]) {
      const reply = request(invalid, operation);
      assert.equal(reply.ok, false);
      assert.equal(reply.result, null);
      assert.deepEqual(reply.error, {
        code: "HOST_DETECTION_FAILED",
        message: "Could not detect the Photoshop host version from UXP host.version."
      });
    }
  });
}
check("unavailable UXP host getter returns a fixed detection error without exception details", () => {
  for (const host of [undefined, { get version() { throw new Error("private runtime detail"); } }]) {
    const reply = request(load({}, { ...runtime, host }), "photoshop_ping");
    assert.equal(reply.ok, false);
    assert.equal(reply.error.code, "HOST_DETECTION_FAILED");
    assert.match(reply.error.message, /Could not detect.*UXP host.version/);
    assert.equal(JSON.stringify(reply).includes("private"), false);
  }
});
check("missing or invalid host names return host detection failures before document access", () => {
  for (const name of [undefined, null, "", " ", 27, {}, "x".repeat(100)]) {
    const invalid = load({ get documents() { throw new Error("Document must not be read"); } }, {
      ...runtime, host: { name, version: "27.10.0" }
    });
    for (const operation of ["photoshop_ping", "photoshop_get_active_document"]) {
      const reply = request(invalid, operation);
      assert.equal(reply.ok, false);
      assert.equal(reply.error.code, "HOST_DETECTION_FAILED");
      assert.match(reply.error.message, /Could not detect.*UXP host.name/);
    }
  }
});
check("host name getter exceptions remain sanitized host detection failures", () => {
  const reply = request(load({}, { ...runtime, host: {
    version: "27.10.0", get name() { throw new Error("private runtime detail"); }
  } }), "photoshop_ping");
  assert.equal(reply.error.code, "HOST_DETECTION_FAILED");
  assert.equal(JSON.stringify(reply).includes("private"), false);
});
check("no document does not access activeDocument", () => {
  const empty = load({ version: "27.10", documents: [], get activeDocument() { throw new Error("Unexpected read"); } });
  assert.deepEqual(request(empty).result, { has_document: false, document: null });
});
check("unsupported operation is rejected before any document access", () => {
  const unsafe = load({ get documents() { throw new Error("Unexpected read"); } });
  assert.equal(request(unsafe, "photoshop_export_png").error.code, "UNSUPPORTED_OPERATION");
});
check("old host is explicitly rejected", () => {
  for (const version of ["27.9", "27.9.99", "26.99"]) {
    const old = load({ version: "28.0" }, { ...runtime, host: { name: "photoshop", version } });
    assert.equal(request(old, "photoshop_ping").error.code, "UNSUPPORTED_HOST");
  }
});
check("unsupported payload fields cannot become executable commands", () => {
  const reply = plugin.handleRequest({ type: "request", protocol_version: 1, id: "x",
    operation: "photoshop_ping", script: "never execute" });
  assert.equal(reply.error.code, "INVALID_MESSAGE");
});
check("optional saved getter can be unavailable without filesystem fallback", () => {
  const doc = { ...documentFixture, get saved() { throw new Error("Getter unavailable"); } };
  assert.equal(request(load({ version: "27.10", documents: [doc], activeDocument: doc })).result.document.saved, null);
});
check("read failure exposes only fixed error text", () => {
  const app = { version: "27.10", get documents() { throw new Error("private document or token"); } };
  const reply = request(load(app));
  assert.equal(reply.error.code, "PHOTOSHOP_READ_FAILED");
  assert.equal(JSON.stringify(reply).includes("private"), false);
});
check("large documents fail without partial data", () => {
  const doc = { ...documentFixture, layers: Array.from({ length: 2001 }, (_, id) => leaf(id, "Layer")) };
  const reply = request(load({ version: "27.10", documents: [doc], activeDocument: doc }));
  assert.equal(reply.ok, false);
  assert.equal(reply.result, null);
  assert.equal(reply.error.code, "DOCUMENT_TOO_LARGE");
});
check("UTF-8 response limits include non-ASCII names", () => {
  assert.equal(plugin.byteLength("🐱猫"), 7);
  const reply = { ...request(plugin), result: { huge: "猫".repeat(100000) } };
  const bounded = JSON.parse(plugin.encodeResponse(reply));
  assert.equal(bounded.error.code, "DOCUMENT_TOO_LARGE");
  assert.equal(bounded.result, null);
});
check("invalid oversized request identifiers cannot inflate an error response", () => {
  const reply = plugin.handleRequest({ type: "request", protocol_version: 1,
    id: "x".repeat(262144), operation: "y".repeat(262144) });
  assert.equal(reply.error.code, "INVALID_MESSAGE");
  assert.ok(plugin.byteLength(plugin.encodeResponse(reply)) < 1024);
});
console.log("PLUGIN GETTER TESTS: " + tests + " passed");


// Exercise the real panel's click/event handlers without Photoshop or a network.
const DIAGNOSTIC_TOKEN = "T".repeat(64);
function panel(options = {}) {
  const logs = [], sockets = [], timers = new Map(), elements = {};
  let timerId = 0, clickHandlers = 0;
  for (const id of ["status", "storage-status", "versions", "diagnostic-detail", "pairing-token", "connect"]) {
    elements[id] = { textContent: "", value: "", addEventListener(type, callback) {
      assert.equal(type, "click");
      clickHandlers += 1;
      this.click = callback;
    } };
  }
  elements["pairing-token"].value = DIAGNOSTIC_TOKEN;
  class Socket {
    constructor(endpoint) {
      assert.equal(endpoint, "ws://localhost:43127");
      if (options.constructorError) throw options.constructorError;
      this.readyState = 0;
      this.sent = [];
      sockets.push(this);
    }
    send(raw) {
      this.sent.push(JSON.parse(raw));
      if (options.sendError) throw new Error(raw);
    }
    close() { this.readyState = 3; }
  }
  const capture = level => (...args) => {
    assert.ok(args.every(value => typeof value === "string"), "Never log raw error/event/payload objects.");
    logs.push(level + ": " + args.join(" "));
  };
  const context = {
    module: { exports: {} },
    console: { log: capture("log"), warn: capture("warn"), error: capture("error") },
    document: { getElementById: id => elements[id] },
    setTimeout: callback => { timers.set(++timerId, callback); return timerId; },
    clearTimeout: id => timers.delete(id),
    require(name) {
      if (name === "photoshop") return { app: { documents: [],
        get version() { throw new Error("Photoshop DOM version must not be read"); }
      } };
      if (name === "uxp") return {
        ...(options.environment || runtime),
        storage: { secureStorage: {
          async getItem() {
            if (options.storageError) throw options.storageError;
            return Uint8Array.from(DIAGNOSTIC_TOKEN, character => character.charCodeAt(0));
          },
          async setItem() { if (options.storageError) throw options.storageError; }
        } },
        entrypoints: { setup() {} }
      };
      throw new Error("Unexpected module");
    }
  };
  if (!options.missingWebSocket) context.WebSocket = Socket;
  vm.runInNewContext(source, context);
  return {
    logs, sockets, timers, elements,
    get clickHandlers() { return clickHandlers; },
    click: () => elements.connect.click(),
    detail: () => elements["diagnostic-detail"].textContent,
    open(socket = sockets.at(-1)) { socket.readyState = 1; socket.onopen(); },
    message(data, socket = sockets.at(-1)) { return socket.onmessage({ data: JSON.stringify(data) }); },
    assertSafe() {
      const output = logs.join("\n") + Object.values(elements).map(element => element.textContent).join("\n");
      assert.equal(output.includes(DIAGNOSTIC_TOKEN), false);
      assert.equal(output.includes('"token"'), false);
      assert.equal(output.includes('"type":"auth"'), false);
    }
  };
}

async function diagnosticTests() {
  async function checkPanel(name, test) {
    await test();
    tests += 1;
    console.log("PASS " + name);
  }
  await checkPanel("panel displays actual host and UXP runtime versions", async () => {
    const ui = panel({ environment: {
      host: { name: "photoshop", version: "27.10.0.26" },
      versions: { uxp: "uxp-9.1.0", plugin: "0.1.7" }
    } });
    assert.equal(ui.elements.versions.textContent, "Photoshop 27.10.0.26 · UXP uxp-9.1.0 · Bridge 0.1.0");
    ui.assertSafe();
  });
  await checkPanel("invalid host versions stay visible without displaying undefined or raw values", async () => {
    for (const version of [undefined, "invalid", DIAGNOSTIC_TOKEN]) {
      const ui = panel({ environment: { ...runtime, host: { name: "photoshop", version } } });
      assert.match(ui.elements.versions.textContent, /Photoshop version detection failed/);
      assert.equal(ui.elements.versions.textContent.includes("undefined"), false);
      await ui.click();
      ui.open();
      await ui.message({ type: "auth_result", protocol_version: 1, ok: true, error: null });
      await ui.message({ type: "request", protocol_version: 1, id: "detect-version", operation: "photoshop_ping" });
      assert.match(ui.detail(), /Could not detect.*UXP host.version/);
      assert.equal(ui.sockets[0].sent.at(-1).ok, false);
      ui.assertSafe();
    }
  });
  await checkPanel("panel initialization and actual connect-click path log construction and state", async () => {
    const ui = panel();
    assert.match(ui.logs.join("\n"), /Plugin panel initialized/);
    assert.equal(ui.clickHandlers, 1);
    await ui.click();
    assert.equal(ui.sockets.length, 1);
    const logs = ui.logs.join("\n");
    for (const marker of ["button clicked", "typeof WebSocket=function", "ws://localhost:43127",
                          "before new WebSocket", "constructor succeeded", "readyState=0"]) {
      assert.ok(logs.includes(marker), marker);
    }
    ui.open();
    assert.match(ui.logs.join("\n"), /WebSocket onopen; readyState=1/);
    assert.equal(ui.sockets[0].sent[0].token, DIAGNOSTIC_TOKEN);
    ui.assertSafe();
  });
  await checkPanel("constructor exceptions expose sanitized name/message/stack in console and panel", async () => {
    const failure = new Error("Access denied " + DIAGNOSTIC_TOKEN);
    failure.name = "SecurityError";
    failure.stack = "SecurityError at WebSocket\n" + JSON.stringify({ type: "auth", token: DIAGNOSTIC_TOKEN });
    const ui = panel({ constructorError: failure });
    await ui.click();
    assert.match(ui.detail(), /WebSocket constructor failed.*SecurityError.*Access denied/);
    assert.match(ui.logs.join("\n"), /error:.*stack=/);
    ui.assertSafe();
  });
  await checkPanel("unavailable WebSocket is visible without guessing the failure", async () => {
    const ui = panel({ missingWebSocket: true });
    await ui.click();
    assert.match(ui.logs.join("\n"), /typeof WebSocket=undefined/);
    assert.match(ui.detail(), /WebSocket constructor failed.*ReferenceError/);
    ui.assertSafe();
  });
  await checkPanel("onerror is visible and its subsequent close remains observable", async () => {
    const ui = panel();
    await ui.click();
    const socket = ui.sockets[0];
    socket.onerror({ error: new Error("Network denied " + DIAGNOSTIC_TOKEN) });
    assert.match(ui.detail(), /WebSocket onerror.*Network denied/);
    assert.equal(socket.onmessage, null);
    assert.equal(ui.timers.size, 0);
    socket.onclose({ code: 1006, reason: "Handshake failed", wasClean: false });
    assert.match(ui.detail(), /code=1006, reason=Handshake failed, wasClean=false/);
    ui.assertSafe();
  });
  await checkPanel("normal close code, reason and wasClean appear in panel and console", async () => {
    const ui = panel();
    await ui.click();
    ui.sockets[0].onclose({ code: 1000, reason: "Bridge stopped", wasClean: true });
    assert.match(ui.detail(), /code=1000, reason=Bridge stopped, wasClean=true/);
    assert.match(ui.logs.join("\n"), /log:.*Connection closed/);
    ui.assertSafe();
  });
  await checkPanel("untrusted close reasons cannot expose tokens or authentication payloads", async () => {
    const ui = panel();
    await ui.click();
    ui.sockets[0].onclose({ code: 1008, wasClean: false,
      reason: JSON.stringify({ type: "auth", protocol_version: 1, token: DIAGNOSTIC_TOKEN }) });
    assert.match(ui.detail(), /code=1008.*redacted.*wasClean=false/);
    ui.assertSafe();
  });
  await checkPanel("authentication rejection is distinct from a connection failure", async () => {
    const ui = panel();
    await ui.click();
    ui.open();
    await ui.message({ type: "auth_result", protocol_version: 1, ok: false,
      error: { code: "AUTH_FAILED", message: DIAGNOSTIC_TOKEN } });
    assert.match(ui.detail(), /Authentication rejected: code=AUTH_FAILED/);
    assert.match(ui.elements.status.textContent, /Pairing failed/);
    assert.equal(ui.detail().includes("Connection failed"), false);
    ui.assertSafe();
  });
  await checkPanel("authenticated messages log only allowlisted type and operation metadata", async () => {
    const ui = panel();
    await ui.click();
    ui.open();
    await ui.message({ type: "auth_result", protocol_version: 1, ok: true, error: null });
    assert.match(ui.detail(), /Connected; authentication accepted: code=OK/);
    await ui.message({ type: "request", protocol_version: 1, id: DIAGNOSTIC_TOKEN, operation: "photoshop_ping" });
    assert.match(ui.logs.join("\n"), /onmessage: type=request, operation=photoshop_ping/);
    assert.equal(ui.sockets[0].sent.length, 2);
    assert.equal(ui.timers.size, 0);
    ui.assertSafe();
  });
  await checkPanel("unexpected message metadata cannot smuggle a secret into logs", async () => {
    const ui = panel();
    await ui.click();
    await ui.message({ type: DIAGNOSTIC_TOKEN, protocol_version: 1, operation: DIAGNOSTIC_TOKEN });
    assert.match(ui.logs.join("\n"), /type=unexpected, operation=none\/unsupported/);
    ui.assertSafe();
  });
  await checkPanel("reconnect retires request handlers and stale close cannot overwrite current detail", async () => {
    const ui = panel();
    await ui.click();
    const old = ui.sockets[0];
    await ui.click();
    const detail = ui.detail();
    assert.equal(old.onmessage, null);
    assert.equal(old.onopen, null);
    old.onclose({ code: 1000, reason: "Previous socket", wasClean: true });
    assert.equal(ui.detail(), detail);
    assert.equal(ui.clickHandlers, 1);
    assert.equal(ui.timers.size, 1);
    ui.assertSafe();
  });
  await checkPanel("send exceptions containing an auth frame never print the frame", async () => {
    const ui = panel({ sendError: true });
    await ui.click();
    ui.open();
    assert.match(ui.detail(), /Authentication send failed.*redacted/);
    ui.assertSafe();
  });
  await checkPanel("secure-storage exceptions are redacted recoverable warnings", async () => {
    const ui = panel({ storageError: new Error("password=private-cache-value " + DIAGNOSTIC_TOKEN) });
    ui.elements["pairing-token"].value = "";
    await ui.click();
    assert.match(ui.logs.join("\n"), /warn:.*Secure pairing cache unavailable/);
    assert.equal(ui.logs.join("\n").includes("private-cache-value"), false);
    ui.assertSafe();
  });
  console.log("PLUGIN TESTS: " + tests + " passed (including panel diagnostics)");
}
diagnosticTests().catch(error => { console.error(error); process.exitCode = 1; });
