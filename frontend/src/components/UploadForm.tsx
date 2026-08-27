import { useState, type FormEvent } from "react";

export interface AnalyzeInput {
  jdText: string;
  resumeText: string;
  jdFile: File | null;
  resumeFile: File | null;
}

interface Props {
  onSubmit: (input: AnalyzeInput) => void;
  disabled: boolean;
}

export function UploadForm({ onSubmit, disabled }: Props) {
  const [jdText, setJdText] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);

  const canSubmit = Boolean((jdText.trim() || jdFile) && (resumeText.trim() || resumeFile));

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit || disabled) return;
    onSubmit({ jdText, resumeText, jdFile, resumeFile });
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
            rows={12}
            disabled={disabled || Boolean(jdFile)}
          />
          <FileField label="…or upload a PDF / DOCX / TXT" file={jdFile} onChange={setJdFile} disabled={disabled} />
        </div>

        <div className="upload-panel">
          <h2>Resume</h2>
          <textarea
            placeholder="Paste the resume text here…"
            value={resumeText}
            onChange={(e) => {
              setResumeText(e.target.value);
              if (e.target.value) setResumeFile(null);
            }}
            rows={12}
            disabled={disabled || Boolean(resumeFile)}
          />
          <FileField
            label="…or upload a PDF / DOCX / TXT"
            file={resumeFile}
            onChange={setResumeFile}
            disabled={disabled}
          />
        </div>
      </div>

      <button type="submit" className="primary-button" disabled={disabled || !canSubmit}>
        {disabled ? "Analyzing…" : "Analyze Match"}
      </button>
    </form>
  );
}

function FileField({
  label,
  file,
  onChange,
  disabled,
}: {
  label: string;
  file: File | null;
  onChange: (f: File | null) => void;
  disabled: boolean;
}) {
  return (
    <label className="file-field">
      <span>{label}</span>
      <input
        type="file"
        accept=".pdf,.docx,.txt,.md"
        disabled={disabled}
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
      {file && <span className="file-name">{file.name}</span>}
    </label>
  );
}
