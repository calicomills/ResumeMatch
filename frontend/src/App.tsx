import { useState } from "react";
import { AnalyzeError, analyze, type AnalyzeResponse } from "./api";
import { UploadForm, type AnalyzeInput } from "./components/UploadForm";
import { MatchGauge } from "./components/MatchGauge";
import { SkillsBreakdown } from "./components/SkillsBreakdown";
import { InterviewQuestions } from "./components/InterviewQuestions";
import { BackgroundCheck } from "./components/BackgroundCheck";

function App() {
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="app">
      <header className="app-header">
        <h1>ResumeMatch</h1>
        <p>
          Paste a job description and a resume to get a match score, targeted interview questions,
          and a quick background check of any links in the resume.
        </p>
      </header>

      <UploadForm onSubmit={handleSubmit} disabled={loading} />

      {loading && (
        <div className="loading-note">
          <div className="spinner" />
          <p>
            Analyzing… this runs on a self-hosted model and can take a minute or two, especially on
            the first request.
          </p>
        </div>
      )}

      {error && <div className="error-note">⚠ {error}</div>}

      {result && (
        <section className="results">
          {result.candidate_name && <h2 className="candidate-name">{result.candidate_name}</h2>}
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

      <footer className="app-footer">
        <span>Runs entirely on a self-hosted model — resumes and JDs are never sent to a third party.</span>
      </footer>
    </div>
  );
}

export default App;
