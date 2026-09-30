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
function png(width, height, colorType = 6) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width); header.writeUInt32BE(height, 4);
  header[8] = 8; header[9] = colorType;
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk("IHDR", header),
    chunk("IDAT", zlib.deflateSync(Buffer.alloc((width * (colorType === 2 ? 3 : 4) + 1) * height))), chunk("IEND", Buffer.alloc(0))]);
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
  const events = [], files = [], modalOptions = [], saves = [], resizes = [], imageResizes = [];
  const batchCalls = [];
  let pixelRead = 0, modal = false;
  const sourceInput = options.input || input;
  const sourceWidth = sourceInput.readUInt32BE(16), sourceHeight = sourceInput.readUInt32BE(20);
  let hasBackground = !!options.background || sourceInput[25] === 2;
  const previous = Object.freeze({ id: 7, saved: false, name: "Unsaved artwork", history: "unchanged" });
  let active = options.noDocument ? null : previous;
  let open = false;
  const autoClose = new Set();
  function maybe(stage) {
    if (options.fail === stage || (Array.isArray(options.fail) && options.fail.includes(stage))) {
      throw new Error("private path/token detail");
    }
  }
  const context = {
    isCancelled: options.cancel === "before",
    hostControl: {
      async registerAutoCloseDocument(id) { autoClose.add(id); events.push("register"); },
      async unregisterAutoCloseDocument(id) { autoClose.delete(id); events.push("unregister"); }
    }
  };
  const doc = {
    layers: [{ id: 9 }], activeLayers: [{ id: 9 }],
    get id() { assert.equal(open, true, "No DOM getters after closing the document"); return 8; },
    width: options.wrongSource ? sourceWidth + 1 : sourceWidth, height: sourceHeight,
    get backgroundLayer() {
      return hasBackground ? {
        async duplicate() { events.push("duplicate-background"); maybe("duplicate-background"); return {}; },
        async delete() {
          events.push("delete-background"); maybe("delete-background");
          if (!options.backgroundRemains) hasBackground = false;
        }
      } : null;
    },
    async resizeImage(...args) {
      events.push("resize-image"); imageResizes.push(args); maybe("resize-image");
      assert.equal(hasBackground, false);
      assert.equal(args[2], undefined);
      assert.ok(["bicubic", "nearest-neighbor"].includes(args[3]));
      if (!options.wrongResize) [doc.width, doc.height] = args;
      if (options.cancel === "resize-image") context.isCancelled = true;
    },
    async resizeCanvas(...args) {
      events.push("resize"); resizes.push(args); maybe("resize");
      [doc.width, doc.height] = args;
      if (options.cancel === "resize") context.isCancelled = true;
    },
    saveAs: { async png(file, config, asCopy) {
      events.push("export"); saves.push({ file, config, asCopy }); maybe("export");
      file.data = options.output || output;
      if (options.cancel === "export") context.isCancelled = true;
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
      doc.width = options.wrongSource ? sourceWidth + 1 : sourceWidth; doc.height = sourceHeight;
      open = true; active = doc;
      if (options.cancel === "open") context.isCancelled = true;
      return doc;
    }
  };
  const photoshop = { app, imaging: {
    async getPixels(settings) {
      events.push("get-pixels"); maybe("get-pixels");
      assert.equal(settings.documentID, 8);
      assert.deepEqual(JSON.parse(JSON.stringify(settings)), { documentID: 8,
        sourceBounds: { left: 0, top: 0, right: doc.width, bottom: doc.height },
        colorSpace: "RGB", componentSize: 8, applyAlpha: false });
      assert.equal(events.includes("resize"), false, "Capture alpha before padding");
      const bounds = options.pixelBounds || { left: 0, top: 0, right: doc.width, bottom: doc.height };
      const width = bounds.right - bounds.left, height = bounds.bottom - bounds.top;
      const components = options.pixelComponents || 4;
      const suppliedAlpha = options.alphas && options.alphas[pixelRead++];
      if (options.cancel === "get-pixels") context.isCancelled = true;
      return { level: options.pixelLevel || 0, sourceBounds: bounds,
        imageData: { width, height, components, colorSpace: "RGB", componentSize: 8, hasAlpha: components === 4,
          async getData(config) {
            events.push("pixel-data"); maybe("pixel-data");
            assert.equal(config.chunky, true);
            return Uint8Array.from(suppliedAlpha ? suppliedAlpha.flatMap(a => [40, 80, 120, a]) :
              options.pixelData || Buffer.alloc(width * height * components));
          },
          dispose() { events.push("dispose-pixels"); maybe("dispose-pixels"); }
        }
      };
    }
  }, action: { async batchPlay(commands, settings) {
    assert.equal(modal, true, "Native mutation must run inside executeAsModal");
    assert.equal(active, doc); assert.equal(hasBackground, false);
    events.push("batch-play"); batchCalls.push(JSON.parse(JSON.stringify({ commands, settings })));
    if (options.batchError) throw options.batchError;
    maybe("batch-play");
    if (options.cancel === "batch-play") context.isCancelled = true;
    return options.batchResults || [{}, {}];
  } }, constants: { PNGMethod: { QUICK: "quick" },
    ResampleMethod: { BICUBIC: "bicubic", NEARESTNEIGHBOR: "nearest-neighbor" }, AnchorPosition: { TOPLEFT: "top-left" } }, core: {
    async executeAsModal(callback, settings) {
      modalOptions.push(settings); maybe("modal");
      if (options.gate) await options.gate;
      try { modal = true; return await callback(context); }
      finally {
        modal = false;
        if (autoClose.size) { open = false; active = previous; autoClose.clear(); events.push("auto-close"); }
      }
    }
  }};
  if (options.capability === false) delete photoshop.action;
  if (options.imagingCapability === false) delete photoshop.imaging;
  if (options.wrongActiveLayer) doc.activeLayers = [{ id: 10 }];
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
  return { processing, plugin, events, files, previous, app, resizes, imageResizes, saves, modalOptions, batchCalls,
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
  for (const colorType of [2, 6]) {
    for (const [label, sw, sh, aw, ah] of [["portrait", 4, 8, 2, 4], ["landscape", 8, 4, 4, 2]]) {
      await check((colorType === 2 ? "RGB " : "RGBA ") + label + " fit shrinks proportionally before padding", async () => {
        const source = png(sw, sh, colorType), h = load({ input: source });
        const reply = await h.plugin.dispatchRequest(wire({ ...params(), image_base64: source.toString("base64"), mode: "fit" }));
        assert.equal(reply.ok, true);
        assert.deepEqual(h.imageResizes, [[aw, ah, undefined, "bicubic"]]);
        assert.equal(reply.result.resampled_alpha_crc32, crc32(Buffer.alloc(aw * ah)));
        assert.deepEqual(h.resizes, [[4, 4]]);
        assert.ok(h.events.indexOf("resize-image") < h.events.indexOf("resize"));
        assert.deepEqual(h.files[0].data, source);
        assert.equal(h.app.activeDocument, h.previous);
        if (colorType === 2) {
          assert.ok(h.events.indexOf("duplicate-background") < h.events.indexOf("delete-background"));
          assert.ok(h.events.indexOf("delete-background") < h.events.indexOf("resize-image"));
        }
        cleaned(h);
      });
    }
    for (const [label, size] of [["exact size", 4], ["smaller than canvas", 2]]) {
      await check((colorType === 2 ? "RGB " : "RGBA ") + label + " fit never upscales", async () => {
        const source = png(size, size, colorType), h = load({ input: source });
        const reply = await h.processing.processImage({ ...params(), image_base64: source.toString("base64"), mode: "fit" });
        assert.deepEqual(h.imageResizes, []);
        assert.equal(h.events.includes("get-pixels"), false);
        assert.equal("resampled_alpha_crc32" in reply, false);
        assert.deepEqual(h.resizes, [[4, 4]]);
        cleaned(h);
      });
    }
  }
  await check("RGB preserve_size converts only the private background layer before padding", async () => {
    const source = png(2, 2, 2), h = load({ input: source });
    await h.processing.processImage({ ...params(), image_base64: source.toString("base64"), mode: "preserve_size" });
    assert.deepEqual(h.imageResizes, []);
    assert.ok(h.events.indexOf("delete-background") < h.events.indexOf("resize"));
    assert.equal(h.previous.saved, false);
    cleaned(h);
  });
  await check("opaque RGB exports are returned for bounded Python RGBA encoding", async () => {
    const source = png(2, 2, 2), h = load({ input: source, output: source });
    const reply = await h.processing.processImage({ ...params(), width_px: 2, height_px: 2,
      image_base64: source.toString("base64"), mode: "fit" });
    assert.deepEqual(Buffer.from(reply.png_base64, "base64"), source);
    assert.deepEqual(h.imageResizes, []);
    cleaned(h);
  });
  for (const [sw, sh, width, height] of [[4, 8, 5, 4], [8, 4, 4, 5]]) {
    await check("odd fit padding " + width + "x" + height + " puts the extra pixel at right/bottom", async () => {
      const source = png(sw, sh), h = load({ input: source, output: png(width, height) });
      await h.processing.processImage({ ...params(), image_base64: source.toString("base64"),
        width_px: width, height_px: height, mode: "fit" });
      assert.deepEqual(h.resizes, [[4, 4], [width, height, "top-left"]]);
      cleaned(h);
    });
  }
  await check("non-integral aspect ratio uses half-up pixel rounding", async () => {
    const source = png(7, 3), h = load({ input: source });
    await h.processing.processImage({ ...params(), image_base64: source.toString("base64"), mode: "fit" });
    assert.deepEqual(h.imageResizes, [[4, 2, undefined, "bicubic"]]);
    cleaned(h);
  });
  await check("invalid modes fail before creating private files", async () => {
    for (const mode of [undefined, null, true, 1, "", "FIT", "crop", [], {}]) {
      const h = load(), reply = await h.plugin.dispatchRequest(wire({ ...params(), mode }));
      assert.equal(reply.ok, false);
      assert.equal(reply.error.code, "INVALID_MODE");
      assert.equal(h.files.length, 0);
    }
  });
  for (const colorType of [2, 6]) {
    for (const resample of ["bicubic", "nearest"]) {
      await check((colorType === 2 ? "RGB " : "RGBA ") + "explicit " + resample + " uses the native method and preserves odd centering", async () => {
        const source = png(4, 8, colorType), h = load({ input: source, output: png(5, 4) });
        const reply = await h.processing.processImage({ ...params(), width_px: 5,
          image_base64: source.toString("base64"), mode: "fit", resample });
        assert.deepEqual(h.imageResizes, [[2, 4, undefined, resample === "nearest" ? "nearest-neighbor" : "bicubic"]]);
        assert.deepEqual(h.resizes, [[4, 4], [5, 4, "top-left"]]);
        assert.equal(h.events.includes("get-pixels"), resample === "bicubic");
        assert.equal("resampled_alpha_crc32" in reply, resample === "bicubic");
        cleaned(h);
      });
    }
  }
  await check("invalid resample values fail before private files or document access", async () => {
    for (const resample of [undefined, null, true, 1, "", "BICUBIC", "bilinear", [], {}]) {
      const h = load(), reply = await h.plugin.dispatchRequest(wire({ ...params(), mode: "fit", resample }));
      assert.equal(reply.ok, false); assert.equal(reply.error.code, "INVALID_RESAMPLE");
      assert.equal(h.files.length, 0); assert.equal(h.events.length, 0);
    }
  });
  await check("both resamplers keep preserve_size and no-upscale calls free of resizeImage", async () => {
    for (const mode of ["preserve_size", "fit"]) {
      for (const resample of ["bicubic", "nearest"]) {
        const h = load();
        const reply = await h.processing.processImage({ ...params(), mode, resample });
        assert.deepEqual(h.imageResizes, []);
        assert.equal(h.events.includes("get-pixels"), false);
        assert.equal("resampled_alpha_crc32" in reply, false);
        cleaned(h);
      }
    }
  });
  await check("bicubic checksum retains partial alpha and restores trimmed empty borders", async () => {
    const source = png(4, 8), h = load({ input: source,
      pixelBounds: { left: 1, top: 1, right: 2, bottom: 3 },
      pixelData: [10, 20, 30, 64, 40, 50, 60, 128] });
    const reply = await h.processing.processImage({ ...params(), image_base64: source.toString("base64"), mode: "fit" });
    assert.equal(reply.resampled_alpha_crc32, crc32(Buffer.from([0, 0, 0, 64, 0, 128, 0, 0])));
    assert.ok(h.events.indexOf("resize-image") < h.events.indexOf("get-pixels"));
    assert.ok(h.events.indexOf("dispose-pixels") < h.events.indexOf("resize"));
    cleaned(h);
  });
  await check("RGB bicubic captures required native partial alpha before canvas expansion without a second read", async () => {
    const source = png(4, 8, 2), alpha = [240, 255, 255, 255, 255, 255, 255, 240];
    const h = load({ input: source, pixelData: alpha.flatMap(a => [40, 80, 120, a]) });
    const reply = await h.processing.processImage({ ...params(), image_base64: source.toString("base64"), mode: "fit" });
    assert.equal(reply.resampled_alpha_crc32, crc32(Buffer.from(alpha)));
    assert.equal("native_diagnostics" in reply, false);
    assert.equal(h.events.filter(e => e === "get-pixels").length, 1);
    assert.ok(h.events.indexOf("resize-image") < h.events.indexOf("get-pixels"));
    assert.ok(h.events.indexOf("dispose-pixels") < h.events.indexOf("resize"));
    assert.deepEqual(h.imageResizes, [[2, 4, undefined, "bicubic"]]);
    assert.deepEqual(h.resizes, [[4, 4]]);
    cleaned(h);
  });
  await check("bicubic checksum supports opaque RGB buffers and empty transparent buffers", async () => {
    for (const [extra, alpha] of [
      [{ pixelComponents: 3 }, Array(8).fill(255)],
      [{ pixelBounds: { left: 0, top: 0, right: 0, bottom: 0 } }, Array(8).fill(0)]
    ]) {
      const source = png(4, 8), h = load({ input: source, ...extra });
      const reply = await h.processing.processImage({ ...params(), image_base64: source.toString("base64"), mode: "fit" });
      assert.equal(reply.resampled_alpha_crc32, crc32(Buffer.from(alpha)));
      cleaned(h);
    }
  });
  for (const colorType of [2, 6]) {
    for (const fail of ["get-pixels", "pixel-data", "dispose-pixels"]) {
      await check((colorType === 2 ? "RGB " : "RGBA ") + fail + " failure rejects export and cleans the private document", async () => {
        const source = png(4, 8, colorType), h = load({ input: source, fail });
        const reply = await h.plugin.dispatchRequest(wire({ ...params(), image_base64: source.toString("base64"), mode: "fit" }));
        assert.equal(reply.ok, false); assert.equal(reply.error.code, "PHOTOSHOP_PROCESSING_FAILED");
        assert.equal(h.saves.length, 0); assert.equal(h.app.activeDocument, h.previous);
        if (fail !== "get-pixels") assert.ok(h.events.includes("dispose-pixels"));
        cleaned(h);
      });
    }
  }
  await check("invalid native pixel bounds, depth buffer, or cache level fail closed", async () => {
    for (const colorType of [2, 6]) {
      for (const extra of [{ pixelBounds: { left: -1, top: 0, right: 1, bottom: 4 } },
                         { pixelData: [1] }, { pixelLevel: 1 }, { pixelComponents: 2 }]) {
        const source = png(4, 8, colorType), h = load({ input: source, ...extra });
        const reply = await h.plugin.dispatchRequest(wire({ ...params(), image_base64: source.toString("base64"), mode: "fit" }));
        assert.equal(reply.ok, false); assert.equal(h.saves.length, 0);
        assert.ok(h.events.includes("dispose-pixels")); cleaned(h);
      }
    }
  });
  await check("cancellation during native alpha capture cannot export", async () => {
    const source = png(4, 8), h = load({ input: source, cancel: "get-pixels" });
    const reply = await h.plugin.dispatchRequest(wire({ ...params(), image_base64: source.toString("base64"), mode: "fit" }));
    assert.equal(reply.ok, false); assert.equal(h.saves.length, 0);
    assert.ok(h.events.includes("dispose-pixels")); cleaned(h);
  });
  await check("explicit preserve_size still refuses to shrink oversized artwork", async () => {
    const source = png(8, 4), h = load({ input: source });
    await assert.rejects(h.processing.processImage({ ...params(), image_base64: source.toString("base64"),
      mode: "preserve_size" }), { code: "CANVAS_TOO_SMALL" });
    assert.equal(h.files.length, 0);
  });
  for (const fail of ["duplicate-background", "delete-background", "resize-image"]) {
    await check(fail + " normalization failure restores the original document and cleans resources", async () => {
      const source = png(8, 4, 2), h = load({ input: source, fail });
      const reply = await h.plugin.dispatchRequest(wire({ ...params(), image_base64: source.toString("base64"), mode: "fit" }));
      assert.equal(reply.error.code, "PHOTOSHOP_PROCESSING_FAILED");
      assert.equal(h.app.activeDocument, h.previous);
      assert.equal(h.saves.length, 0);
      cleaned(h);
    });
  }
  await check("cancellation after fit resize cannot export", async () => {
    const source = png(8, 4), h = load({ input: source, cancel: "resize-image" });
    const reply = await h.plugin.dispatchRequest(wire({ ...params(), image_base64: source.toString("base64"), mode: "fit" }));
    assert.equal(reply.ok, false); assert.equal(h.saves.length, 0); cleaned(h);
  });
  await check("unexpected host resize or background conversion is rejected", async () => {
    for (const extra of [{ wrongResize: true }, { backgroundRemains: true }]) {
      const source = png(8, 4, 2), h = load({ input: source, ...extra });
      const reply = await h.plugin.dispatchRequest(wire({ ...params(), image_base64: source.toString("base64"), mode: "fit" }));
      assert.equal(reply.ok, false); assert.equal(h.saves.length, 0); cleaned(h);
    }
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
    const h = load({ capability: false }), reply = await h.plugin.dispatchRequest(wire({ ...params(), remove_background: true }));
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
  await check("unsupported PNG color type and invalid signature are rejected before opening", async () => {
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
  const removalParams = source => ({ ...params(), image_base64: source.toString("base64"), remove_background: true });
  const fixedCommands = [
    { _obj: "autoCutout", sampleAllLayers: false },
    { _obj: "make", new: { _class: "channel" }, at: { _ref: "channel", _enum: "channel", _value: "mask" },
      using: { _enum: "userMaskEnabled", _value: "revealSelection" } }
  ];
  for (const color of [2, 6]) {
    await check((color === 2 ? "RGB" : "RGBA") + " removal captures native alpha before normalization and preserves fixed descriptors", async () => {
      const source = png(2, 2, color), before = color === 2 ? [255, 255, 255, 255] : [0, 128, 255, 255];
      const after = color === 2 ? [0, 255, 255, 255] : [0, 0, 255, 255];
      const h = load({ input: source, alphas: [before, after] });
      const reply = await h.plugin.dispatchRequest(wire(removalParams(source)));
      assert.equal(reply.ok, true);
      assert.equal(reply.result.background_removal_requested, true);
      assert.equal(reply.result.background_removal_completed, true);
      assert.deepEqual(h.batchCalls, [{ commands: fixedCommands, settings: {} }]);
      assert.equal(reply.result.removal_evidence.removed_pixels, 1);
      assert.equal(reply.result.removal_evidence.visible_pixels, color === 2 ? 4 : 3);
      assert.equal(reply.result.removal_evidence.foreground_pixels, color === 2 ? 3 : 2);
      assert.equal(reply.result.removal_evidence.before_alpha_crc32, crc32(before));
      assert.equal(reply.result.removal_evidence.after_alpha_crc32, crc32(after));
      assert.equal(reply.result.resampled_alpha_crc32, crc32(after));
      assert.equal(h.events.filter(e => e === "get-pixels").length, 2);
      assert.ok(h.events.indexOf("get-pixels") < h.events.indexOf("batch-play"));
      assert.ok(h.events.lastIndexOf("get-pixels") < h.events.indexOf("resize"));
      assert.equal(h.app.activeDocument, h.previous); cleaned(h);
    });
  }
  for (const removed of [1, 2, 3]) {
    await check("RGB native removal threshold " + removed + "/2000", async () => {
      const source = png(40, 50, 2), before = Array(2000).fill(255), after = [...before];
      after.fill(0, 0, removed);
      const h = load({ input: source, output: png(40, 50), alphas: [before, after] });
      const reply = await h.plugin.dispatchRequest(wire({ ...removalParams(source), width_px: 40, height_px: 50 }));
      assert.equal(reply.ok, removed >= 2);
      if (removed < 2) {
        assert.equal(reply.error.code, "OUTPUT_VALIDATION_FAILED");
        assert.equal(reply.error.reason, "BACKGROUND_REMOVAL_NO_OP");
        assert.equal(h.resizes.length, 0); assert.equal(h.saves.length, 0);
      }
      cleaned(h);
    });
  }
  for (const [label, before, after, reason] of [
    ["opaque no-op", [255,255,255,255], [255,255,255,255], "BACKGROUND_REMOVAL_NO_OP"],
    ["RGBA existing alpha", [0,128,255,255], [0,128,255,255], "BACKGROUND_REMOVAL_NO_OP"],
    ["empty subject", [255,255,255,255], [0,0,0,0], "BACKGROUND_REMOVAL_EMPTY_SUBJECT"],
    ["increased alpha", [0,255,255,255], [255,0,255,255], "BACKGROUND_REMOVAL_ALPHA_INCREASED"],
    ["insignificant alpha drop", [23,255,255,255], [8,255,255,255], "BACKGROUND_REMOVAL_NO_OP"],
    ["insufficiently cleared pixel", [255,255,255,255], [9,255,255,255], "BACKGROUND_REMOVAL_NO_OP"]
  ]) {
    await check(label + " rejects before resizing, padding or export", async () => {
      const h = load({ alphas: [before, after] });
      const reply = await h.plugin.dispatchRequest(wire(removalParams(input)));
      assert.equal(reply.error.code, "OUTPUT_VALIDATION_FAILED"); assert.equal(reply.error.reason, reason);
      assert.equal(reply.result, null); assert.equal(h.saves.length, 0); assert.equal(h.resizes.length, 0);
      assert.equal(h.imageResizes.length, 0); cleaned(h);
    });
  }
  for (const resample of ["bicubic", "nearest"]) {
    await check("removal then fit uses " + resample + " and captures artwork alpha before padding", async () => {
      const source = png(4, 8, 2), before = Array(32).fill(255);
      const after = Array(16).fill(0).concat(Array(16).fill(255));
      const scaled = [0,0,0,0,255,255,255,255];
      const h = load({ input: source, alphas: [before, after, scaled] });
      const reply = await h.plugin.dispatchRequest(wire({ ...removalParams(source), mode: "fit", resample }));
      assert.equal(reply.ok, true);
      assert.equal(reply.result.resampled_alpha_crc32, crc32(scaled));
      assert.deepEqual(h.imageResizes, [[2,4,undefined,resample === "bicubic" ? "bicubic" : "nearest-neighbor"]]);
      assert.ok(h.events.indexOf("batch-play") < h.events.indexOf("resize-image"));
      assert.ok(h.events.lastIndexOf("get-pixels") > h.events.indexOf("resize-image"));
      assert.equal(h.events.filter(e => e === "dispose-pixels").length, 3); cleaned(h);
    });
  }
  for (const [label, extra, code] of [
    ["missing imaging API", { imagingCapability: false }, "BACKGROUND_REMOVAL_UNAVAILABLE"],
    ["wrong active layer", { wrongActiveLayer: true }, "PHOTOSHOP_PROCESSING_FAILED"],
    ["native error result", { batchResults: [{ _obj: "error", result: -1, message: "private" }] }, "PHOTOSHOP_PROCESSING_FAILED"],
    ["native rejected promise", { batchError: new Error("private") }, "PHOTOSHOP_PROCESSING_FAILED"],
    ["cancelled result", { batchResults: [{ _obj: "error", result: -128 }] }, "PHOTOSHOP_CANCELLED"],
    ["cancelled rejection", { batchError: { number: -128, message: "private" } }, "PHOTOSHOP_CANCELLED"],
    ["cancelled context", { cancel: "batch-play" }, "PHOTOSHOP_CANCELLED"],
    ["cancelled export", { cancel: "export" }, "PHOTOSHOP_CANCELLED"],
    ["incomplete native results", { batchResults: [{}] }, "PHOTOSHOP_PROCESSING_FAILED"]
  ]) {
    await check(label + " yields the correct structured failure and cleans resources", async () => {
      const h = load({ alphas: [[255,255,255,255], [0,255,255,255]], ...extra });
      const reply = await h.plugin.dispatchRequest(wire(removalParams(input)));
      assert.equal(reply.error.code, code); assert.equal(reply.result, null);
      assert.equal(JSON.stringify(reply).includes("private"), false);
      if (label !== "cancelled export") assert.equal(h.saves.length, 0);
      cleaned(h);
    });
  }
  for (const [label, extra, code] of [
    ["no-op", { alphas: [[255,255,255,255], [255,255,255,255]] }, "OUTPUT_VALIDATION_FAILED"],
    ["cancel", { alphas: [[255,255,255,255]], batchResults: [{ _obj: "error", result: -128 }] }, "PHOTOSHOP_CANCELLED"],
    ["operation", { alphas: [[255,255,255,255]], batchError: new Error("private") }, "PHOTOSHOP_PROCESSING_FAILED"]
  ]) {
    await check(label + " retains original failure when document and private-file cleanup both fail", async () => {
      const h = load({ ...extra, fail: ["close", "delete"] });
      const reply = await h.plugin.dispatchRequest(wire(removalParams(input)));
      assert.equal(reply.error.code, code); assert.equal(reply.result, null);
      assert.ok(h.events.includes("auto-close"));
      assert.equal(h.events.filter(e => e === "delete").length, 2);
      assert.equal(h.app.activeDocument, h.previous);
      assert.equal(h.isOpen(), false);
    });
  }
  await check("removal rejects every caller-controlled descriptor surface before filesystem access", async () => {
    for (const field of ["ActionJSON", "commands", "selection", "_target", "_options", "sampleAllLayers"]) {
      const h = load();
      const reply = await h.plugin.dispatchRequest(wire({ ...removalParams(input), [field]: "arbitrary" }));
      assert.equal(reply.error.code, "INVALID_MESSAGE");
      assert.equal(h.files.length, 0); assert.equal(h.batchCalls.length, 0);
    }
  });
  await check("remove_background false never invokes native removal even when its APIs are absent", async () => {
    const h = load({ capability: false, imagingCapability: false });
    const reply = await h.plugin.dispatchRequest(wire(params()));
    assert.equal(reply.ok, true); assert.equal(reply.result.background_removal_completed, false);
    assert.equal("removal_evidence" in reply.result, false); assert.equal(h.batchCalls.length, 0);
    cleaned(h);
  });
  await check("RGB baseline must be fully opaque before invoking removal", async () => {
    const source = png(2, 2, 2), h = load({ input: source, alphas: [[0,255,255,255]] });
    const reply = await h.plugin.dispatchRequest(wire(removalParams(source)));
    assert.equal(reply.error.code, "OUTPUT_VALIDATION_FAILED");
    assert.equal(reply.error.reason, "BACKGROUND_REMOVAL_EVIDENCE_MISMATCH");
    assert.equal(h.batchCalls.length, 0); assert.equal(h.saves.length, 0); cleaned(h);
  });
  await check("invalid removal exports never return a candidate", async () => {
    for (const exported of [png(4, 4, 2), png(5, 4), Buffer.from("invalid")]) {
      const h = load({ alphas: [[255,255,255,255], [0,255,255,255]], output: exported });
      const reply = await h.plugin.dispatchRequest(wire(removalParams(input)));
      assert.equal(reply.error.code, "OUTPUT_VALIDATION_FAILED");
      assert.equal(reply.error.reason, "BACKGROUND_REMOVAL_OUTPUT_INVALID");
      assert.equal(reply.result, null); cleaned(h);
    }
  });
  await check("cancelled pixel capture is preserved through disposal and close failures", async () => {
    const h = load({ alphas: [[255,255,255,255]], cancel: "get-pixels", fail: ["dispose-pixels", "close"] });
    const reply = await h.plugin.dispatchRequest(wire(removalParams(input)));
    assert.equal(reply.error.code, "PHOTOSHOP_CANCELLED");
    assert.ok(h.events.includes("dispose-pixels")); assert.ok(h.events.includes("auto-close"));
    assert.equal(h.saves.length, 0); cleaned(h);
  });
  await check("removal busy state resets after a no-op and cleanup failure", async () => {
    const options = { alphas: [[255,255,255,255], [255,255,255,255]], fail: "delete" };
    const h = load(options);
    assert.equal((await h.plugin.dispatchRequest(wire(removalParams(input)))).error.code, "OUTPUT_VALIDATION_FAILED");
    options.fail = null;
    const second = await h.plugin.dispatchRequest(wire(params()));
    assert.equal(second.ok, true); assert.equal(h.isOpen(), false);
  });
  console.log(count + " Phase 2 UXP checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
