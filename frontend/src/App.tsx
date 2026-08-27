import { useState } from "react";
import { AnalyzeError, analyze, bulkAnalyze, type AnalyzeResponse, type BulkAnalyzeResponse } from "./api";
import { UploadForm, type AnalyzeInput } from "./components/UploadForm";
import { BulkUploadForm, type BulkAnalyzeInput } from "./components/BulkUploadForm";
import { BulkResultsTable } from "./components/BulkResultsTable";
import { MatchGauge } from "./components/MatchGauge";
import { SkillsBreakdown } from "./components/SkillsBreakdown";
import { InterviewQuestions } from "./components/InterviewQuestions";
import { BackgroundCheck } from "./components/BackgroundCheck";
import { IntegrityWarning } from "./components/IntegrityWarning";

type Mode = "single" | "bulk";

function App() {
  const [mode, setMode] = useState<Mode>("single");

  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [bulkResult, setBulkResult] = useState<BulkAnalyzeResponse | null>(null);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  // Kept so "view full analysis" can re-run the single pipeline on one candidate without
  // re-uploading anything — the JD and resume Files from the bulk run are still in memory.
  const [bulkJd, setBulkJd] = useState<{ text: string; file: File | null } | null>(null);
  const [bulkResumeFiles, setBulkResumeFiles] = useState<File[]>([]);
  const [viewingFullFrom, setViewingFullFrom] = useState(false);

  async function handleSubmit(input: AnalyzeInput) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await analyze(input);
      setResult(res);
    } catch (err) {
      setError(err instanceof AnalyzeError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleBulkSubmit(input: BulkAnalyzeInput) {
    setBulkLoading(true);
    setBulkError(null);
    setBulkResult(null);
    setBulkJd({ text: input.jdText, file: input.jdFile });
    setBulkResumeFiles(input.resumeFiles);
    try {
      const res = await bulkAnalyze(input);
      setBulkResult(res);
    } catch (err) {
      setBulkError(err instanceof AnalyzeError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBulkLoading(false);
    }
  }

  async function handleViewFull(filename: string) {
    const file = bulkResumeFiles.find((f) => f.name === filename);
    if (!file || !bulkJd) return;

    setViewingFullFrom(true);
    setMode("single");
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await analyze({ jdText: bulkJd.text, resumeText: "", jdFile: bulkJd.file, resumeFile: file });
      setResult(res);
    } catch (err) {
      setError(err instanceof AnalyzeError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function backToBulkResults() {
    setViewingFullFrom(false);
    setMode("bulk");
    setResult(null);
    setError(null);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>ResumeSmash</h1>
        <p>
          {mode === "single"
            ? "Paste a job description and a resume to get a match score, targeted interview questions, and a quick background check of any links in the resume."
            : "Upload one job description and many resumes to get a ranked shortlist by match percentage."}
        </p>
      </header>

      <div className="mode-toggle">
        <button
          className={mode === "single" ? "mode-button mode-active" : "mode-button"}
          onClick={() => setMode("single")}
        >
          Single Match
        </button>
        <button
          className={mode === "bulk" ? "mode-button mode-active" : "mode-button"}
          onClick={() => setMode("bulk")}
        >
          Bulk Ranking
        </button>
      </div>

      {mode === "single" && (
        <>
          {viewingFullFrom && (
            <button className="secondary-button back-button" onClick={backToBulkResults}>
              ← Back to bulk results
            </button>
          )}

          <UploadForm onSubmit={handleSubmit} disabled={loading} />

          {loading && (
            <div className="loading-note">
              <div className="spinner" />
              <p>
                Analyzing… this runs on a self-hosted model and can take a minute or two, especially
                on the first request.
              </p>
            </div>
          )}

          {error && <div className="error-note">⚠ {error}</div>}

          {result && (
            <section className="results">
              {result.candidate_name && <h2 className="candidate-name">{result.candidate_name}</h2>}
              <IntegrityWarning integrity={result.integrity} />
              <div className="results-top">
                <MatchGauge score={result.match.score} />
                <div className="results-summary">
                  <SkillsBreakdown match={result.match} jd={result.jd_requirements} resume={result.resume_profile} />
                </div>
              </div>

              <div className="results-section">
                <h2>Suggested interview questions</h2>
                <InterviewQuestions questions={result.interview_questions} />
              </div>

              <div className="results-section">
                <h2>Background check</h2>
                <BackgroundCheck
                  githubProfiles={result.background_check.github_profiles}
                  websites={result.background_check.websites}
                  summary={result.background_check.summary}
                  linkedinLinks={result.links.linkedin}
                />
              </div>
            </section>
          )}
        </>
      )}

      {mode === "bulk" && (
        <>
          <BulkUploadForm onSubmit={handleBulkSubmit} disabled={bulkLoading} />

          {bulkLoading && (
            <div className="loading-note">
              <div className="spinner" />
              <p>
                Ranking candidates… each resume runs its own model call, so a large batch can take a
                while on a self-hosted model.
              </p>
            </div>
          )}

          {bulkError && <div className="error-note">⚠ {bulkError}</div>}

          {bulkResult && <BulkResultsTable result={bulkResult} onViewFull={handleViewFull} />}
        </>
      )}

      <footer className="app-footer">
        <span>Runs entirely on a self-hosted model — resumes and JDs are never sent to a third party.</span>
      </footer>
    </div>
  );
}

export default App;
