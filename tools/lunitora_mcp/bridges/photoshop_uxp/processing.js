/* Staging normalization: no arbitrary paths, descriptors, cloud APIs or user-file access. */
"use strict";
const photoshop = require("photoshop");
const uxp = require("uxp");
const MAX_BYTES = 24 * 1024 * 1024;
const MAX_BASE64_BYTES = 4 * Math.ceil(MAX_BYTES / 3);
const MAX_DIMENSION = 2048;
const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const VALUES = new Int16Array(128).fill(-1);
for (let i = 0; i < ALPHABET.length; i++) VALUES[ALPHABET.charCodeAt(i)] = i;
let busy = false;
let sequence = 0;

function fail(code) { const error = new Error(code); error.code = code; throw error; }

function encode(bytes) {
  // A small scratch buffer avoids millions of string nodes at the 24 MiB limit.
  // These are local encoding fragments; the transport still sends one JSON message.
  const parts = [], buffer = new Uint8Array(8192);
  let used = 0;
  for (let i = 0; i < bytes.length; i += 3) {
    const n = (bytes[i] << 16) | ((bytes[i + 1] || 0) << 8) | (bytes[i + 2] || 0);
    buffer[used++] = ALPHABET.charCodeAt((n >>> 18) & 63);
    buffer[used++] = ALPHABET.charCodeAt((n >>> 12) & 63);
    buffer[used++] = i + 1 < bytes.length ? ALPHABET.charCodeAt((n >>> 6) & 63) : 61;
    buffer[used++] = i + 2 < bytes.length ? ALPHABET.charCodeAt(n & 63) : 61;
    if (used === buffer.length) {
      parts.push(String.fromCharCode.apply(null, buffer));
      used = 0;
    }
  }
  if (used) parts.push(String.fromCharCode.apply(null, buffer.subarray(0, used)));
  return parts.join("");
}

function decode(text) {
  if (typeof text !== "string" || !text.length || text.length > MAX_BASE64_BYTES ||
      text.length % 4) fail("INVALID_MESSAGE");
  const padding = text.endsWith("==") ? 2 : text.endsWith("=") ? 1 : 0;
  const length = text.length / 4 * 3 - padding;
  if (!length || length > MAX_BYTES) fail("INVALID_MESSAGE");
  const bytes = new Uint8Array(length);
  const value = index => {
    const code = text.charCodeAt(index);
    return code < VALUES.length ? VALUES[code] : -1;
  };
  let offset = 0;
  for (let i = 0; i < text.length; i += 4) {
    const last = i + 4 === text.length;
    const a = value(i), b = value(i + 1);
    const c = last && padding === 2 ? 0 : value(i + 2);
    const d = last && padding ? 0 : value(i + 3);
    if (a < 0 || b < 0 || c < 0 || d < 0 ||
        (last && ((padding === 2 && (b & 15)) || (padding === 1 && (c & 3))))) fail("INVALID_MESSAGE");
    bytes[offset++] = (a << 2) | (b >>> 4);
    if (offset < length) bytes[offset++] = ((b & 15) << 4) | (c >>> 2);
    if (offset < length) bytes[offset++] = ((c & 3) << 6) | d;
  }
  return bytes;
}

function dimensions(bytes) {
  const signature = [137, 80, 78, 71, 13, 10, 26, 10];
  if (bytes.length < 33 || signature.some((value, i) => bytes[i] !== value) ||
      bytes[12] !== 73 || bytes[13] !== 72 || bytes[14] !== 68 || bytes[15] !== 82 ||
      bytes[24] !== 8 || ![2, 6].includes(bytes[25]) || bytes[26] || bytes[27] || bytes[28]) fail("INVALID_IMAGE");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const width = view.getUint32(16), height = view.getUint32(20);
  if (!width || !height || width > MAX_DIMENSION || height > MAX_DIMENSION) fail("INVALID_IMAGE");
  return { width, height, colorType: bytes[25] };
}

async function alphaChecksum(documentId, width, height) {
  // Read the native result before padding/export, without another resize or matte.
  const pixels = await photoshop.imaging.getPixels({ documentID: documentId,
    sourceBounds: { left: 0, top: 0, right: width, bottom: height },
    colorSpace: "RGB", componentSize: 8, applyAlpha: false });
  const data = pixels.imageData;
  try {
    const bounds = pixels.sourceBounds;
    if (pixels.level !== 0 || !bounds ||
        ![bounds.left, bounds.top, bounds.right, bounds.bottom].every(Number.isInteger) ||
        bounds.left < 0 || bounds.top < 0 || bounds.right > width || bounds.bottom > height ||
        bounds.right < bounds.left || bounds.bottom < bounds.top ||
        data.width !== bounds.right - bounds.left || data.height !== bounds.bottom - bounds.top ||
        data.colorSpace !== "RGB" || data.componentSize !== 8 ||
        ![3, 4].includes(data.components) || data.hasAlpha !== (data.components === 4)) {
      fail("PHOTOSHOP_PROCESSING_FAILED");
    }
    const raw = await data.getData({ chunky: true });
    if (!(raw instanceof Uint8Array) || raw.length !== data.width * data.height * data.components) {
      fail("PHOTOSHOP_PROCESSING_FAILED");
    }
    // getPixels can trim empty borders; put those zeros back into the checksum.
    const alpha = new Uint8Array(width * height);
    for (let y = 0; y < data.height; y++) {
      for (let x = 0; x < data.width; x++) {
        alpha[(y + bounds.top) * width + x + bounds.left] = data.components === 4
          ? raw[(y * data.width + x) * 4 + 3] : 255;
      }
    }
    let crc = 0xffffffff;
    for (const value of alpha) {
      crc ^= value;
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
    return (crc ^ 0xffffffff) >>> 0;
  } finally {
    if (data) data.dispose();
  }
}

async function processImage(parameters) {
  const required = ["height_px", "image_base64", "remove_background", "width_px"];
  if (!parameters || !required.every(key => Object.prototype.hasOwnProperty.call(parameters, key)) ||
      Object.keys(parameters).some(key => ![...required, "mode", "resample"].includes(key)) ||
      typeof parameters.remove_background !== "boolean") fail("INVALID_MESSAGE");
  const mode = Object.prototype.hasOwnProperty.call(parameters, "mode") ? parameters.mode : "preserve_size";
  if (!["preserve_size", "fit"].includes(mode)) fail("INVALID_MODE");
  const resample = Object.prototype.hasOwnProperty.call(parameters, "resample") ? parameters.resample : "bicubic";
  if (!["bicubic", "nearest"].includes(resample)) fail("INVALID_RESAMPLE");
  const { width_px: width, height_px: height } = parameters;
  if (![width, height].every(n => Number.isInteger(n) && n >= 1 && n <= MAX_DIMENSION)) fail("INVALID_DIMENSIONS");
  if (parameters.remove_background) fail("BACKGROUND_REMOVAL_UNAVAILABLE");
  const input = decode(parameters.image_base64);
  const source = dimensions(input);
  let artworkWidth = source.width, artworkHeight = source.height;
  if (width < source.width || height < source.height) {
    if (mode === "preserve_size") fail("CANVAS_TOO_SMALL");
    // One scale factor, half-up integer rounding, never upsample either axis.
    if (width * source.height <= height * source.width) {
      artworkWidth = width;
      artworkHeight = Math.max(1, Math.floor((2 * source.height * width + source.width) / (2 * source.width)));
    } else {
      artworkHeight = height;
      artworkWidth = Math.max(1, Math.floor((2 * source.width * height + source.height) / (2 * source.height)));
    }
  }
  if (busy) fail("BUSY");
  busy = true;
  let inputFile = null, outputFile = null, resampledAlpha;
  try {
    // Only plugin-private temporary entries; the peer cannot supply a filename or URL.
    const folder = await uxp.storage.localFileSystem.getTemporaryFolder();
    const name = "lunitora-" + Date.now() + "-" + (++sequence);
    inputFile = await folder.createFile(name + "-input.png", { overwrite: false });
    outputFile = await folder.createFile(name + "-output.png", { overwrite: false });
    await inputFile.write(input.buffer, { format: uxp.storage.formats.binary });
    await photoshop.core.executeAsModal(async context => {
      let doc = null, documentId = null;
      const previous = photoshop.app.documents.length ? photoshop.app.activeDocument : null;
      try {
        if (context.isCancelled) fail("PHOTOSHOP_PROCESSING_FAILED");
        doc = await photoshop.app.open(inputFile);
        // Host cleanup also runs if cancellation prevents a normal DOM close.
        documentId = doc.id;
        await context.hostControl.registerAutoCloseDocument(documentId);
        if (doc.width !== source.width || doc.height !== source.height) fail("INVALID_IMAGE");
        if (doc.backgroundLayer) {
          if (source.colorType !== 2) fail("INVALID_IMAGE");
          // Duplicate becomes a regular pixel layer. Only the private copy is edited.
          const background = doc.backgroundLayer;
          await background.duplicate();
          await background.delete();
          if (doc.backgroundLayer) fail("PHOTOSHOP_PROCESSING_FAILED");
        }
        if (context.isCancelled) fail("PHOTOSHOP_PROCESSING_FAILED");
        if (artworkWidth !== source.width || artworkHeight !== source.height) {
          await doc.resizeImage(artworkWidth, artworkHeight, undefined,
            resample === "bicubic" ? photoshop.constants.ResampleMethod.BICUBIC
              : photoshop.constants.ResampleMethod.NEARESTNEIGHBOR);
          if (doc.width !== artworkWidth || doc.height !== artworkHeight) fail("PHOTOSHOP_PROCESSING_FAILED");
          if (context.isCancelled) fail("PHOTOSHOP_PROCESSING_FAILED");
          if (resample === "bicubic") {
            resampledAlpha = await alphaChecksum(documentId, artworkWidth, artworkHeight);
          }
        }
        if (context.isCancelled) fail("PHOTOSHOP_PROCESSING_FAILED");
        // First add symmetric padding, then put any odd extra pixel at right/bottom.
        const evenWidth = width - ((width - artworkWidth) % 2);
        const evenHeight = height - ((height - artworkHeight) % 2);
        await doc.resizeCanvas(evenWidth, evenHeight);
        if (evenWidth !== width || evenHeight !== height) {
          if (context.isCancelled) fail("PHOTOSHOP_PROCESSING_FAILED");
          await doc.resizeCanvas(width, height, photoshop.constants.AnchorPosition.TOPLEFT);
        }
        if (context.isCancelled) fail("PHOTOSHOP_PROCESSING_FAILED");
        await doc.saveAs.png(outputFile, {
          method: photoshop.constants.PNGMethod.QUICK, compression: 6, interlaced: false
        }, true);
      } finally {
        try {
          if (doc) {
            await doc.closeWithoutSaving();
            await context.hostControl.unregisterAutoCloseDocument(documentId);
          }
        } finally {
          if (previous) photoshop.app.activeDocument = previous;
        }
      }
    }, { commandName: "Create Lunitora staging candidate", timeOut: 1 });
    const output = new Uint8Array(await outputFile.read({ format: uxp.storage.formats.binary }));
    if (output.length > MAX_BYTES) fail("IMAGE_TOO_LARGE");
    const size = dimensions(output);
    if (size.width !== width || size.height !== height) fail("PHOTOSHOP_PROCESSING_FAILED");
    return { png_base64: encode(output), width_px: width, height_px: height,
      background_removal_requested: false, background_removal_completed: false,
      ...(resampledAlpha === undefined ? {} : { resampled_alpha_crc32: resampledAlpha }) };
  } finally {
    try {
      // Cleanup failures prevent success; the caller never receives a candidate.
      if (inputFile) await inputFile.delete();
    } finally {
      try { if (outputFile) await outputFile.delete(); }
      finally { busy = false; }
    }
  }
}

module.exports = { processImage };
