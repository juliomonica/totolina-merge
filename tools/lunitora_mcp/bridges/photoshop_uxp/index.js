/* Compatible read-only getters; separate bounded processing of temporary copies. */
"use strict";

console.log("[Lunitora UXP] Plugin script initialization started");

const photoshop = require("photoshop");
const uxp = require("uxp");
const { host, versions } = uxp;
const VERSION = "0.1.0";
const PROTOCOL_VERSION = 1;
const ENDPOINT = "ws://localhost:43127";
const MAX_INSPECTION_BYTES = 262144;
// Match Python: canonical Base64 for one 24 MiB PNG plus 1 KiB of JSON metadata.
const MAX_PAYLOAD_BYTES = 4 * Math.ceil((24 * 1024 * 1024) / 3) + 1024;
const MAX_LAYERS = 2000;
const MAX_DEPTH = 64;
const STORAGE_KEY = "lunitora.phase1.pairing";
const HOST_VERSION_ERROR = "Could not detect the Photoshop host version from UXP host.version.";
const HOST_NAME_ERROR = "Could not detect the Photoshop host name from UXP host.name.";
const PROCESS_OPERATION = "photoshop_process_image";
const ALLOWED = new Set(["photoshop_ping", "photoshop_get_active_document", PROCESS_OPERATION]);
const MESSAGES = Object.freeze({
  INVALID_MESSAGE: "Invalid bridge request.",
  UNSUPPORTED_OPERATION: "Only the two read-only Photoshop operations are supported.",
  PHOTOSHOP_READ_FAILED: "Photoshop could not read the current document.",
  DOCUMENT_TOO_LARGE: "Document exceeds the bounded inspection limits.",
  UNSUPPORTED_HOST: "Photoshop 27.10 or newer is required."
});

let diagnosticDetail = null;

function safeDiagnostic(value, secret = "") {
  if (typeof value !== "string") return "unavailable";
  // Never pass raw events, errors, messages or auth frames to the console.
  let text = secret ? value.split(secret).join("[redacted]") : value;
  if (/(?:token|password|secret|authorization)["'\\\s]*[:=]/i.test(text)) {
    return "[redacted sensitive detail]";
  }
  text = text.replace(/[A-Za-z0-9_-]{64,}/g, "[redacted]");
  return text.replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, 4096);
}

function diagnostic(level, stage, error = null, secret = "", show = true) {
  const details = [];
  if (error) {
    for (const field of ["name", "message", "stack"]) {
      try {
        if (typeof error[field] === "string") {
          details.push(field + "=" + safeDiagnostic(error[field], secret));
        }
      } catch (_) { details.push(field + "=unavailable"); }
    }
  }
  const safeStage = safeDiagnostic(stage, secret);
  console[level]("[Lunitora UXP] " + safeStage + (details.length ? " | " + details.join(" | ") : ""));
  if (show && diagnosticDetail) {
    const visible = details.filter(detail => !detail.startsWith("stack="));
    diagnosticDetail.textContent = safeStage + (visible.length ? " | " + visible.join(" | ").slice(0, 500) : "");
  }
}

function socketState(ws) {
  try { return typeof ws.readyState === "number" ? ws.readyState : "unavailable"; }
  catch (_) { return "unavailable"; }
}

function closedDiagnostic(event, show = true) {
  const code = event && typeof event.code === "number" ? event.code : "unavailable";
  const clean = event && typeof event.wasClean === "boolean" ? event.wasClean : "unavailable";
  const reason = event && typeof event.reason === "string" ? safeDiagnostic(event.reason) : "unavailable";
  diagnostic(clean === true ? "log" : "warn",
    "Connection closed: code=" + code + ", reason=" + reason + ", wasClean=" + clean, null, "", show);
}

function fail(code) {
  const error = new Error(MESSAGES[code]);
  error.code = code;
  throw error;
}

function readHostVersion() {
  let value;
  try { value = host.version; }
  catch (_) { return null; }
  if (typeof value !== "string") return null;
  const version = value.trim();
  const match = version.length < 100 && version.match(/^(\d+)\.(\d+)(?:\.\d+)*$/);
  if (!match) return null;
  const major = Number(match[1]), minor = Number(match[2]);
  if (!Number.isSafeInteger(major) || !Number.isSafeInteger(minor)) return null;
  return { version, major, minor };
}

function supportsHost(version) {
  return version && (version.major > 27 || (version.major === 27 && version.minor >= 10));
}

function readHostName() {
  try {
    const name = host.name;
    return typeof name === "string" && name.trim().length > 0 && name.length < 100 ? name : null;
  } catch (_) { return null; }
}

function optionalString(getter) {
  try {
    const value = getter();
    return value == null ? null : String(value);
  } catch (_) {
    return null;
  }
}

function ping(version, hostName) {
  return {
    host_name: hostName,
    photoshop_version: version.version,
    host_version: version.version,
    uxp_version: optionalString(() => versions.uxp),
    plugin_version: optionalString(() => versions.plugin) || "unavailable"
  };
}

function readActiveDocument() {
  const app = photoshop.app;
  if (app.documents.length === 0) return { has_document: false, document: null };
  const doc = app.activeDocument;
  if (!doc) return { has_document: false, document: null };
  let count = 0;
  function layersOf(collection, depth) {
    const layers = [];
    if (!collection) return layers;
    if (collection.length && depth > MAX_DEPTH) fail("DOCUMENT_TOO_LARGE");
    for (let index = 0; index < collection.length; index += 1) {
      count += 1;
      if (count > MAX_LAYERS) fail("DOCUMENT_TOO_LARGE");
      const layer = collection[index];
      layers.push({
        id: layer.id,
        name: layer.name,
        kind: String(layer.kind),
        children: layersOf(layer.layers, depth + 1)
      });
    }
    return layers;
  }
  const layers = layersOf(doc.layers, 1);
  const artboards = [];
  const sourceArtboards = doc.artboards;
  if (sourceArtboards) {
    if (sourceArtboards.length > MAX_LAYERS) fail("DOCUMENT_TOO_LARGE");
    for (let index = 0; index < sourceArtboards.length; index += 1) {
      artboards.push({ id: sourceArtboards[index].id, name: sourceArtboards[index].name });
    }
  }
  let saved = null;
  try {
    const state = doc.saved;
    if (typeof state === "boolean") saved = state;
  } catch (_) { /* Optional getter; never inspect the filesystem as a fallback. */ }
  return {
    has_document: true,
    document: {
      id: doc.id,
      name: doc.name,
      width_px: doc.width,
      height_px: doc.height,
      saved,
      top_level_layer_count: layers.length,
      recursive_layer_count: count,
      layers,
      artboard_count: artboards.length,
      artboards
    }
  };
}

function handleRequest(request) {
  const response = {
    type: "response",
    protocol_version: PROTOCOL_VERSION,
    id: request && typeof request.id === "string" && request.id.length <= 64 ? request.id : "",
    operation: request && typeof request.operation === "string" && request.operation.length <= 64 ? request.operation : "",
    ok: false,
    result: null,
    error: null
  };
  try {
    if (!request || request.type !== "request" || request.protocol_version !== PROTOCOL_VERSION ||
        typeof request.id !== "string" || !request.id.length || request.id.length > 64 ||
        Object.keys(request).sort().join(",") !== "id,operation,protocol_version,type") {
      fail("INVALID_MESSAGE");
    }
    if (!ALLOWED.has(request.operation) || request.operation === PROCESS_OPERATION) fail("UNSUPPORTED_OPERATION");
    const version = readHostVersion();
    const hostName = readHostName();
    if (!version || !hostName) {
      const message = !version ? HOST_VERSION_ERROR : HOST_NAME_ERROR;
      response.error = { code: "HOST_DETECTION_FAILED", message };
      diagnostic("error", message);
      return response;
    }
    if (!supportsHost(version)) fail("UNSUPPORTED_HOST");
    response.result = request.operation === "photoshop_ping" ? ping(version, hostName) : readActiveDocument();
    response.ok = true;
  } catch (error) {
    const code = error && Object.prototype.hasOwnProperty.call(MESSAGES, error.code)
      ? error.code : "PHOTOSHOP_READ_FAILED";
    response.error = { code, message: MESSAGES[code] };
  }
  return response;
}

async function dispatchRequest(request) {
  if (!request || request.operation !== PROCESS_OPERATION) return handleRequest(request);
  const response = {
    type: "response", protocol_version: PROTOCOL_VERSION,
    id: typeof request.id === "string" && request.id.length <= 64 ? request.id : "",
    operation: PROCESS_OPERATION, ok: false, result: null, error: null
  };
  if (request.type !== "request" || request.protocol_version !== PROTOCOL_VERSION ||
      !response.id || Object.keys(request).sort().join(",") !== "id,operation,parameters,protocol_version,type") {
    response.error = { code: "INVALID_MESSAGE", message: "Invalid processing request." };
    return response;
  }
  const hostCheck = handleRequest({ type: "request", protocol_version: PROTOCOL_VERSION,
    id: request.id, operation: "photoshop_ping" });
  if (!hostCheck.ok) { response.error = hostCheck.error; return response; }
  try {
    response.result = await require("./processing.js").processImage(request.parameters);
    response.ok = true;
  } catch (error) {
    const errors = {
      INVALID_MESSAGE: "Invalid processing request.",
      INVALID_IMAGE: "Only bounded non-interlaced RGB/RGBA8 PNG is supported.",
      INVALID_MODE: "Processing mode must be preserve_size or fit.",
      INVALID_RESAMPLE: "Resample must be bicubic or nearest.",
      INVALID_DIMENSIONS: "Canvas dimensions must be integers from 1 through 2048.",
      CANVAS_TOO_SMALL: "Canvas would crop the source.",
      IMAGE_TOO_LARGE: "PNG exceeds the 24 MiB processing limit.",
      BACKGROUND_REMOVAL_UNAVAILABLE: "Native Photoshop background-removal capability is unavailable.",
      OUTPUT_VALIDATION_FAILED: "The removal result failed alpha validation.",
      PHOTOSHOP_CANCELLED: "Photoshop processing was cancelled.",
      BUSY: "A temporary image is already being processed.",
      PHOTOSHOP_PROCESSING_FAILED: "Photoshop could not process the temporary image."
    };
    const code = error && Object.prototype.hasOwnProperty.call(errors, error.code)
      ? error.code : "PHOTOSHOP_PROCESSING_FAILED";
    response.error = { code, message: errors[code] };
    if (code === "OUTPUT_VALIDATION_FAILED" && ["BACKGROUND_REMOVAL_NO_OP",
      "BACKGROUND_REMOVAL_EMPTY_SUBJECT", "BACKGROUND_REMOVAL_ALPHA_INCREASED",
      "BACKGROUND_REMOVAL_EVIDENCE_MISMATCH", "BACKGROUND_REMOVAL_OUTPUT_OPAQUE",
      "BACKGROUND_REMOVAL_OUTPUT_INVALID"].includes(error.reason)) {
      response.error.reason = error.reason;
    }
  }
  return response;
}

// JSON contains escaped control characters; this counts UTF-8 without a Node dependency.
function byteLength(text) {
  let bytes = 0;
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index);
    if (code < 0x80) bytes += 1;
    else if (code < 0x800) bytes += 2;
    else if (code >= 0xD800 && code <= 0xDBFF && index + 1 < text.length &&
             text.charCodeAt(index + 1) >= 0xDC00 && text.charCodeAt(index + 1) <= 0xDFFF) {
      bytes += 4;
      index += 1;
    } else bytes += 3;
  }
  return bytes;
}

function encodeResponse(response) {
  let raw = JSON.stringify(response);
  const limit = response.operation === PROCESS_OPERATION ? MAX_PAYLOAD_BYTES : MAX_INSPECTION_BYTES;
  if (byteLength(raw) > limit) {
    raw = JSON.stringify({
      type: "response", protocol_version: PROTOCOL_VERSION,
      id: response.id, operation: response.operation, ok: false, result: null,
      error: { code: "DOCUMENT_TOO_LARGE", message: MESSAGES.DOCUMENT_TOO_LARGE }
    });
  }
  return raw;
}

let socket = null;
let generation = 0;
let authTimer = null;
const RECONNECT_INTERVAL_MS = 5000;
let reconnectTimer = null;
let connecting = false;
let destroyed = false;

function cancelReconnect() {
  if (reconnectTimer !== null) clearTimeout(reconnectTimer);
  reconnectTimer = null;
}

function disconnect() {
  generation += 1;
  connecting = false;
  if (authTimer !== null) clearTimeout(authTimer);
  authTimer = null;
  if (socket) {
    socket.onopen = socket.onmessage = socket.onerror = null;
    // Keep only a diagnostic callback so an onerror-triggered close is observable.
    const closedGeneration = generation;
    socket.onclose = event => closedDiagnostic(event, generation === closedGeneration && socket === null);
    try { socket.close(); }
    catch (error) { diagnostic("warn", "WebSocket close raised an exception", error); }
    socket = null;
  }
}

function initializePanel() {
  diagnosticDetail = document.getElementById("diagnostic-detail");
  diagnostic("log", "Plugin panel initializing");
  const status = document.getElementById("status");
  const storageStatus = document.getElementById("storage-status");
  const input = document.getElementById("pairing-token");
  const hostName = optionalString(() => host.name) || "Host unavailable";
  const hostLabel = hostName.toLowerCase() === "photoshop" ? "Photoshop" : hostName;
  const version = readHostVersion();
  document.getElementById("versions").textContent =
    safeDiagnostic(hostLabel) + " " + (version ? version.version : "version detection failed") +
    " · UXP " + safeDiagnostic(optionalString(() => versions.uxp)) + " · Bridge " + VERSION;

  function scheduleReconnect() {
    if (destroyed || reconnectTimer !== null) return;
    const retryGeneration = generation;
    const timer = setTimeout(() => {
      // clearTimeout cannot retract a callback already queued by the host.
      if (destroyed || retryGeneration !== generation || reconnectTimer !== timer) return;
      reconnectTimer = null;
      void connect(true);
    }, RECONNECT_INTERVAL_MS);
    reconnectTimer = timer;
  }

  async function connect(automatic = false) {
    if (destroyed || (automatic && (connecting || socket))) return;
    cancelReconnect();
    diagnostic("log", automatic ? "Automatic reconnect" : "Connect / Reconnect button clicked");
    diagnostic("log", "typeof WebSocket=" + typeof WebSocket + "; endpoint=" + ENDPOINT);
    disconnect();
    connecting = true;
    const current = generation;
    // Background startup never consumes an operator's partially entered token.
    let token = automatic ? "" : input.value.trim();
    if (!automatic) input.value = "";
    if (!token) {
      try {
        const bytes = await uxp.storage.secureStorage.getItem(STORAGE_KEY);
        token = Array.from(bytes, value => String.fromCharCode(value)).join("");
      } catch (error) { diagnostic("warn", "Secure pairing cache unavailable", error); }
    }
    if (current !== generation) return;
    if (!/^[A-Za-z0-9_-]{64}$/.test(token)) {
      connecting = false;
      status.textContent = "Enter the pairing token from local setup.";
      diagnostic("warn", "Pairing token missing or invalid");
      return;
    }
    status.textContent = "Connecting…";
    let ws;
    diagnostic("log", "Connecting to " + ENDPOINT + "; before new WebSocket");
    try {
      ws = new WebSocket(ENDPOINT);
      diagnostic("log", "WebSocket constructor succeeded; readyState=" + socketState(ws));
    } catch (error) {
      connecting = false;
      status.textContent = "Connection failed. Check the local bridge and plugin network permission.";
      diagnostic("error", "WebSocket constructor failed", error, token);
      scheduleReconnect();
      return;
    }
    socket = ws;
    let authenticated = false;
    authTimer = setTimeout(() => {
      if (current !== generation) return;
      diagnostic("warn", "WebSocket connection/authentication timeout; readyState=" + socketState(ws));
      disconnect();
      status.textContent = "Waiting for ChatGPT/Codex. Retrying automatically.";
      scheduleReconnect();
    }, 10000);
    ws.onopen = () => {
      if (current !== generation) return;
      diagnostic("log", "WebSocket onopen; readyState=" + socketState(ws));
      try {
        ws.send(JSON.stringify({ type: "auth", protocol_version: PROTOCOL_VERSION, token }));
      } catch (error) {
        diagnostic("error", "Authentication send failed", error, token);
        disconnect();
        scheduleReconnect();
      }
    };
    ws.onmessage = async event => {
      if (current !== generation) return;
      let message;
      try {
        if (typeof event.data !== "string" || byteLength(event.data) > MAX_PAYLOAD_BYTES) {
          throw new Error("Invalid frame");
        }
        message = JSON.parse(event.data);
        if ((!message || message.operation !== PROCESS_OPERATION) && byteLength(event.data) > MAX_INSPECTION_BYTES) {
          throw new Error("Invalid frame");
        }
        const type = message && ["auth_result", "request"].includes(message.type) ? message.type : "unexpected";
        const operation = message && ALLOWED.has(message.operation) ? message.operation : "none/unsupported";
        diagnostic("log", "WebSocket onmessage: type=" + type + ", operation=" + operation);
        if (!message || message.protocol_version !== PROTOCOL_VERSION) throw new Error("Invalid version");
      } catch (error) {
        diagnostic("error", "Invalid WebSocket message", error, token);
        disconnect();
        status.textContent = "Invalid bridge message. Disconnected.";
        scheduleReconnect();
        return;
      }
      if (!authenticated) {
        if (message.type !== "auth_result" || message.ok !== true) {
          const allowedCodes = ["AUTH_FAILED", "INVALID_MESSAGE", "PAYLOAD_TOO_LARGE", "UNSUPPORTED_OPERATION"];
          const code = message.error && allowedCodes.includes(message.error.code) ? message.error.code : "UNKNOWN";
          diagnostic("error", "Authentication rejected: code=" + code);
          disconnect();
          status.textContent = "Pairing failed. Re-enter the local token.";
          // A rejected credential needs operator repair, not repeated auth traffic.
          return;
        }
        authenticated = true;
        connecting = false;
        cancelReconnect();
        clearTimeout(authTimer);
        authTimer = null;
        status.textContent = "Connected · inspection and staging candidates";
        diagnostic("log", "Connected; authentication accepted: code=OK");
        // No document requests are handled before authentication succeeds.
        const pairedToken = token;
        token = "";
        try {
          await uxp.storage.secureStorage.setItem(STORAGE_KEY, pairedToken);
          if (current === generation) storageStatus.textContent = "Pairing saved securely on this computer.";
        } catch (error) {
          diagnostic("warn", "Secure pairing cache write unavailable", error, pairedToken, current === generation);
          if (current === generation) storageStatus.textContent =
            "Pairing is valid for this session. Secure storage is unavailable.";
        }
        return;
      }
      if (message.type !== "request") {
        diagnostic("error", "Unexpected WebSocket message type");
        disconnect();
        status.textContent = "Unexpected bridge message. Disconnected.";
        scheduleReconnect();
        return;
      }
      const response = await dispatchRequest(message);
      if (current === generation && ws.readyState === 1) {
        try { ws.send(encodeResponse(response)); }
        catch (error) { diagnostic("error", "WebSocket response send failed", error); }
      }
    };
    ws.onerror = event => {
      if (current !== generation) return;
      diagnostic("error", "WebSocket onerror; readyState=" + socketState(ws), event && (event.error || event), token);
      disconnect();
      status.textContent = "Waiting for ChatGPT/Codex. Retrying automatically.";
      scheduleReconnect();
    };
    ws.onclose = event => {
      closedDiagnostic(event, current === generation);
      if (current !== generation) return;
      disconnect();
      cancelReconnect();
      if (authenticated && event && event.code === 1000 && event.wasClean === true &&
          event.reason === "Replaced by authenticated reconnect") {
        // Another authenticated runtime owns the bridge now. Retrying here makes
        // installed/development or duplicate panels replace each other forever.
        status.textContent = "Bridge is owned by another authenticated connection. Use Connect / Reconnect to take over.";
        return;
      }
      status.textContent = "Waiting for ChatGPT/Codex. Retrying automatically.";
      scheduleReconnect();
    };
  }

  document.getElementById("connect").addEventListener("click", () => connect(false));
  uxp.entrypoints.setup({ plugin: { create() {}, destroy() {
    destroyed = true;
    cancelReconnect();
    disconnect();
  } } });
  diagnostic("log", "Plugin panel initialized; typeof WebSocket=" + typeof WebSocket + "; endpoint=" + ENDPOINT);
  // Runs on plugin load, including startup with the panel hidden. No UI click or ping.
  void connect(true);
}

if (typeof document !== "undefined") initializePanel();
// The same DOM-reading functions are exercised with read-only mocks; never ship a mock host.
if (typeof module !== "undefined") module.exports = { handleRequest, dispatchRequest, encodeResponse, byteLength };
