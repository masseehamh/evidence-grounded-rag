import React, { useEffect, useState } from "react";
import { API_BASE_URL, isApiConfigured, checkHealth, uploadDocument, askBackend, normalizeResult, buildAskPayload, validateUploadFile } from "./api.js";
import { demoResult } from "./demoData.js";

function AnimatedText({ text, className = "" }) {
  return <span className={`animated-text ${className}`} aria-label={text}>{Array.from(text).map((letter, index) => <span className="type-letter" key={`${text}-${index}`} style={{ "--letter-index": index }}>{letter === " " ? "\u00a0" : letter}</span>)}</span>;
}

function StatusPill({ status }) {
  const key = String(status || "UNKNOWN").toUpperCase().replaceAll(" ", "_");
  const label = key.replaceAll("_", " ");
  const cls = key === "SUPPORTED" || key === "PASS" || key === "OK" ? "supported"
    : key === "CONTRADICTED" || key === "FAIL" ? "contradicted"
    : key === "NOT_ENOUGH_EVIDENCE" || key === "NOT_CHECKED" ? "uncertain" : "neutral";
  return <span className={`status-pill ${cls}`}><span className="status-dot" />{label}</span>;
}

function looksLikeCasualStatement(text) {
  const value = String(text || "").trim().replace(/\s+/g, " ").toLowerCase();
  if (!value || value.includes("?")) return false;
  if (/^(verify|fact[- ]?check|check|assess|evaluate)\b/.test(value)) return false;
  return /^(hi|hey|hello|heya|yo|sup|good morning|good afternoon|good evening|good night|thanks|thank you|thx|bye|goodbye|lol|lmao|haha|hehe|bruh|bro|dude|nice|cool|awesome|great|okay|ok|alright|wow|omg|oops|yikes|i am|i'm|im|i feel|i think|i guess|i like|i love|i hate|i prefer|i want|i wish|i hope|i need|i miss|i enjoy|i'm feeling|im feeling|that is|that's|thats|this is|this's|it is|it's|its|my name is|call me|meet my|look at|listen|guess what|i'm just|im just|just saying|not gonna lie|ngl)\b/.test(value);
}

function App() {
  const [page, setPage] = useState("home");
  const [returnPage, setReturnPage] = useState("ask");
  const [mode, setMode] = useState("manual");
  const [showAdvanced, setShowAdvanced] = useState(true);
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
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    if (!mobileNavOpen) return undefined;
    function handleNavigationKey(event) {
      if (event.key === "Escape") setMobileNavOpen(false);
    }
    window.addEventListener("keydown", handleNavigationKey);
    return () => window.removeEventListener("keydown", handleNavigationKey);
  }, [mobileNavOpen]);

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
    const casualStatement = looksLikeCasualStatement(question);
    if (!casualStatement && mode === "manual" && !evidence.trim()) {
      setError("Paste the evidence you want the answer checked against.");
      return;
    }
    if (!casualStatement && mode === "document" && !file && !documentId) {
      setError("Choose a document before asking a question.");
      return;
    }
    if (!casualStatement && mode === "document" && file && !documentId) {
      const problem = validateUploadFile(file);
      if (problem) {
        setError(problem);
        return;
      }
    }
    setBusy(true);
    try {
      if (!isApiConfigured) {
        if (mode === "document") throw new Error("Document upload requires the connected backend. Set VITE_API_BASE_URL and redeploy the frontend.");
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

  function navigate(nextPage) {
    if (nextPage === "results" && !result) { setPage("ask"); setError("Ask a question first."); }
    else { setPage(nextPage); setError(""); }
    setMobileNavOpen(false);
  }

  return (
    <div className={`app-shell${mobileNavOpen ? " mobile-nav-open" : ""}`}>
      {mobileNavOpen && <button className="drawer-backdrop" aria-label="Close navigation menu" onClick={() => setMobileNavOpen(false)} />}
      <aside className="sidebar" id="app-sidebar" aria-label="Workspace navigation">
        <button className="brand" onClick={() => navigate("home")} aria-label="Go to dashboard">
          <span className="brand-mark">H</span>
          <span><strong>Hally</strong><small>Evidence lab</small></span>
        </button>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <button className={page === "home" ? "nav-item active" : "nav-item"} onClick={() => navigate("home")}><span className="nav-icon">⌂</span> Overview</button>
          <button className={page === "ask" ? "nav-item active" : "nav-item"} onClick={() => navigate("ask")}><span className="nav-icon">＋</span> Ask a question</button>
          <button className={page === "results" ? "nav-item active" : "nav-item"} onClick={() => navigate("results")} aria-label={result ? "Open verification results" : "Ask a question first to open verification results"}><span className="nav-icon">☷</span> Verification results{!result && <small className="nav-item-hint">Ask a question first</small>}</button>
          <button className={page === "evaluation" ? "nav-item active" : "nav-item"} onClick={() => navigate("evaluation")}><span className="nav-icon">⌁</span> Evaluation tests</button>
          <button className={page === "behind" ? "nav-item active" : "nav-item"} onClick={() => navigate("behind")}><span className="nav-icon">✳</span> Curious? Behind the scenes</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note"><span className="note-icon">◎</span><div><strong>Evidence first</strong><p>Every claim should be traceable to a source.</p></div></div>
          <div className="sidebar-foot">AI REALITY CHECK<br /><span>HALLUCINATION DETECTION &amp; CORRECTION</span></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb"><button className="menu-button" type="button" aria-label={mobileNavOpen ? "Close navigation menu" : "Open navigation menu"} aria-controls="app-sidebar" aria-expanded={mobileNavOpen} onClick={() => setMobileNavOpen(!mobileNavOpen)}><span></span><span></span><span></span></button><button className="breadcrumb-link" onClick={() => navigate("home")}>Workspace</button> <span>/</span> <button className="breadcrumb-link" onClick={() => navigate("home")}>Overview</button>{page !== "home" && <><span>/</span> <span>{page === "ask" ? "Ask a question" : page === "evaluation" ? "Evaluation tests" : page === "behind" ? "Behind the scenes" : "Verification results"}</span></>}</div>
          <nav className="top-nav" aria-label="Main navigation">
            <button className={page === "home" ? "top-nav-link active" : "top-nav-link"} onClick={() => navigate("home")}>Overview</button>
            <button className={page === "ask" ? "top-nav-link active" : "top-nav-link"} onClick={() => navigate("ask")}>Ask a question</button>
            <button className={page === "results" ? "top-nav-link active" : "top-nav-link"} onClick={() => navigate("results")}>Results</button>
            <button className={page === "evaluation" ? "top-nav-link active" : "top-nav-link"} onClick={() => navigate("evaluation")}>Test Hally</button>
            <button className={page === "behind" ? "top-nav-link active" : "top-nav-link"} onClick={() => navigate("behind")}>Behind the scenes</button>
          </nav>
          <div className="topbar-right">
            <span className={`connection ${backendStatus}`}><span />{backendStatus === "online" ? "Backend connected" : backendStatus === "checking" ? "Checking backend" : backendStatus === "offline" ? "Backend unavailable" : "Demo mode"}</span>
            <span className="avatar">ER</span>
          </div>
        </header>

        <div className="content">
          {page === "home" && <HomePage onStart={() => setPage("ask")} onEvaluation={() => setPage("evaluation")} onBehind={() => setPage("behind")} />}
          {page === "behind" && <BehindScenesPage onStart={() => navigate("ask")} onEvaluation={() => navigate("evaluation")} />}
          {page === "evaluation" && <EvaluationPage onRunTest={(test) => { setMode("manual"); setShowAdvanced(true); setQuestion(test.question); setEvidence(test.evidence); setError(""); setResult(null); setUsedDemo(false); setPage("ask"); }} />}
          {page === "ask" && (
            <section className="page-section">
              <div className="page-heading">
                <div><div className="eyebrow">LET’S CHECK SOMETHING</div><h1><AnimatedText text="Ask away." /></h1><p>Got a claim? Let’s see if the evidence backs it up.</p></div>
                
              </div>
              <div className="mode-grid">
                <ModeCard active={mode === "web"} icon="⌕" title="Website search" desc="Find an answer online and check it against the sources we find." onClick={() => selectMode("web")} />
                <ModeCard active={mode === "document"} icon="⇧" title="Upload document" desc="Ask a question about a text file." onClick={() => selectMode("document")} />
              </div>
              <div className="advanced-evidence">
                <button type="button" className="advanced-toggle" aria-expanded={showAdvanced} onClick={() => {
                  if (mode === "manual" && showAdvanced) {
                    selectMode("document");
                    setShowAdvanced(false);
                  } else {
                    setShowAdvanced(!showAdvanced);
                    if (!showAdvanced) selectMode("manual");
                  }
                }}>
                  <span>{showAdvanced ? "−" : "+"}</span> {showAdvanced ? "Hide manual evidence" : "Use specific evidence text"}
                  <small>Got a quote or paragraph? Check it right here</small>
                </button>
                {showAdvanced && <ModeCard active={mode === "manual"} icon="≡" title="Manual evidence" desc="Check a claim against text you paste here." onClick={() => selectMode("manual")} />}
              </div>
              <form className="question-form panel" onSubmit={handleSubmit}>
                <div className="form-title"><span className="step-number">01</span><div><h2>What’s the claim?</h2><p>Drop your question below. We’ll do a quick reality check.</p></div></div>
                <label htmlFor="question">Question</label>
                <textarea id="question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What did the AI say? Let’s check it…" rows={3} /><div className="question-field-actions"><button type="button" className="button button-ghost" onClick={clearForm}>↺ Clear</button></div>
                {mode === "manual" && <>
                  <div className="field-row"><label htmlFor="evidence">Evidence text</label><span className="field-hint">Paste excerpts, notes, or source text</span></div>
                  <textarea id="evidence" value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="Paste the text you want Hally to check…" rows={7} />
                </>}
                {mode === "document" && <div className="upload-box">
                  <div className="upload-symbol">⇧</div><div><strong>{file ? file.name : "Choose a .txt document"}</strong><p>Plain-text .txt file, up to 2 MB. Upload only material you are authorized to share; ask a focused question that the file can answer.</p><label className="button button-ghost file-button" htmlFor="document-file">Browse files</label><input id="document-file" type="file" accept=".txt,text/plain" onChange={handleFileChange} /></div>
                  {documentId && <span className="upload-ready"><span aria-hidden="true">✓</span> Uploaded — ready for questions</span>}
                </div>}
                
                {error && <div className="error-message" role="alert"><strong>Could not process request</strong><span>{error}</span></div>}
                <div className="form-footer"><span className="privacy-note">⌑ Your input is sent only to the configured backend.</span><button className="button button-primary" type="submit" disabled={busy}>{busy ? <><span className="spinner" /> {uploading ? "Uploading document…" : "Processing…"}</> : <>Run verification <span>→</span></>}</button></div>
              </form>
            </section>
          )}
          {page === "results" && result && <ResultsPage result={result} usedDemo={usedDemo} onAskAgain={() => navigate(returnPage)} backLabel="← Back to question" />}{page === "results" && !result && <section className="page-section"><div className="empty-state panel results-empty"><h2>Ask a question first</h2><p>Your verification report will appear here after you run a question.</p><button className="button button-primary" onClick={() => navigate("ask")}>Start a question <span>→</span></button></div></section>}
        </div>
        <footer className="app-footer"><span>Hally <span className="footer-dot">·</span> Evidence-based answer verification</span><span>{isApiConfigured ? `API: ${API_BASE_URL}` : "API not configured"}</span></footer>
      </main>
    </div>
  );
}

function ModeCard({ active, icon, title, desc, onClick, disabled }) {
  return <button type="button" className={`mode-card ${active ? "selected" : ""} ${disabled ? "mode-disabled" : ""}`} onClick={onClick} disabled={disabled}>
    <span className="mode-icon">{icon}</span><span className="mode-copy"><strong>{title}</strong><small>{desc}</small></span><span className="mode-radio">{active ? "✓" : ""}</span>
  </button>;
}

function HomePage({ onStart, onEvaluation, onBehind }) {
  const steps = [
    ["01", "Find the receipts", "Look for the bits that can back up an answer."],
    ["02", "Get an answer", "Put the useful info together into a reply."],
    ["03", "Check the facts", "Check each claim against the info we found, and flag numbers that don’t match."],
    ["04", "Fix what’s off", "Tweak or remove details that the evidence can’t back up."]
  ];
  return <section className="home-page">
    <div className="hero">
      <div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line" /> <AnimatedText text="SAY HI TO HALLY" /></div><h1 className="hero-title"><span className="type-line">{Array.from("Hallucination detection").map((letter, i) => <span className="type-letter" key={`a-${i}`} style={{ "--letter-index": i }}>{letter === " " ? "\u00a0" : letter}</span>)}</span><br /><span className="type-line accent-line">{Array.from("& correction.").map((letter, i) => <span className="type-letter" key={`b-${i}`} style={{ "--letter-index": i + 23 }}>{letter === " " ? "\u00a0" : letter}</span>)}</span></h1><p className="hero-pun">In AI, not humans.</p><p className="hero-description">AI can make things up with a straight face. Hally helps you catch that, check the receipts, and see what actually adds up.</p><div className="hero-actions"><button className="button button-primary" onClick={onStart}>Start asking <span>→</span></button><button className="button button-ghost" onClick={onBehind}>Curious how it works? <span>→</span></button></div><div className="hero-meta"><span><i className="tiny-check">✓</i> Claim-level verification</span><span><i className="tiny-check">✓</i> Evidence-linked corrections</span></div><div className="home-quick-links"><button onClick={onEvaluation}>Run a contradiction test <span>→</span></button><span>Try a tricky claim and see what Hally spots.</span></div></div>
      <div className="hero-visual" aria-label="Animated illustration of Hally checking an AI answer"><div className="hallucination-orbit" aria-hidden="true"><span className="orbit-ring ring-one"></span><span className="orbit-ring ring-two"></span><span className="orbit-spark">?</span><span className="orbit-check">✓</span><span className="orbit-dot"></span></div>
        <div className="visual-top"><span className="visual-dot" /><span className="visual-dot" /><span className="visual-dot" /><span className="visual-title">HOW VERIFICATION WORKS</span><span className="visual-live">WORKFLOW EXAMPLE</span></div>
        <div className="pipeline">
          <div className="pipeline-node"><span className="pipeline-icon">⌕</span><div><strong>Evidence retrieved</strong><small>Relevant passages from the selected source</small></div></div>
          <div className="pipeline-connector" />
          <div className="pipeline-node"><span className="pipeline-icon">▤</span><div><strong>Claims extracted</strong><small>Sentence-level analysis</small></div><span className="count-badge">03</span></div>
          <div className="claim-mini"><span className="claim-mark good">✓</span><div><strong>Claim 01</strong><small>Entailed by evidence</small></div></div>
          <div className="claim-mini"><span className="claim-mark warn">!</span><div><strong>Claim 02</strong><small>Evidence insufficient</small></div></div>
          <div className="pipeline-connector" />
          <div className="pipeline-node corrected"><span className="pipeline-icon">✳</span><div><strong>Corrected response</strong><small>Unsupported detail removed</small></div><span className="done-icon">✓</span></div>
        </div>
        <div className="visual-caption"><span className="caption-line" /> EXPLAINABLE BY DESIGN</div>
      </div>
    </div>
    <div id="workflow-details" className="section-intro"><div><div className="eyebrow">THE WORKFLOW</div><h2>Four small steps. No mystery.</h2></div><p>Find the evidence, draft an answer, check the claims, then tidy up anything the evidence can’t support. Tap a step to explore it.</p></div>
    <div className="steps-grid">{steps.map(([number, title, desc]) => <details className="step-card step-interactive" key={number}><summary><span className="step-number">{number}</span><span className="step-summary-copy"><strong>{title}</strong><small>Tap to see what happens</small></span><span className="step-expand" aria-hidden="true">+</span></summary><p>{desc}</p></details>)}</div>
    <section className="platform-section">
      <div className="section-intro"><div><div className="eyebrow">ABOUT HALLY</div><h2>Sounds right ≠ is right.</h2></div><p>Hally helps you ask, “Wait — where did that come from?” It puts the answer next to the evidence, so you can inspect it, challenge it, and make up your own mind.</p></div>
      <div className="platform-grid">
        <article className="platform-card"><span className="platform-icon">⌕</span><h3>Bring your own receipts</h3><p>Use your own text or upload a plain-text document as evidence.</p></article>
        <article className="platform-card"><span className="platform-icon">✓</span><h3>Check the claims</h3><p>Claims are labelled as supported, contradicted, or not supported by enough evidence.</p></article>
        <article className="platform-card"><span className="platform-icon">↺</span><h3>Fix the shaky bits</h3><p>The system can revise unsupported content instead of treating every generated sentence as fact.</p></article>
        <article className="platform-card"><span className="platform-icon">▤</span><h3>Show me the proof</h3><p>Review the original answer, corrected answer, evidence excerpts, verification signals, and retrieved sources.</p></article>
      </div>
      <p className="platform-disclaimer">Research prototype, not a guarantee of truth. Search snippets can be incomplete, models can make mistakes, and important claims should be checked against the original sources.</p>
    </section>
    <div className="home-bottom"><div><span className="bottom-icon">✳</span><div><strong>Designed for transparency</strong><p>See supported, contradicted, and uncertain claims separately.</p></div></div><div className="home-bottom-actions"><button className="button button-ghost" onClick={onBehind}>Curious about the behind-scenes?</button><button className="button button-ghost" onClick={onEvaluation}>Test verification</button><button className="button button-primary" onClick={onStart}>New verification <span>→</span></button></div></div>
  </section>;
}



function BehindScenesPage({ onStart, onEvaluation }) {
  return <section className="page-section behind-page">
    <div className="page-heading">
      <div><div className="eyebrow">THE CURIOUS CORNER</div><h1><AnimatedText text="Curious about the behind-the-scenes?" /></h1><p>No deep tech dive needed. Here’s the vibe, step by step.</p></div>
    </div>
    <div className="behind-intro panel"><div className="behind-intro-kicker">THE SHORT VERSION</div><h2>Good answers show their work.</h2><p>AI can get a detail wrong even when the rest sounds convincing. I check answers against the evidence, show you what lines up, and flag what needs a closer look.</p><div className="behind-intro-tags"><span>Evidence first</span><span>Claims checked</span><span>Clear reasons</span></div></div>
    <div className="behind-grid">
      <article className="behind-card"><span>01</span><h3>Find the receipts</h3><p>Hally uses the source you choose: a website search, a text document, or evidence you paste in.</p></article>
      <article className="behind-card"><span>02</span><h3>Break it into claims</h3><p>Instead of treating a whole answer as one big fact, it looks at the individual things the answer says.</p></article>
      <article className="behind-card"><span>03</span><h3>Check what adds up</h3><p>Each claim is compared with the available evidence. It might be supported, contradicted, or still unclear.</p></article>
      <article className="behind-card"><span>04</span><h3>Show the why</h3><p>The report helps you see the evidence behind the verdict, so you can judge it for yourself.</p></article>
    </div>
    <div className="behind-note"><strong>One thing to keep in mind</strong><p>Hally is a helper, not an all-knowing fact machine. If the evidence is thin or a claim really matters, check the original source too.</p></div>
    <div className="behind-actions"><button className="button button-primary" onClick={onStart}>Okay, let’s try it <span>→</span></button><button className="button button-ghost" onClick={onEvaluation}>Try a mini test</button></div>
  </section>;
}

function EvaluationPage({ onRunTest }) {
  const tests = [
    { id: "contradiction", label: "Contradicted claim", intent: "Check whether the evidence challenges a stated claim.", question: "Verify this claim: The Eiffel Tower is located in Rome.", evidence: "The Eiffel Tower is located in Paris, France.", expected: "The evidence points to a different location. The verifier should identify the conflict if it recognizes the claim." },
    { id: "supported", label: "Supported claim", intent: "Check a simple fact directly stated in the evidence.", question: "When was the Eiffel Tower completed?", evidence: "The Eiffel Tower was completed in 1889.", expected: "The year is stated directly in the evidence." },
    { id: "insufficient", label: "Insufficient evidence", intent: "Check that the system avoids filling in a missing fact.", question: "Verify this claim: The Eiffel Tower opened to the public in 1900.", evidence: "The Eiffel Tower was completed in 1889.", expected: "The provided passage gives a completion year, not a public opening date." }
  ];
  return <section className="page-section evaluation-page">
    <div className="page-heading"><div><div className="eyebrow">TRY A LITTLE EXPERIMENT</div><h1><AnimatedText text="Let’s test Hally." /></h1><p>Pick a mini challenge and see if Hally catches what’s off. The results are real, not staged.</p></div></div>
    <div className="evaluation-notice"><strong>How to use these tests</strong><p>Select a case to load its question and evidence into the workspace. Then run verification and compare the actual report with the test intent. The model may fail a case; that is useful evaluation data, not a result to hide.</p></div>
    <div className="evaluation-grid">{tests.map((test, index) => <article className="evaluation-card panel" key={test.id}><div className="evaluation-card-top"><span className="step-number">0{index+1}</span><span className="evaluation-kind">CONTROLLED INPUT</span></div><h2>{test.label}</h2><p>{test.intent}</p><div className="evaluation-field"><span>QUESTION</span><p>{test.question}</p></div><div className="evaluation-field"><span>EVIDENCE</span><p>{test.evidence}</p></div><div className="evaluation-expectation"><strong>Test intent</strong><p>{test.expected}</p></div><button className="button button-primary" onClick={() => onRunTest(test)}>Load test in workspace <span>→</span></button></article>)}</div>
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
  if (result.verification_mode === "conversation") {
    return <section className="page-section results-page conversation-page">
      <div className="page-heading"><div><div className="eyebrow">HALLY · CONVERSATION</div><h1>Just chatting.</h1><p>No evidence check needed for this one.</p></div><button className="button button-ghost" onClick={onAskAgain}>{backLabel}</button></div>
      <article className="answer-card panel conversation-answer"><div className="card-heading"><span className="answer-icon corrected-icon">✳</span><div><h2>Hally</h2><p>A natural response to what you said</p></div></div><div className="answer-body">{result.corrected_answer || result.original_answer || "Hey! What's up?"}</div></article>
      <div className="result-actions"><span>Ask a factual question any time to use evidence-grounded verification.</span><button className="button button-primary" onClick={onAskAgain}>Keep chatting <span>→</span></button></div>
    </section>;
  }
  return <section className="page-section results-page">
    <div className="page-heading"><div><div className="eyebrow">YOUR FACT-CHECK REPORT</div><h1>Here’s the tea.</h1><p>Here’s what checked out, what didn’t, and what the evidence actually says.</p></div><button className="button button-ghost" onClick={onAskAgain}>{backLabel}</button></div>
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
      <div className="claim-evidence"><div className="evidence-heading"><span>▤</span> Decisive evidence</div><p>{claim.evidence || "No supporting evidence was returned by the backend."}</p></div>
      <div className="claim-verdict-reason"><strong>Why this verdict</strong><p>{claim.reason || "The verifier did not return an additional explanation for this claim."}</p></div>
      <details className="claim-details"><summary>Technical verification details</summary><div className="claim-metadata">
        <div><span className="metadata-label">VERIFICATION METHOD</span><strong>Instruction-model verifier</strong><small>This deployment does not report a separately trained NLI classifier.</small></div>
        <div><span className="metadata-label">NUMERIC CONSISTENCY CHECK</span><strong>{claim.consistency?.status || "Not available"}</strong><small>{claim.consistency?.details || claim.consistency?.message || "No consistency details returned."}</small></div>
      </div></details>
    </article>) : <div className="empty-state panel">{insufficient
      ? "No claims were extracted, because the answer was withheld: the evidence did not contain enough information to answer the question, so there was nothing to verify."
      : "No individual claims were returned. Confirm that the backend includes a `claims` array."}</div>}</div>
    {result.removed_claims?.length > 0 && <section className="removed-section"><div className="claims-heading"><div><div className="eyebrow">CORRECTION LOG</div><h2>Unsupported or removed claims</h2><p>Details omitted or changed during correction.</p></div></div><div className="removed-list panel">{result.removed_claims.map((claim, i) => <div key={i} className="removed-item"><span>−</span><p>{typeof claim === "string" ? claim : claim.claim || claim.text || JSON.stringify(claim)}</p></div>)}</div></section>}
    {result.sources?.length > 0 && <section className="sources-section"><div className="claims-heading"><div><div className="eyebrow">RETRIEVED REFERENCES</div><h2>Sources used</h2><p>Evidence sources returned by the configured backend.</p></div><span className="claim-count">{result.sources.length} sources</span></div><div className="source-list">{result.sources.map((source, i) => <article className="source-card panel" key={`${source.url || source.title || "source"}-${i}`}><span className="source-number">{String(i + 1).padStart(2, "0")}</span><div><strong>{source.title || source.name || "Untitled source"}</strong>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.url} ↗</a> : <span className="source-kind">Uploaded document</span>}{(source.snippet || source.passage) && <details className="source-details"><summary>Evidence excerpt</summary><p>{source.snippet || source.passage}</p></details>}</div><span className="external-icon">↗</span></article>)}</div></section>}
    <div className="result-actions"><span>Always check the cited evidence before relying on an answer.</span><button className="button button-primary" onClick={onAskAgain}>{backLabel.includes("demo") ? "Run another scenario" : "Ask another question"} <span>→</span></button></div>
  </section>;
}

export default App;
