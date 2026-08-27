import { useState, type FormEvent } from "react";

export interface BulkAnalyzeInput {
  jdText: string;
  jdFile: File | null;
  resumeFiles: File[];
}

interface Props {
  onSubmit: (input: BulkAnalyzeInput) => void;
  disabled: boolean;
}

export function BulkUploadForm({ onSubmit, disabled }: Props) {
  const [jdText, setJdText] = useState("");
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [resumeFiles, setResumeFiles] = useState<File[]>([]);

  const hasJd = Boolean(jdText.trim() || jdFile);
  const hasResumes = resumeFiles.length > 0;
  const canSubmit = hasJd && hasResumes;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit || disabled) return;
    onSubmit({ jdText, jdFile, resumeFiles });
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <div className="upload-columns">
        <div className="upload-panel">
          <h2>Job Description</h2>
          <textarea
            placeholder="Paste the job description here…"
            value={jdText}
            onChange={(e) => {
              setJdText(e.target.value);
              if (e.target.value) setJdFile(null);
            }}
            rows={10}
            disabled={disabled || Boolean(jdFile)}
          />
          <label className="file-field">
            <span>…or upload a PDF / DOCX / TXT</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              disabled={disabled}
              onChange={(e) => setJdFile(e.target.files?.[0] ?? null)}
            />
            {jdFile && <span className="file-name">{jdFile.name}</span>}
          </label>
        </div>

        <div className="upload-panel">
          <h2>Resumes ({resumeFiles.length} selected)</h2>
          <p className="bulk-hint">
            Select multiple PDF/DOCX/TXT files at once — one candidate per file, up to 50.
          </p>
          <label className="file-field">
            <span>Choose resume files</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              multiple
              disabled={disabled}
              onChange={(e) => setResumeFiles(Array.from(e.target.files ?? []))}
            />
          </label>
          {resumeFiles.length > 0 && (
            <ul className="bulk-file-list">
              {resumeFiles.map((f) => (
                <li key={f.name}>{f.name}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <button type="submit" className="primary-button" disabled={disabled || !canSubmit}>
        {disabled ? "Ranking…" : `Rank ${resumeFiles.length || ""} Candidate${resumeFiles.length === 1 ? "" : "s"}`}
      </button>
      {!disabled && !canSubmit && (
        <p className="form-hint">
          {!hasJd && !hasResumes && "Add a job description and select resume files to continue."}
          {!hasJd && hasResumes && "Add a job description above to continue."}
          {hasJd && !hasResumes && "Select at least one resume file above to continue."}
        </p>
      )}
    </form>
  );
}
