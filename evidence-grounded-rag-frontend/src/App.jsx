import React, { useEffect, useState } from "react";
import { API_BASE_URL, isApiConfigured, checkHealth, uploadDocument, askBackend, normalizeResult, buildAskPayload, validateUploadFile } from "./api.js";
import { demoResult } from "./demoData.js";

function StatusPill({ status }) {
  const key = String(status || "UNKNOWN").toUpperCase().replaceAll(" ", "_");
  const label = key.replaceAll("_", " ");
  const cls = key === "SUPPORTED" || key === "PASS" || key === "OK" ? "supported"
    : key === "CONTRADICTED" || key === "FAIL" ? "contradicted"
    : key === "NOT_ENOUGH_EVIDENCE" || key === "NOT_CHECKED" ? "uncertain" : "neutral";
  return <span className={`status-pill ${cls}`}><span className="status-dot" />{label}</span>;
}

function App() {
  const [page, setPage] = useState("home");
  const [returnPage, setReturnPage] = useState("ask");
  const [mode, setMode] = useState("manual");
  const [question, setQuestion] = useState("");
  const [evidence, setEvidence] = useState("");
  const [file, setFile] = useState(null);
  const [documentId, setDocumentId] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [backendStatus, setBackendStatus] = useState(isApiConfigured ? "checking" : "demo");
  const [usedDemo, setUsedDemo] = useState(false);

  useEffect(() => {
    if (!isApiConfigured) {
      setBackendStatus("demo");
      return;
    }
    let active = true;
    checkHealth()
      .then(() => active && setBackendStatus("online"))
      .catch(() => active && setBackendStatus("offline"));
    return () => { active = false; };
  }, []);

  function clearForm() {
    setQuestion("");
    setEvidence("");
    setFile(null);
    setDocumentId("");
    setResult(null);
    setError("");
    setUsedDemo(false);
    const input = document.getElementById("document-file");
    if (input) input.value = "";
  }

  function selectMode(nextMode) {
    setMode(nextMode);
    setError("");
    setResult(null);
    setUsedDemo(false);
  }

  async function handleUpload() {
    if (!file) throw new Error("Choose a document to upload first.");
    if (!isApiConfigured) throw new Error("Document upload needs a connected FastAPI backend. Demo mode does not process files.");
    const problem = validateUploadFile(file);
    if (problem) throw new Error(problem);
    setUploading(true);
    try {
      const uploaded = await uploadDocument(file);
      const id = uploaded.document_id ?? uploaded.id;
      if (!id) throw new Error("The upload endpoint did not return a document_id. Confirm the agreed API response format.");
      setDocumentId(String(id));
      return String(id);
    } finally {
      setUploading(false);
    }
  }

  function handleFileChange(event) {
    const chosen = event.target.files?.[0] || null;
    setFile(chosen);
    setDocumentId("");
    // Type/size/emptiness problems are reported immediately, before any request.
    setError(chosen ? (validateUploadFile(chosen) || "") : "");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    setUsedDemo(false);
    if (!question.trim()) {
      setError("Enter a question before running verification.");
      return;
    }
    if (mode === "manual" && !evidence.trim()) {
      setError("Paste the evidence you want the answer checked against.");
      return;
    }
    if (mode === "document" && !file && !documentId) {
      setError("Choose a document before asking a question.");
      return;
    }
    if (mode === "document" && file && !documentId) {
      const problem = validateUploadFile(file);
      if (problem) {
        setError(problem);
        return;
      }
    }
    setBusy(true);
    try {
      if (!isApiConfigured) {
        if (mode === "document" || mode === "web") throw new Error("Document upload and web search require the connected backend. Set VITE_API_BASE_URL and redeploy the frontend.");
        setResult(normalizeResult(demoResult));
        setUsedDemo(true);
        setReturnPage("ask");
        setPage("results");
        return;
      }
      let id = documentId;
      if (mode === "document" && file && !id) {
        // Upload once. (The old code uploaded the same file twice.)
        id = await handleUpload();
      }
      const payload = buildAskPayload({ mode, question, evidence, documentId: id });
      const raw = await askBackend(payload);
      const normalized = normalizeResult(raw);
      setResult(normalized);
      setReturnPage("ask");
      setPage("results");
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setPage("home")} aria-label="Go to dashboard">
          <span className="brand-mark">V</span>
          <span><strong>Verity RAG</strong><small>Evidence lab</small></span>
        </button>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <button className={page === "home" ? "nav-item active" : "nav-item"} onClick={() => setPage("home")}><span className="nav-icon">⌂</span> Overview</button>
          <button className={page === "ask" ? "nav-item active" : "nav-item"} onClick={() => setPage("ask")}><span className="nav-icon">＋</span> Ask a question</button>
          <button className={page === "results" ? "nav-item active" : "nav-item"} disabled={!result} onClick={() => setPage("results")}><span className="nav-icon">☷</span> Verification results</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note"><span className="note-icon">✳</span><div><strong>Evidence first</strong><p>Every claim should be traceable to a source.</p></div></div>
          <div className="sidebar-foot">COLLEGE MINI PROJECT<br /><span>RAG · NLI · FACT CHECKING</span></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> {page === "home" ? "Overview" : page === "ask" ? "Ask a question" : "Verification results"}</div>
          <div className="topbar-right">
            <span className={`connection ${backendStatus}`}><span />{backendStatus === "online" ? "Backend connected" : backendStatus === "checking" ? "Checking backend" : backendStatus === "offline" ? "Backend unavailable" : "Demo mode"}</span>
            <span className="avatar">ER</span>
          </div>
        </header>

        <div className="content">
          {page === "home" && <HomePage onStart={() => setPage("ask")} />}
          {page === "ask" && (
            <section className="page-section">
              <div className="page-heading">
                <div><div className="eyebrow">EVIDENCE WORKSPACE</div><h1>Ask with confidence.</h1><p>Choose where the evidence comes from. The backend will generate, verify, and correct the answer.</p></div>
                <button className="button button-ghost" onClick={clearForm}>↺ Clear</button>
              </div>
              <div className="mode-grid">
                <ModeCard active={mode === "manual"} icon="≡" title="Manual evidence" desc="Paste source text directly." onClick={() => selectMode("manual")} />
                <ModeCard active={mode === "document"} icon="⇧" title="Upload document" desc="Ask about a file you provide." onClick={() => selectMode("document")} />
                <ModeCard active={mode === "web"} icon="⌕" title="Web search" desc="Find current online sources for your question." onClick={() => selectMode("web")} />
              </div>
              <form className="question-form panel" onSubmit={handleSubmit}>
                {mode === "web" && <div className="web-mode-note"><span>⌕</span><div><strong>Search the web for evidence</strong><p>Verity retrieves online snippets, then generates, verifies, and corrects an answer against the retrieved evidence. Check the linked sources in the report.</p></div></div>}
                <div className="form-title"><span className="step-number">01</span><div><h2>Your question</h2><p>Be specific about what you want the evidence to establish.</p></div></div>
                <label htmlFor="question">Question</label>
                <textarea id="question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. What results are reported, and what is not supported?" rows={3} />
                {mode === "manual" && <>
                  <div className="field-row"><label htmlFor="evidence">Evidence text</label><span className="field-hint">Paste excerpts, notes, or source text</span></div>
                  <textarea id="evidence" value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="Paste the evidence that the answer must be grounded in..." rows={7} />
                </>}
                {mode === "document" && <div className="upload-box">
                  <div className="upload-symbol">⇧</div><div><strong>{file ? file.name : "Choose a .txt document"}</strong><p>Plain-text .txt file, up to 2 MB. The document is sent only to the configured backend.</p><label className="button button-ghost file-button" htmlFor="document-file">Browse files</label><input id="document-file" type="file" accept=".txt,text/plain" onChange={handleFileChange} /></div>
                  {documentId && <span className="upload-ready"><span aria-hidden="true">✓</span> Uploaded — ready for questions</span>}
                </div>}
                {error && <div className="error-message" role="alert"><strong>Could not process request</strong><span>{error}</span></div>}
                <div className="form-footer"><span className="privacy-note">⌑ Your input is sent only to the configured backend.</span><button className="button button-primary" type="submit" disabled={busy}>{busy ? <><span className="spinner" /> {uploading ? "Uploading document…" : "Processing…"}</> : <>Run verification <span>→</span></>}</button></div>
              </form>
            </section>
          )}
          {page === "results" && result && <ResultsPage result={result} usedDemo={usedDemo} onAskAgain={() => setPage(returnPage)} backLabel="← Back to question" />}
        </div>
        <footer className="app-footer"><span>Verity RAG <span className="footer-dot">·</span> Evidence-grounded answer verification</span><span>Prototype interface <span className="footer-dot">·</span> Backend: {isApiConfigured ? API_BASE_URL : "not configured"}</span></footer>
      </main>
    </div>
  );
}

function ModeCard({ active, icon, title, desc, onClick, disabled }) {
  return <button type="button" className={`mode-card ${active ? "selected" : ""} ${disabled ? "mode-disabled" : ""}`} onClick={onClick} disabled={disabled}>
    <span className="mode-icon">{icon}</span><span className="mode-copy"><strong>{title}</strong><small>{desc}</small></span><span className="mode-radio">{active ? "✓" : ""}</span>
  </button>;
}

function HomePage({ onStart }) {
  const steps = [
    ["01", "Retrieve evidence", "Find relevant passages from pasted text, uploaded documents, or a web search."],
    ["02", "Generate an answer", "Use the retrieved evidence as context for the response."],
    ["03", "Verify each claim", "Check claims against evidence using NLI and consistency signals."],
    ["04", "Correct the answer", "Revise or remove unsupported claims and show the evidence trail."]
  ];
  return <section className="home-page">
    <div className="hero">
      <div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line" /> TRUSTWORTHY AI RESEARCH</div><h1>Answers should be<br /><span>backed by evidence.</span></h1><p className="hero-description">A transparent RAG workflow that checks claims, highlights uncertainty, and corrects responses when the evidence doesn't support them.</p><div className="hero-actions"><button className="button button-primary" onClick={onStart}>Start asking <span>→</span></button><button className="button button-ghost" onClick={onStart}>Explore the workflow <span>↗</span></button></div><div className="hero-meta"><span><i className="tiny-check">✓</i> Claim-level verification</span><span><i className="tiny-check">✓</i> Evidence-linked corrections</span></div></div>
      <div className="hero-visual" aria-label="Illustration of evidence checking">
        <div className="visual-top"><span className="visual-dot" /><span className="visual-dot" /><span className="visual-dot" /><span className="visual-title">VERIFICATION PIPELINE</span><span className="visual-live">● READY</span></div>
        <div className="pipeline">
          <div className="pipeline-node"><span className="pipeline-icon">⌕</span><div><strong>Evidence retrieved</strong><small>3 relevant passages</small></div><StatusPill status="SUPPORTED" /></div>
          <div className="pipeline-connector" />
          <div className="pipeline-node"><span className="pipeline-icon">▤</span><div><strong>Claims extracted</strong><small>Sentence-level analysis</small></div><span className="count-badge">03</span></div>
          <div className="claim-mini"><span className="claim-mark good">✓</span><div><strong>Claim 01</strong><small>Entailed by evidence</small></div><span className="mini-confidence">97%</span></div>
          <div className="claim-mini"><span className="claim-mark warn">!</span><div><strong>Claim 02</strong><small>Evidence insufficient</small></div><span className="mini-confidence">89%</span></div>
          <div className="pipeline-connector" />
          <div className="pipeline-node corrected"><span className="pipeline-icon">✳</span><div><strong>Corrected response</strong><small>Unsupported detail removed</small></div><span className="done-icon">✓</span></div>
        </div>
        <div className="visual-caption"><span className="caption-line" /> EXPLAINABLE BY DESIGN</div>
      </div>
    </div>
    <div className="section-intro"><div><div className="eyebrow">THE WORKFLOW</div><h2>From question to verified answer.</h2></div><p>Make each step visible, so evaluators can see not just what the system answered, but why.</p></div>
    <div className="steps-grid">{steps.map(([number, title, desc]) => <article className="step-card" key={number}><span className="step-number">{number}</span><h3>{title}</h3><p>{desc}</p></article>)}</div>
    <section className="platform-section">
      <div className="section-intro"><div><div className="eyebrow">ABOUT VERITY RAG</div><h2>More than a fluent answer.</h2></div><p>Verity RAG is an evidence-grounded question-answering prototype built to make AI answers easier to inspect, challenge, and trust responsibly.</p></div>
      <div className="platform-grid">
        <article className="platform-card"><span className="platform-icon">⌕</span><h3>Three evidence paths</h3><p>Use your own text, upload a plain-text document, or search the web for relevant evidence.</p></article>
        <article className="platform-card"><span className="platform-icon">✓</span><h3>Claim-level checks</h3><p>Claims are labelled as supported, contradicted, or not supported by enough evidence.</p></article>
        <article className="platform-card"><span className="platform-icon">↺</span><h3>Evidence-based correction</h3><p>The system can revise unsupported content instead of treating every generated sentence as fact.</p></article>
        <article className="platform-card"><span className="platform-icon">▤</span><h3>Inspectable reports</h3><p>Review the original answer, corrected answer, evidence excerpts, verification signals, and retrieved sources.</p></article>
      </div>
      <p className="platform-disclaimer">Research prototype, not a guarantee of truth. Search snippets can be incomplete, models can make mistakes, and important claims should be checked against the original sources.</p>
    </section>
    <div className="home-bottom"><div><span className="bottom-icon">✳</span><div><strong>Designed for transparency</strong><p>See supported, contradicted, and uncertain claims separately.</p></div></div><button className="button button-primary" onClick={onStart}>Try the workspace <span>→</span></button></div>
  </section>;
}

function ResultsPage({ result, usedDemo, onAskAgain, backLabel = "← Back to question" }) {
  const supported = result.claims.filter((c) => c.status === "SUPPORTED").length;
  const contradicted = result.claims.filter((c) => c.status === "CONTRADICTED").length;
  const uncertain = result.claims.filter((c) => c.status === "NOT_ENOUGH_EVIDENCE").length;
  // The backend says plainly when the evidence cannot answer the question; the UI
  // must explain that too, instead of showing a silent or empty corrected answer.
  const insufficient = result.corrected_status === "NOT_ENOUGH_EVIDENCE" ||
    /not sufficient|no answer was generated/i.test(result.corrected_answer || "") ||
    /NOT[ _]ENOUGH[ _]EVIDENCE/i.test(result.verification_status || "");
  return <section className="page-section results-page">
    <div className="page-heading"><div><div className="eyebrow">VERIFICATION REPORT</div><h1>Answer review.</h1><p>Review the original response, corrected answer, and evidence behind each claim.</p></div><button className="button button-ghost" onClick={onAskAgain}>{backLabel}</button></div>
    {result.demo_mode && <div className="demo-banner"><span>ⓘ</span><div><strong>Controlled correction demonstration{result.demo_scenario?.title ? `: ${result.demo_scenario.title}` : "."}</strong><p>{result.demo_scenario?.description ? `${result.demo_scenario.description} ` : ""}{result.demo_notice || "The initial answer is deliberately seeded as incorrect; the backend then runs verification, correction, and re-verification."}</p>{result.demo_scenario?.expected_behavior && <p><strong>What this scenario demonstrates:</strong> {result.demo_scenario.expected_behavior}</p>}</div></div>}
    {usedDemo && <div className="demo-banner"><span>ⓘ</span><div><strong>Illustrative sample result — not generated by your AI model.</strong><p>This example only demonstrates how the interface presents verification results.</p></div></div>}
    <div className="result-summary panel"><div><div className="summary-label">OVERALL VERIFICATION</div><h2>{String(result.verification_status || "STATUS UNAVAILABLE").replaceAll("_", " ")}</h2><p>{result.message || `${result.claims.length} claims reviewed in this response`}</p></div><div className="summary-stats"><div><strong className="stat-good">{supported.toString().padStart(2, "0")}</strong><span>Supported</span></div><div><strong className="stat-bad">{contradicted.toString().padStart(2, "0")}</strong><span>Contradicted</span></div><div><strong className="stat-warn">{uncertain.toString().padStart(2, "0")}</strong><span>Uncertain</span></div></div></div>
    <div className="answer-grid">
      <article className="answer-card panel"><div className="card-heading"><span className="answer-icon original">↗</span><div><h2>Original answer</h2><p>Before evidence-based correction</p></div></div><div className="answer-body">{result.original_answer || <em>The backend did not return an original answer.</em>}</div></article>
      <article className="answer-card panel corrected-card"><div className="card-heading"><span className="answer-icon corrected-icon">✓</span><div><h2>Corrected answer</h2><p>Grounded in the available evidence</p></div><StatusPill status={result.corrected_status || "UNCHECKED"} /></div><div className="answer-body">{result.corrected_answer || <em>The backend did not return a corrected answer.</em>}</div>{result.corrected_evidence && <div className="corrected-evidence"><strong>Answer taken from this evidence:</strong> {result.corrected_evidence}</div>}</article>
    </div>
    {insufficient && <div className="insufficient-note" role="note"><span aria-hidden="true">ⓘ</span><div><strong>The supplied evidence does not contain enough information to answer this question.</strong><p>Instead of guessing, the system withheld the unsupported answer. Any claims that could not be verified appear below — add evidence that addresses the question, or rephrase it, to get a verified answer.</p></div></div>}
    <div className="claims-heading"><div><div className="eyebrow">CLAIM-BY-CLAIM BREAKDOWN</div><h2>Evidence and verification</h2><p>Each extracted claim is labelled with the available evidence and model signals.</p></div><span className="claim-count">{result.claims.length} claims</span></div>
    <div className="claim-list">{result.claims.length ? result.claims.map((claim, index) => <article className="claim-card panel" key={`${claim.claim}-${index}`}>
      <div className="claim-card-top"><div className="claim-number">{String(index + 1).padStart(2, "0")}</div><div className="claim-main"><div className="claim-label">EXTRACTED CLAIM</div><p className="claim-text">{claim.claim}</p></div><StatusPill status={claim.status} /></div>
      <div className="claim-evidence"><div className="evidence-heading"><span>▤</span> Supporting evidence</div><p>{claim.evidence || "No supporting evidence was returned by the backend."}</p></div>
      <div className="claim-metadata">
        <div><span className="metadata-label">NLI VERIFICATION</span><strong>{claim.nli_label || "Not available"}</strong>{claim.nli_confidence !== null && claim.nli_confidence !== undefined && <small>NLI score: {Math.round(Number(claim.nli_confidence))}%</small>}</div>
        <div><span className="metadata-label">OVERALL CONFIDENCE</span><strong>{claim.confidence === null || claim.confidence === undefined ? (claim.support_basis === "answer_span_in_evidence" ? "Grounded by evidence checks" : "Not available") : `${Math.round(Number(claim.confidence))}%`}</strong>{claim.confidence !== null && claim.confidence !== undefined && <div className="confidence-track"><span style={{ width: `${Math.max(0, Math.min(100, Number(claim.confidence)))}%` }} /></div>}{claim.support_basis && <small>Support basis: {claim.support_basis === "answer_span_in_evidence" ? "answer appears in question-relevant evidence" : "NLI entailment"}</small>}</div>
        <div><span className="metadata-label">NUMBER / ENTITY CHECK</span><strong>{claim.consistency?.status || "Not available"}</strong><small>{claim.consistency?.details || claim.consistency?.message || "No consistency details returned."}</small></div>
      </div>
    </article>) : <div className="empty-state panel">{insufficient
      ? "No claims were extracted, because the answer was withheld: the evidence did not contain enough information to answer the question, so there was nothing to verify."
      : "No individual claims were returned. Confirm that the backend includes a `claims` array."}</div>}</div>
    {result.removed_claims?.length > 0 && <section className="removed-section"><div className="claims-heading"><div><div className="eyebrow">CORRECTION LOG</div><h2>Unsupported or removed claims</h2><p>Details omitted or changed during correction.</p></div></div><div className="removed-list panel">{result.removed_claims.map((claim, i) => <div key={i} className="removed-item"><span>−</span><p>{typeof claim === "string" ? claim : claim.claim || claim.text || JSON.stringify(claim)}</p></div>)}</div></section>}
    {result.sources?.length > 0 && <section className="sources-section"><div className="claims-heading"><div><div className="eyebrow">RETRIEVED REFERENCES</div><h2>Sources used</h2><p>Evidence sources returned by the configured backend.</p></div><span className="claim-count">{result.sources.length} sources</span></div><div className="source-list">{result.sources.map((source, i) => <article className="source-card panel" key={`${source.url || source.title || "source"}-${i}`}><span className="source-number">{String(i + 1).padStart(2, "0")}</span><div><strong>{source.title || source.name || "Untitled source"}</strong>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.url} ↗</a> : <span className="source-kind">Uploaded document</span>}{(source.snippet || source.passage) && <p>{source.snippet || source.passage}</p>}</div><span className="external-icon">↗</span></article>)}</div></section>}
    <div className="result-actions"><span>Always check the cited evidence before relying on an answer.</span><button className="button button-primary" onClick={onAskAgain}>{backLabel.includes("demo") ? "Run another scenario" : "Ask another question"} <span>→</span></button></div>
  </section>;
}

export default App;
