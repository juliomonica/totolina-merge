/* Actual UXP modules, mocked Photoshop/private storage; no Adobe host or npm. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const zlib = require("node:zlib");
const processingSource = fs.readFileSync(path.join(__dirname, "../bridges/photoshop_uxp/processing.js"), "utf8");
const pluginSource = fs.readFileSync(path.join(__dirname, "../bridges/photoshop_uxp/index.js"), "utf8");
let count = 0;
async function check(name, test) { await test(); count++; console.log("PASS " + name); }
function crc32(bytes) {
  let crc = 0xffffffff;
  for (const b of bytes) {
    crc ^= b;
    for (let n = 0; n < 8; n++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const bytes = Buffer.concat([Buffer.alloc(4), Buffer.from(type), data, Buffer.alloc(4)]);
  bytes.writeUInt32BE(data.length);
  bytes.writeUInt32BE(crc32(bytes.subarray(4, -4)), bytes.length - 4);
  return bytes;
}
function png(width, height) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width); header.writeUInt32BE(height, 4);
  header[8] = 8; header[9] = 6;
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk("IHDR", header),
    chunk("IDAT", zlib.deflateSync(Buffer.alloc((width * 4 + 1) * height))), chunk("IEND", Buffer.alloc(0))]);
}
const input = png(2, 2), output = png(4, 4);
const params = () => ({ image_base64: input.toString("base64"), width_px: 4, height_px: 4, remove_background: false });
const wire = parameters => ({ type: "request", protocol_version: 1, id: "processing-test",
  operation: "photoshop_process_image", parameters });
const MAX_BYTES = 24 * 1024 * 1024;
const MAX_BASE64_BYTES = 4 * Math.ceil(MAX_BYTES / 3);
const MAX_PAYLOAD_BYTES = MAX_BASE64_BYTES + 1024;
function sizedPng(data, size) {
  const text = Buffer.alloc(size - data.length - 12, 120);
  text[1] = 0; // Valid tEXt keyword, separator and text.
  return Buffer.concat([data.subarray(0, -12), chunk("tEXt", text), data.subarray(-12)]);
}

function load(options = {}) {
  const events = [], files = [], modalOptions = [], saves = [], resizes = [];
  const previous = Object.freeze({ id: 7, saved: false, name: "Unsaved artwork", history: "unchanged" });
  let active = options.noDocument ? null : previous;
  let open = false;
  const autoClose = new Set();
  function maybe(stage) { if (options.fail === stage) throw new Error("private path/token detail"); }
  const context = {
    isCancelled: options.cancel === "before",
    hostControl: {
      async registerAutoCloseDocument(id) { autoClose.add(id); events.push("register"); },
      async unregisterAutoCloseDocument(id) { autoClose.delete(id); events.push("unregister"); }
    }
  };
  const doc = {
    get id() { assert.equal(open, true, "No DOM getters after closing the document"); return 8; },
    width: options.wrongSource ? 3 : 2, height: 2, backgroundLayer: options.background ? {} : null,
    async resizeCanvas(...args) {
      events.push("resize"); resizes.push(args); maybe("resize");
      [doc.width, doc.height] = args;
      if (options.cancel === "resize") context.isCancelled = true;
    },
    saveAs: { async png(file, config, asCopy) {
      events.push("export"); saves.push({ file, config, asCopy }); maybe("export");
      file.data = options.output || output;
    }},
    async closeWithoutSaving() {
      events.push("close"); maybe("close"); open = false; active = previous;
    }
  };
  const app = {
    get documents() { return options.noDocument && !open ? [] : open ? [previous, doc] : [previous]; },
    get activeDocument() { return active; },
    set activeDocument(value) { assert.equal(value, previous); active = value; events.push("restore"); },
    async open(file) {
      events.push("open"); assert.equal(file, files[files.length - 2]); maybe("open");
      doc.width = options.wrongSource ? 3 : 2; doc.height = 2;
      open = true; active = doc;
      if (options.cancel === "open") context.isCancelled = true;
      return doc;
    }
  };
  const photoshop = { app, constants: { PNGMethod: { QUICK: "quick" } }, core: {
    async executeAsModal(callback, settings) {
      modalOptions.push(settings); maybe("modal");
      if (options.gate) await options.gate;
      try { return await callback(context); }
      finally {
        if (autoClose.size) { open = false; active = previous; autoClose.clear(); events.push("auto-close"); }
      }
    }
  }};
  const uxp = {
    host: { name: "photoshop", version: options.version || "27.10.0" },
    versions: { uxp: "mock", plugin: "0.1.0" },
    storage: { formats: { binary: "binary" }, localFileSystem: {
      async getTemporaryFolder() {
        maybe("folder");
        return { async createFile(name, settings) {
          assert.match(name, /^lunitora-\d+-\d+-(input|output)\.png$/);
          assert.equal(settings.overwrite, false);
          maybe(files.length ? "create-output" : "create-input");
          const file = {
            name, data: null, deleted: false,
            async write(data, format) {
              maybe("write"); assert.equal(format.format, "binary"); file.data = Buffer.from(data);
            },
            async read(format) {
              maybe("read"); assert.equal(format.format, "binary");
              return Uint8Array.from(file.data).buffer;
            },
            async delete() { events.push("delete"); maybe("delete"); file.deleted = true; }
          };
          files.push(file); return file;
        }};
      }
    }}
  };
  let processing;
  function run(source) {
    const scope = { module: { exports: {} }, Uint8Array, DataView,
      require(name) {
        if (name === "photoshop") return photoshop;
        if (name === "uxp") return uxp;
        if (name === "./processing.js") return processing;
        throw new Error("Unexpected module " + name);
      }};
    vm.runInNewContext(source, scope);
    return scope.module.exports;
  }
  processing = run(processingSource);
  const plugin = run(pluginSource);
  return { processing, plugin, events, files, previous, app, resizes, saves, modalOptions,
    isOpen: () => open };
}
function cleaned(host) {
  assert.equal(host.isOpen(), false);
  assert.ok(host.files.every(file => file.deleted));
}

(async () => {
  await check("structured dispatch opens only private copy, expands canvas and exports PNG as copy", async () => {
    const h = load(), reply = await h.plugin.dispatchRequest(wire(params()));
    assert.equal(reply.ok, true);
    assert.equal(reply.id, "processing-test");
    assert.equal(reply.operation, "photoshop_process_image");
    assert.equal(reply.error, null);
    assert.deepEqual(Buffer.from(reply.result.png_base64, "base64"), output);
    assert.equal(reply.result.width_px, 4); assert.equal(reply.result.height_px, 4);
    assert.equal(reply.result.background_removal_requested, false);
    assert.equal(reply.result.background_removal_completed, false);
    assert.deepEqual(h.files[0].data, input);
    assert.deepEqual(h.resizes, [[4, 4]]);
    assert.equal(h.saves[0].asCopy, true);
    assert.deepEqual(JSON.parse(JSON.stringify(h.saves[0].config)), { method: "quick", compression: 6, interlaced: false });
    assert.equal(h.modalOptions[0].timeOut, 1); // Adobe API uses seconds.
    assert.equal(h.app.activeDocument, h.previous);
    assert.equal(h.previous.saved, false);
    assert.ok(h.events.indexOf("register") < h.events.indexOf("resize"));
    assert.ok(h.events.indexOf("close") < h.events.indexOf("unregister"));
    cleaned(h);
  });
  await check("no existing document is required", async () => {
    const h = load({ noDocument: true });
    await h.processing.processImage(params()); cleaned(h);
    assert.equal(h.events.includes("restore"), false);
  });
  await check("same-size canvas and original transparent padding are not trimmed", async () => {
    const h = load({ output: input });
    await h.processing.processImage({ ...params(), width_px: 2, height_px: 2 });
    assert.deepEqual(h.resizes, [[2, 2]]); cleaned(h);
  });
  await check("arbitrary paths or additional action parameters never reach Photoshop", async () => {
    for (const extra of [{ path: "C:/assets/input.png" }, { batchPlay: [] }]) {
      const h = load();
      await assert.rejects(h.processing.processImage({ ...params(), ...extra }), { code: "INVALID_MESSAGE" });
      assert.equal(h.files.length, 0);
    }
  });
  await check("dimensions reject booleans, strings, fractions and out-of-bounds values", async () => {
    const h = load();
    for (const width_px of [true, "4", 0, -1, 1.5, 2049, null]) {
      await assert.rejects(h.processing.processImage({ ...params(), width_px }), { code: "INVALID_DIMENSIONS" });
    }
    assert.equal(h.files.length, 0);
  });
  await check("smaller canvas is rejected before opening a temporary file", async () => {
    const h = load();
    await assert.rejects(h.processing.processImage({ ...params(), width_px: 1 }), { code: "CANVAS_TOO_SMALL" });
    assert.equal(h.files.length, 0);
  });
  await check("background removal returns explicit unsupported error without export", async () => {
    const h = load(), reply = await h.plugin.dispatchRequest(wire({ ...params(), remove_background: true }));
    assert.equal(reply.error.code, "BACKGROUND_REMOVAL_UNAVAILABLE");
    assert.equal(reply.ok, false); assert.equal(reply.result, null); assert.equal(h.files.length, 0);
  });
  await check("malformed and oversized base64 are rejected", async () => {
    const h = load();
    for (const image_base64 of ["", "?", "Zh==", "Zm9=", "====", "AA=A", "AA==AAAA", "AĀAA",
                                "AAA\n", "AAA", "A".repeat(MAX_BASE64_BYTES + 4)]) {
      await assert.rejects(h.processing.processImage({ ...params(), image_base64 }), { code: "INVALID_MESSAGE" });
    }
    assert.equal(h.files.length, 0);
  });
  await check("non-RGBA PNG and invalid signature are rejected before opening", async () => {
    const h = load();
    for (const offset of [0, 25]) {
      const data = Buffer.from(input); data[offset] = 0;
      await assert.rejects(h.processing.processImage({ ...params(), image_base64: data.toString("base64") }),
        { code: "INVALID_IMAGE" });
    }
    assert.equal(h.files.length, 0);
  });
  for (const fail of ["folder", "create-input", "create-output", "write", "modal", "open", "resize", "export", "read"]) {
    await check(fail + " failure is sanitized and all created resources are cleaned", async () => {
      const h = load({ fail }), reply = await h.plugin.dispatchRequest(wire(params()));
      assert.equal(reply.ok, false); assert.equal(reply.result, null);
      assert.equal(reply.error.code, "PHOTOSHOP_PROCESSING_FAILED");
      assert.equal(JSON.stringify(reply).includes("private"), false); cleaned(h);
    });
  }
  for (const cancel of ["before", "open", "resize"]) {
    await check("cancellation at " + cancel + " closes only the temporary document", async () => {
      const h = load({ cancel }), reply = await h.plugin.dispatchRequest(wire(params()));
      assert.equal(reply.ok, false); assert.equal(h.saves.length, 0); cleaned(h);
    });
  }
  await check("host auto-close remains registered if normal close fails", async () => {
    const h = load({ fail: "close" }), reply = await h.plugin.dispatchRequest(wire(params()));
    assert.equal(reply.ok, false); assert.ok(h.events.includes("auto-close")); cleaned(h);
    assert.equal(h.app.activeDocument, h.previous);
  });
  await check("private-file cleanup failure cannot become a successful result", async () => {
    const h = load({ fail: "delete" }), reply = await h.plugin.dispatchRequest(wire(params()));
    assert.equal(reply.ok, false); assert.equal(reply.result, null);
    assert.equal(h.isOpen(), false); assert.equal(h.events.filter(e => e === "delete").length, 2);
  });
  await check("opaque background layer or unexpected imported size fails before resizing", async () => {
    for (const options of [{ background: true }, { wrongSource: true }]) {
      const h = load(options), reply = await h.plugin.dispatchRequest(wire(params()));
      assert.equal(reply.error.code, "INVALID_IMAGE"); assert.equal(h.resizes.length, 0); cleaned(h);
    }
  });
  await check("wrong-size or oversized exports are rejected", async () => {
    for (const output of [input, Buffer.alloc(MAX_BYTES + 1)]) {
      const h = load({ output }), reply = await h.plugin.dispatchRequest(wire(params()));
      assert.equal(reply.ok, false); assert.equal(reply.result, null); cleaned(h);
    }
  });
  await check("processing concurrency is bounded and busy state resets", async () => {
    let release;
    const h = load({ gate: new Promise(resolve => { release = resolve; }) });
    const first = h.processing.processImage(params());
    await assert.rejects(h.processing.processImage(params()), { code: "BUSY" });
    release(); await first; await h.processing.processImage(params()); cleaned(h);
  });
  await check("processing rejects incompatible hosts and malformed request envelopes", async () => {
    const h = load({ version: "27.9" });
    assert.equal((await h.plugin.dispatchRequest(wire(params()))).error.code, "UNSUPPORTED_HOST");
    for (const change of [{ protocol_version: 2 }, { extra: true }, { id: "" }]) {
      assert.equal((await h.plugin.dispatchRequest({ ...wire(params()), ...change })).error.code, "INVALID_MESSAGE");
    }
    assert.equal(h.files.length, 0);
  });
  await check("async dispatch preserves both legacy read-only responses without loading image files", async () => {
    const h = load({ noDocument: true });
    for (const operation of ["photoshop_ping", "photoshop_get_active_document"]) {
      const request = { type: "request", protocol_version: 1, id: "old-client", operation };
      assert.deepEqual(await h.plugin.dispatchRequest(request), h.plugin.handleRequest(request));
    }
    assert.equal(h.files.length, 0);
  });
  for (const size of [MAX_BYTES - 1, MAX_BYTES, MAX_BYTES + 1]) {
    await check("input PNG boundary " + size + " bytes", async () => {
      const data = sizedPng(input, size), h = load();
      const reply = await h.plugin.dispatchRequest(wire({ ...params(), image_base64: data.toString("base64") }));
      if (size <= MAX_BYTES) {
        assert.equal(reply.ok, true);
        assert.deepEqual(h.files[0].data, data);
      } else {
        assert.equal(reply.error.code, "INVALID_MESSAGE");
        assert.equal(h.files.length, 0);
      }
      cleaned(h);
    });
    await check("exported PNG boundary " + size + " bytes", async () => {
      const data = sizedPng(output, size), h = load({ output: data });
      const reply = await h.plugin.dispatchRequest(wire(params()));
      if (size <= MAX_BYTES) {
        assert.equal(reply.ok, true);
        assert.equal(reply.result.png_base64, data.toString("base64"));
        const raw = h.plugin.encodeResponse(reply);
        assert.ok(Buffer.byteLength(raw) <= MAX_PAYLOAD_BYTES);
        assert.equal(JSON.parse(raw).ok, true);
      } else {
        assert.equal(reply.error.code, "IMAGE_TOO_LARGE");
        assert.equal(reply.result, null);
      }
      cleaned(h);
    });
  }
  await check("Base64 preserves every byte value and all padding lengths", async () => {
    const pattern = Buffer.from(Array.from({ length: 256 }, (_, i) => i));
    for (const extra of [0, 1, 2]) {
      // The mock only reads IHDR; Python separately verifies full PNG structure/CRCs.
      const data = Buffer.concat([input, pattern, Buffer.alloc(extra)]);
      const h = load({ output: data });
      const reply = await h.processing.processImage({ ...params(), width_px: 2, height_px: 2,
        image_base64: data.toString("base64") });
      assert.deepEqual(h.files[0].data, data);
      assert.equal(reply.png_base64, data.toString("base64"));
      cleaned(h);
    }
  });
  await check("processing response UTF-8 message boundary is exactly 32 MiB plus 1 KiB", async () => {
    const h = load();
    const response = { type: "response", protocol_version: 1, id: "猫🐱",
      operation: "photoshop_process_image", ok: true, error: null, result: { padding: "" } };
    const overhead = Buffer.byteLength(JSON.stringify(response));
    for (const size of [MAX_PAYLOAD_BYTES - 1, MAX_PAYLOAD_BYTES, MAX_PAYLOAD_BYTES + 1]) {
      response.result.padding = "x".repeat(size - overhead);
      assert.equal(Buffer.byteLength(JSON.stringify(response)), size);
      const raw = h.plugin.encodeResponse(response);
      const reply = JSON.parse(raw);
      if (size <= MAX_PAYLOAD_BYTES) {
        assert.equal(Buffer.byteLength(raw), size);
        assert.equal(reply.ok, true);
      } else {
        assert.equal(reply.ok, false);
        assert.equal(reply.result, null);
        assert.ok(Buffer.byteLength(raw) < 1024);
      }
    }
  });
  console.log(count + " Phase 2A UXP checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
