/* Client-side AES-GCM for private farms. Same process as WakaGym.
   The recovery key never goes to the server. Ciphertext on the server is opaque to admin. */
(function (global) {
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  function b64u(bytes) {
    let s = "";
    const b = bytes instanceof ArrayBuffer ? new Uint8Array(bytes) : bytes;
    for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function unb64u(text) {
    const s = String(text || "").replace(/-/g, "+").replace(/_/g, "/");
    const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
    const bin = atob(s + pad);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function generateRecoveryKey() {
    return b64u(crypto.getRandomValues(new Uint8Array(32)));
  }

  async function importKey(recovery) {
    const raw = unb64u(recovery);
    if (raw.length !== 32) throw new Error("bad recovery key");
    return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
  }

  async function encryptJson(obj, key) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(JSON.stringify(obj)));
    return { iv: b64u(iv), ct: b64u(ct) };
  }

  async function decryptJson(iv, ct, key) {
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64u(iv) }, key, unb64u(ct));
    return JSON.parse(dec.decode(pt));
  }

  function isSealed(state) {
    return !!(state && state.private && state.v && state.iv && state.ct);
  }

  function publicListingView(lot) {
    return {
      produce_name: lot && lot.produce_name,
      category: lot && lot.category,
      unit: lot && lot.unit,
      price_per_kg: lot && lot.price_per_kg,
      quantity_kg: lot && lot.quantity_kg,
    };
  }

  async function sealListing(lot, key) {
    const { iv, ct } = await encryptJson({
      produce_name: lot.produce_name,
      category: lot.category,
      quantity_kg: lot.quantity_kg,
      price_per_kg: lot.price_per_kg,
      unit: lot.unit,
      pickup_point: lot.pickup_point,
      note: lot.note || "",
    }, key);
    return { private: true, v: 1, iv, ct, public: publicListingView(lot) };
  }

  async function openListing(envelope, key) {
    return decryptJson(envelope.iv, envelope.ct, key);
  }

  const LS = (uid) => "sk_privacy_key_" + String(uid || "");

  function saveRecoveryLocal(uid, recovery) {
    try { localStorage.setItem(LS(uid), recovery); } catch {}
  }
  function loadRecoveryLocal(uid) {
    try { return localStorage.getItem(LS(uid)); } catch { return null; }
  }
  function clearRecoveryLocal(uid) {
    try { localStorage.removeItem(LS(uid)); } catch {}
  }

  global.generateRecoveryKey = generateRecoveryKey;
  global.importKey = importKey;
  global.encryptJson = encryptJson;
  global.decryptJson = decryptJson;
  global.isSealed = isSealed;
  global.sealListing = sealListing;
  global.openListing = openListing;
  global.saveRecoveryLocal = saveRecoveryLocal;
  global.loadRecoveryLocal = loadRecoveryLocal;
  global.clearRecoveryLocal = clearRecoveryLocal;
})(window);
