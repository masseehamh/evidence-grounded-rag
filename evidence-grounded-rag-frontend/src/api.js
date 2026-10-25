// `import.meta.env` only exists under Vite; plain Node (npm test) has no such object.
// The process.env fallback lets the Node tests point at a test server; browsers ignore it.
const configuredBaseUrl =
  import.meta.env?.VITE_API_BASE_URL || globalThis.process?.env?.VITE_API_BASE_URL || "";
export const API_BASE_URL = configuredBaseUrl.trim().replace(/\/+$/, "");
export const isApiConfigured = Boolean(API_BASE_URL);

export function apiUrl(path) {
  if (!API_BASE_URL) throw new Error("Backend URL is not configured. Set VITE_API_BASE_URL in .env.");
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

// ngrok free tunnels serve an HTML interstitial to browser requests unless this header is
// sent. Harmless on any other backend, so it rides along on every request.
const NGROK_SKIP_HEADER = "ngrok-skip-browser-warning";

function looksLikeHtml(text) {
  return /<\s*(!doctype|html|head|body)\b/i.test(text || "");
}

// Only https backends are tunnels in this project; the local fallback is plain http.
function offlineHint() {
  if (!API_BASE_URL.startsWith("https://")) return "";
  return ` The URL ${API_BASE_URL} looks like a Colab/ngrok tunnel: if the Colab runtime stopped, ` +
    "restart it, re-run the FastAPI + ngrok cell, and copy the new URL into .env as VITE_API_BASE_URL.";
}

async function readBody(response) {
  try {
    return await response.text();
  } catch {
    return "";
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(apiUrl(path), {
      ...options,
      headers: { [NGROK_SKIP_HEADER]: "1", ...(options.headers || {}) }
    });
  } catch {
    throw new Error("Could not reach the backend. Check that FastAPI is running and VITE_API_BASE_URL is correct." + offlineHint());
  }
  if (!response.ok) {
    const detail = await readBody(response);
    let message = detail;
    try {
      const parsed = JSON.parse(detail);
      message = parsed.detail || parsed.message || detail;
    } catch { /* Keep plain-text backend errors readable. */ }
    if (!message || looksLikeHtml(message)) {
      // An expired ngrok tunnel answers with an HTML error page instead of JSON.
      throw new Error(`The backend returned HTTP ${response.status} without a readable API error.` + offlineHint());
    }
    throw new Error(message);
  }
  try {
    return await response.json();
  } catch {
    const detail = await readBody(response);
    if (looksLikeHtml(detail)) {
      throw new Error("The backend returned a web page instead of JSON." + offlineHint());
    }
    throw new Error("The backend returned a response that is not valid JSON.");
  }
}

export async function checkHealth() {
  return request("/api/health");
}

export async function uploadDocument(file) {
  const body = new FormData();
  body.append("file", file);
  return request("/api/upload", { method: "POST", body });
}

export async function askBackend(payload) {
  return request("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

// Builds the JSON body for POST /api/ask. Kept here (not inside the component) so it can be tested.
export function buildAskPayload({ mode, question, evidence = "", documentId = "" }) {
  const payload = { question: String(question ?? "").trim(), mode };
  if (mode === "manual") payload.evidence = String(evidence ?? "").trim();
  if (mode === "document") payload.document_id = documentId;
  return payload;
}

export function normalizeResult(raw) {
  if (!raw || typeof raw !== "object") throw new Error("The backend response was empty or invalid.");
  const claims = Array.isArray(raw.claims) ? raw.claims.map((item) => ({
    claim: String(item.claim ?? item.text ?? "Claim text unavailable"),
    status: normalizeStatus(item.status ?? item.label),
    evidence: item.evidence ?? item.supporting_evidence ?? "",
    nli_label: item.nli_label ?? item.nli_verification_label ?? null,
    confidence: normalizeConfidence(item.confidence),
    nli_confidence: normalizeConfidence(item.nli_confidence ?? item.confidence),
    support_basis: item.support_basis ?? item.consistency?.support_basis ?? null,
    consistency: item.consistency ?? item.numeric_entity_consistency ?? null
  })) : [];
  return {
    verification_status: raw.verification_status ?? raw.overall_status ?? "STATUS_UNAVAILABLE",
    message: raw.message ?? "",
    original_answer: raw.original_answer ?? raw.generated_answer ?? "",
    corrected_answer: raw.corrected_answer ?? raw.final_answer ?? "",
    claims,
    removed_claims: Array.isArray(raw.removed_claims) ? raw.removed_claims :
      Array.isArray(raw.unsupported_claims) ? raw.unsupported_claims : [],
    sources: Array.isArray(raw.sources) ? raw.sources : []
  };
}

function normalizeStatus(status) {
  const value = String(status ?? "NOT_ENOUGH_EVIDENCE").toUpperCase().replaceAll(" ", "_");
  if (["SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_EVIDENCE"].includes(value)) return value;
  if (["ENTAILMENT", "SUPPORTS"].includes(value)) return "SUPPORTED";
  if (["CONTRADICTION", "CONTRADICTS"].includes(value)) return "CONTRADICTED";
  return "NOT_ENOUGH_EVIDENCE";
}

function normalizeConfidence(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.max(0, Math.min(100, number <= 1 ? number * 100 : number));
}
