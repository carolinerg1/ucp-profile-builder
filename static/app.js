/**
 * UCP Well-Known Profile Builder - Application Logic
 * 2-Way Sync between UI Form State and Profile JSON Document.
 */

document.addEventListener("DOMContentLoaded", async () => {
  // App State
  let state = {
    version: "2026-08-25",
    serviceEndpoint: "https://business.example.com/ucp/v1",
    selectedCapabilities: new Set([
      "dev.ucp.shopping.cart",
      "dev.ucp.shopping.checkout",
      "dev.ucp.shopping.fulfillment",
      "dev.ucp.common.identity_linking"
    ]),
    capabilityConfigs: {},
    paymentHandlers: {
      gpay: true,
      shopPay: true,
      stripe: false
    },
    keys: [
      {
        kid: "key_2026_01",
        kty: "EC",
        crv: "P-256",
        x: "WbbXwVYGdJoP4Xm3qCkGvBRcRvKtEfXDbWvPzpPS8LA",
        y: "sP4jHHxYqC89HBo8TjrtVOAGHfJDflYxw7MFMxuFMPY",
        use: "sig",
        alg: "ES256"
      }
    ]
  };

  let versionsData = [];
  let capabilitiesData = {};
  let presetsData = {};
  let isUpdatingFromText = false; // Flag to prevent circular updates

  // DOM Elements
  const ucpVersionSelect = document.getElementById("ucpVersion");
  const selectedVersionLabel = document.getElementById("selectedVersionLabel");
  const serviceEndpointInput = document.getElementById("serviceEndpoint");
  const presetSelect = document.getElementById("presetSelect");
  const capabilitiesContainer = document.getElementById("capabilitiesContainer");
  const capabilityConfigsContainer = document.getElementById("capabilityConfigsContainer");
  const keysContainer = document.getElementById("keysContainer");
  const jsonTextarea = document.getElementById("jsonTextarea");
  const validationBadge = document.getElementById("validationBadge");
  const validationResults = document.getElementById("validationResults");
  const valTitle = document.getElementById("valTitle");
  const valMessageList = document.getElementById("valMessageList");

  // Payment Handlers Checkboxes
  const handlerGpay = document.getElementById("handlerGpay");
  const handlerShopPay = document.getElementById("handlerShopPay");
  const handlerStripe = document.getElementById("handlerStripe");

  // Action Buttons
  const btnCopyJson = document.getElementById("btnCopyJson");
  const btnDownloadJson = document.getElementById("btnDownloadJson");
  const btnAddKey = document.getElementById("btnAddKey");
  const btnSelectAll = document.getElementById("btnSelectAll");
  const btnDeselectAll = document.getElementById("btnDeselectAll");
  const btnSelectShoppingOnly = document.getElementById("btnSelectShoppingOnly");

  // Initialize App
  async function init() {
    try {
      const [vRes, cRes, pRes] = await Promise.all([
        fetch("/api/versions").then(r => r.json()),
        fetch("/api/capabilities").then(r => r.json()),
        fetch("/api/presets").then(r => r.json())
      ]);

      versionsData = vRes;
      capabilitiesData = cRes;
      presetsData = pRes;

      renderVersionOptions();
      renderCapabilitiesGrid();
      setupEventListeners();
      
      // Initial render & sync
      updateFormUIFromState();
      generateJsonFromState();
    } catch (err) {
      console.error("Initialization error:", err);
    }
  }

  // Render Version Select Dropdown
  function renderVersionOptions() {
    ucpVersionSelect.innerHTML = versionsData.map(v => 
      `<option value="${v.version}">${v.label}</option>`
    ).join("");
    ucpVersionSelect.value = state.version;
    selectedVersionLabel.textContent = state.version;
  }

  // Version comparison helper: returns true if selectedVer >= minVer
  function isVersionSupported(minVer, selectedVer) {
    if (!minVer) return true;
    return selectedVer.localeCompare(minVer) >= 0;
  }

  // Render Capabilities Grid (Filtered strictly by selected UCP version)
  function renderCapabilitiesGrid() {
    const shoppingCaps = [];
    const commonCaps = [];

    Object.values(capabilitiesData).forEach(cap => {
      if (isVersionSupported(cap.min_version, state.version)) {
        if (cap.category === "Shopping") {
          shoppingCaps.push(cap);
        } else {
          commonCaps.push(cap);
        }
      }
    });

    let html = "";
    if (shoppingCaps.length > 0) {
      html += `
        <div class="capability-category-header">🛒 Shopping Capabilities</div>
        ${shoppingCaps.map(renderCapabilityCard).join("")}
      `;
    }

    if (commonCaps.length > 0) {
      html += `
        <div class="capability-category-header" style="margin-top: 12px;">🔐 Common & Extension Capabilities</div>
        ${commonCaps.map(renderCapabilityCard).join("")}
      `;
    }

    if (shoppingCaps.length === 0 && commonCaps.length === 0) {
      html = `<div class="input-help" style="padding: 12px; text-align: center;">No capabilities supported in version ${state.version}.</div>`;
    }

    capabilitiesContainer.innerHTML = html;
  }

  function renderCapabilityCard(cap) {
    const isChecked = state.selectedCapabilities.has(cap.name);
    const minVer = cap.min_version || "2026-01-01";
    const localSpecDocUrl = `http://gcarolinetest.c.googlers.com:8050/latest/${cap.spec_path}`;

    return `
      <div class="capability-card ${isChecked ? 'selected' : ''}" data-cap="${cap.name}">
        <input type="checkbox" class="capability-checkbox" data-cap="${cap.name}" ${isChecked ? 'checked' : ''}>
        <div class="capability-info" style="width: 100%;">
          <strong>${cap.title}</strong>
          <code>${cap.name}</code>
          <p>${cap.description}</p>
          <div class="capability-introduced-line" style="margin-top: 6px; font-size: 12px; font-weight: 500; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between;">
            <span>Introduced in UCP version ${minVer}</span>
            <a href="${localSpecDocUrl}" target="_blank" rel="noopener" style="color: var(--accent-cyan); text-decoration: none; font-weight: 600;" onclick="event.stopPropagation();">📖 View Specification Docs ↗</a>
          </div>
        </div>
      </div>
    `;
  }

  // Render Dynamic Config Forms for Selected Capabilities
  function renderCapabilityConfigs() {
    if (state.selectedCapabilities.size === 0) {
      capabilityConfigsContainer.innerHTML = `
        <div class="input-help" style="padding: 12px; text-align: center;">No capabilities selected. Select capabilities above to view and edit details.</div>
      `;
      return;
    }

    const html = Array.from(state.selectedCapabilities).map(capName => {
      const cap = capabilitiesData[capName];
      if (!cap) return "";

      const localSpecUrl = `http://gcarolinetest.c.googlers.com:8050/latest/${cap.spec_path}`;
      const specUrl = `https://ucp.dev/${state.version}/${cap.spec_path}`;
      const schemaUrl = `https://ucp.dev/${state.version}/${cap.schema_path}`;

      return `
        <div class="cap-config-item">
          <div class="cap-config-header">
            <h4>${cap.name}</h4>
            <span class="badge-subtitle">v${state.version}</span>
          </div>
          <div class="form-group">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label>Spec URL</label>
              <a href="${localSpecUrl}" target="_blank" rel="noopener" style="font-size: 11px; color: var(--accent-cyan); text-decoration: none; font-weight: 600;">Open ucp.dev Spec Docs ↗</a>
            </div>
            <input type="text" class="input-control" value="${specUrl}" readonly style="opacity: 0.8; font-family: var(--font-mono); font-size: 12px;">
          </div>
          <div class="form-group">
            <label>Schema URL</label>
            <input type="text" class="input-control" value="${schemaUrl}" readonly style="opacity: 0.8; font-family: var(--font-mono); font-size: 12px;">
          </div>
          ${renderSpecificCapConfigFields(capName)}
        </div>
      `;
    }).join("");

    capabilityConfigsContainer.innerHTML = html;
  }

  function renderSpecificCapConfigFields(capName) {
    if (capName === "dev.ucp.common.identity_linking") {
      return `
        <div class="form-group" style="margin-top: 6px;">
          <label>Config Scopes Map (User Auth Requirements)</label>
          <div class="checkbox-group-inline">
            <label class="checkbox-pill">
              <input type="checkbox" checked disabled>
              <span><code>dev.ucp.shopping.order:read</code></span>
            </label>
            <label class="checkbox-pill">
              <input type="checkbox" checked disabled>
              <span><code>dev.ucp.shopping.order:manage</code></span>
            </label>
          </div>
        </div>
      `;
    } else if (capName === "dev.ucp.shopping.fulfillment") {
      return `
        <div class="form-group" style="margin-top: 6px;">
          <label>Config Fulfillment Methods</label>
          <div class="checkbox-group-inline">
            <label class="checkbox-pill">
              <input type="checkbox" checked disabled>
              <span>shipping</span>
            </label>
            <label class="checkbox-pill">
              <input type="checkbox" checked disabled>
              <span>pickup</span>
            </label>
          </div>
        </div>
      `;
    }
    return "";
  }

  // Render JWK Keys
  function renderKeys() {
    if (state.keys.length === 0) {
      keysContainer.innerHTML = `<div class="input-help" style="padding: 8px;">No JWK signing keys published. Click "+ Add Signing Key" to add one.</div>`;
      return;
    }

    keysContainer.innerHTML = state.keys.map((k, index) => `
      <div class="key-card">
        <div class="form-group">
          <label>Key ID (kid)</label>
          <input type="text" class="input-control key-kid" data-index="${index}" value="${k.kid || ''}" placeholder="key_2026_1">
        </div>
        <div class="form-group">
          <label>Key Type (kty)</label>
          <select class="input-control key-kty" data-index="${index}">
            <option value="EC" ${k.kty === 'EC' ? 'selected' : ''}>EC (ECDSA P-256)</option>
            <option value="OKP" ${k.kty === 'OKP' ? 'selected' : ''}>OKP (Ed25519 WBA)</option>
          </select>
        </div>
        <div class="form-group">
          <label>Algorithm (alg)</label>
          <input type="text" class="input-control key-alg" data-index="${index}" value="${k.alg || 'ES256'}" readonly>
        </div>
        <button class="btn-danger-sm btn-delete-key" data-index="${index}">Remove</button>
      </div>
    `).join("");
  }

  // Setup Event Listeners
  function setupEventListeners() {
    // Version select change
    ucpVersionSelect.addEventListener("change", (e) => {
      state.version = e.target.value;
      selectedVersionLabel.textContent = state.version;

      // Auto-deselect capabilities not supported in selected version
      for (const capName of Array.from(state.selectedCapabilities)) {
        const cap = capabilitiesData[capName];
        if (cap && cap.min_version && !isVersionSupported(cap.min_version, state.version)) {
          state.selectedCapabilities.delete(capName);
        }
      }

      renderCapabilitiesGrid();
      renderCapabilityConfigs();
      generateJsonFromState();
    });

    // Service endpoint change
    serviceEndpointInput.addEventListener("input", (e) => {
      state.serviceEndpoint = e.target.value;
      generateJsonFromState();
    });

    // Preset selector change
    presetSelect.addEventListener("change", (e) => {
      const presetKey = e.target.value;
      if (presetKey && presetsData[presetKey]) {
        applyPreset(presetsData[presetKey].profile);
      }
    });

    // Capability checkboxes toggle (event delegation)
    capabilitiesContainer.addEventListener("click", (e) => {
      const card = e.target.closest(".capability-card");
      if (!card || card.classList.contains("unsupported")) return;

      const capName = card.dataset.cap;
      const checkbox = card.querySelector(".capability-checkbox");
      if (!checkbox || checkbox.disabled) return;

      if (e.target !== checkbox) {
        checkbox.checked = !checkbox.checked;
      }

      if (checkbox.checked) {
        state.selectedCapabilities.add(capName);
        card.classList.add("selected");
      } else {
        state.selectedCapabilities.delete(capName);
        card.classList.remove("selected");
      }

      renderCapabilityConfigs();
      generateJsonFromState();
    });

    // Payment Handlers checkboxes
    handlerGpay.addEventListener("change", (e) => {
      state.paymentHandlers.gpay = e.target.checked;
      generateJsonFromState();
    });
    handlerShopPay.addEventListener("change", (e) => {
      state.paymentHandlers.shopPay = e.target.checked;
      generateJsonFromState();
    });
    handlerStripe.addEventListener("change", (e) => {
      state.paymentHandlers.stripe = e.target.checked;
      generateJsonFromState();
    });

    // Keys management
    btnAddKey.addEventListener("click", () => {
      const newIndex = state.keys.length + 1;
      state.keys.push({
        kid: `key_2026_${newIndex}`,
        kty: "EC",
        crv: "P-256",
        x: "WbbXwVYGdJoP4Xm3qCkGvBRcRvKtEfXDbWvPzpPS8LA",
        y: "sP4jHHxYqC89HBo8TjrtVOAGHfJDflYxw7MFMxuFMPY",
        use: "sig",
        alg: "ES256"
      });
      renderKeys();
      generateJsonFromState();
    });

    keysContainer.addEventListener("input", (e) => {
      const idx = e.target.dataset.index;
      if (idx !== undefined) {
        if (e.target.classList.contains("key-kid")) {
          state.keys[idx].kid = e.target.value;
        } else if (e.target.classList.contains("key-kty")) {
          const kty = e.target.value;
          state.keys[idx].kty = kty;
          if (kty === "EC") {
            state.keys[idx].crv = "P-256";
            state.keys[idx].alg = "ES256";
            state.keys[idx].y = "sP4jHHxYqC89HBo8TjrtVOAGHfJDflYxw7MFMxuFMPY";
          } else {
            state.keys[idx].crv = "Ed25519";
            state.keys[idx].alg = "EdDSA";
            delete state.keys[idx].y;
          }
          renderKeys();
        }
        generateJsonFromState();
      }
    });

    keysContainer.addEventListener("click", (e) => {
      if (e.target.classList.contains("btn-delete-key")) {
        const idx = parseInt(e.target.dataset.index, 10);
        state.keys.splice(idx, 1);
        renderKeys();
        generateJsonFromState();
      }
    });

    // Preset buttons
    btnSelectAll.addEventListener("click", () => {
      state.selectedCapabilities.clear();
      Object.values(capabilitiesData).forEach(c => {
        if (isVersionSupported(c.min_version, state.version)) {
          state.selectedCapabilities.add(c.name);
        }
      });
      renderCapabilitiesGrid();
      renderCapabilityConfigs();
      generateJsonFromState();
    });

    btnDeselectAll.addEventListener("click", () => {
      state.selectedCapabilities.clear();
      renderCapabilitiesGrid();
      renderCapabilityConfigs();
      generateJsonFromState();
    });

    btnSelectShoppingOnly.addEventListener("click", () => {
      state.selectedCapabilities.clear();
      Object.values(capabilitiesData).forEach(c => {
        if (c.category === "Shopping" && isVersionSupported(c.min_version, state.version)) {
          state.selectedCapabilities.add(c.name);
        }
      });
      renderCapabilitiesGrid();
      renderCapabilityConfigs();
      generateJsonFromState();
    });

    // 2-Way Sync: Manual Text Editing in JSON Textarea
    jsonTextarea.addEventListener("input", () => {
      if (isUpdatingFromText) return;
      isUpdatingFromText = true;
      try {
        const parsed = JSON.parse(jsonTextarea.value);
        updateStateFromParsedJson(parsed);
        validateJsonDocument(parsed);
      } catch (err) {
        showValidationStatus(false, [`JSON Syntax Error: ${err.message}`], []);
      } finally {
        isUpdatingFromText = false;
      }
    });

    // Action buttons
    btnCopyJson.addEventListener("click", () => {
      navigator.clipboard.writeText(jsonTextarea.value).then(() => {
        const originalText = btnCopyJson.innerHTML;
        btnCopyJson.innerHTML = `✓ Copied!`;
        setTimeout(() => { btnCopyJson.innerHTML = originalText; }, 2000);
      });
    });

    btnDownloadJson.addEventListener("click", () => {
      const blob = new Blob([jsonTextarea.value], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "ucp.json";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  // Update Capabilities Checkboxes in DOM to match State
  function updateCapabilitiesGridState() {
    const cards = capabilitiesContainer.querySelectorAll(".capability-card");
    cards.forEach(card => {
      const capName = card.dataset.cap;
      const checkbox = card.querySelector(".capability-checkbox");
      const isSelected = state.selectedCapabilities.has(capName);
      checkbox.checked = isSelected;
      if (isSelected) {
        card.classList.add("selected");
      } else {
        card.classList.remove("selected");
      }
    });
  }

  // Update UI Controls from State
  function updateFormUIFromState() {
    ucpVersionSelect.value = state.version;
    selectedVersionLabel.textContent = state.version;
    serviceEndpointInput.value = state.serviceEndpoint;

    handlerGpay.checked = state.paymentHandlers.gpay;
    handlerShopPay.checked = state.paymentHandlers.shopPay;
    handlerStripe.checked = state.paymentHandlers.stripe;

    renderCapabilitiesGrid();
    renderCapabilityConfigs();
    renderKeys();
  }

  // Generate Profile JSON Object from State
  function generateJsonFromState() {
    if (isUpdatingFromText) return;

    const capabilitiesObj = {};
    state.selectedCapabilities.forEach(capName => {
      const capMeta = capabilitiesData[capName];
      if (!capMeta) return;

      // Only include capabilities supported in state.version
      if (!isVersionSupported(capMeta.min_version, state.version)) return;

      const entry = {
        version: state.version,
        spec: `https://ucp.dev/${state.version}/${capMeta.spec_path}`,
        schema: `https://ucp.dev/${state.version}/${capMeta.schema_path}`
      };

      if (capName === "dev.ucp.common.identity_linking") {
        entry.config = {
          scopes: {
            "dev.ucp.shopping.order:read": {},
            "dev.ucp.shopping.order:manage": {}
          }
        };
      } else if (capName === "dev.ucp.shopping.fulfillment") {
        entry.config = {
          fulfillment_methods: ["shipping", "pickup"]
        };
      }

      capabilitiesObj[capName] = [entry];
    });

    const paymentHandlersObj = {};
    const mapOrderHandlers = [];

    if (state.paymentHandlers.gpay) {
      paymentHandlersObj["com.google.pay"] = [{
        id: "gpay",
        version: state.version,
        spec: "https://payments.google.com/gpay/specification",
        schema: "https://payments.google.com/gpay/schema.json"
      }];
      mapOrderHandlers.push("com.google.pay");
    }

    if (state.paymentHandlers.shopPay) {
      paymentHandlersObj["dev.shopify.shop_pay"] = [{
        id: "shop_pay",
        version: state.version,
        spec: "https://shopify.dev/ucp/shop-pay",
        schema: "https://shopify.dev/ucp/shop-pay.json"
      }];
      mapOrderHandlers.push("dev.shopify.shop_pay");
    }

    if (state.paymentHandlers.stripe) {
      paymentHandlersObj["com.stripe"] = [{
        id: "stripe",
        version: state.version,
        spec: "https://stripe.com/docs/ucp",
        schema: "https://stripe.com/schemas/ucp.json"
      }];
      mapOrderHandlers.push("com.stripe");
    }

    const doc = {
      ucp: {
        version: state.version,
        services: {
          "dev.ucp.shopping": [
            {
              version: state.version,
              spec: `https://ucp.dev/${state.version}/specification/overview`,
              transport: "rest",
              schema: `https://ucp.dev/${state.version}/services/shopping/rest.openapi.json`,
              endpoint: state.serviceEndpoint || "https://business.example.com/ucp/v1"
            }
          ]
        },
        capabilities: capabilitiesObj,
        payment_handlers: paymentHandlersObj
      }
    };

    if (mapOrderHandlers.length > 0) {
      doc.ucp.map_order = {
        payment_handlers: mapOrderHandlers
      };
    }

    if (state.keys && state.keys.length > 0) {
      doc.keys = state.keys;
    }

    const jsonString = JSON.stringify(doc, null, 2);
    jsonTextarea.value = jsonString;

    validateJsonDocument(doc);
  }

  // Parse JSON Document and update UI Form State (Profile -> Form 2-way sync)
  function updateStateFromParsedJson(doc) {
    if (!doc || typeof doc !== "object") return;
    const ucp = doc.ucp;
    if (!ucp || typeof ucp !== "object") return;

    if (ucp.version) {
      state.version = ucp.version;
    }

    if (ucp.services && ucp.services["dev.ucp.shopping"] && ucp.services["dev.ucp.shopping"][0]) {
      const s = ucp.services["dev.ucp.shopping"][0];
      if (s.endpoint) state.serviceEndpoint = s.endpoint;
    }

    if (ucp.capabilities && typeof ucp.capabilities === "object") {
      state.selectedCapabilities.clear();
      Object.keys(ucp.capabilities).forEach(capName => {
        const capMeta = capabilitiesData[capName];
        if (!capMeta || isVersionSupported(capMeta.min_version, state.version)) {
          state.selectedCapabilities.add(capName);
        }
      });
    }

    if (ucp.payment_handlers && typeof ucp.payment_handlers === "object") {
      state.paymentHandlers.gpay = !!ucp.payment_handlers["com.google.pay"];
      state.paymentHandlers.shopPay = !!ucp.payment_handlers["dev.shopify.shop_pay"];
      state.paymentHandlers.stripe = !!ucp.payment_handlers["com.stripe"];
    }

    if (Array.isArray(doc.keys)) {
      state.keys = doc.keys;
    }

    updateFormUIFromState();
  }

  // Apply Preset Profile
  function applyPreset(profileDoc) {
    updateStateFromParsedJson(profileDoc);
    jsonTextarea.value = JSON.stringify(profileDoc, null, 2);
    validateJsonDocument(profileDoc);
  }

  // Validate Profile JSON against Server API
  async function validateJsonDocument(doc) {
    try {
      const res = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(doc)
      });
      const data = await res.json();
      showValidationStatus(data.valid, data.errors || [], data.warnings || []);
    } catch (err) {
      console.error("Validation error:", err);
    }
  }

  // Show Validation Banner & Badge
  function showValidationStatus(isValid, errors, warnings) {
    if (isValid) {
      validationBadge.className = "status-badge status-valid";
      validationBadge.querySelector(".status-text").textContent = "Valid Profile";
      
      validationResults.className = "validation-banner val-success";
      valTitle.textContent = "✓ Profile Schema Validation Passed";
      valMessageList.innerHTML = warnings.length > 0 
        ? warnings.map(w => `<li style="color: #fbbf24;">⚠️ ${w}</li>`).join("")
        : `<li>Profile structure conforms to <code>profile.json</code> schema specification.</li>`;
    } else {
      validationBadge.className = "status-badge status-invalid";
      validationBadge.querySelector(".status-text").textContent = "Invalid Profile";

      validationResults.className = "validation-banner val-error";
      valTitle.textContent = "✖ Validation Errors Detected";
      valMessageList.innerHTML = errors.map(e => `<li>${e}</li>`).join("");
    }
  }

  init();
});
