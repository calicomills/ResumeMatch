export interface MatchResult {
  score: number;
  required_matched: string[];
  required_missing: string[];
  nice_to_have_matched: string[];
  nice_to_have_missing: string[];
  experience_ok: boolean;
  experience_detail: string;
  education_ok: boolean;
  breakdown: Record<string, number>;
}

export interface InterviewQuestion {
  gap_kind: string;
  gap_label: string;
  question: string;
  source: "llm" | "fallback";
}

export interface ExtractedLink {
  url: string;
  domain: string;
  kind: "github" | "linkedin" | "site";
  username?: string | null;
}

export interface NotableRepo {
  name: string;
  url: string;
  stars: number;
  language?: string | null;
  description?: string | null;
}

export interface GithubProfile {
  username: string;
  found: boolean;
  profile_url: string;
  name?: string | null;
  bio?: string | null;
  company?: string | null;
  public_repos: number;
  followers: number;
  account_created_at?: string | null;
  top_languages: string[];
  most_recent_push?: string | null;
  notable_repos: NotableRepo[];
  error?: string | null;
}

export interface WebsiteCheck {
  url: string;
  reachable: boolean;
  status_code?: number | null;
  final_url?: string | null;
  title?: string | null;
  description?: string | null;
  error?: string | null;
}

export interface JDRequirements {
  required_skills: string[];
  nice_to_have_skills: string[];
  min_years_experience: number;
  education: string;
}

export interface ResumeProfile {
  skills: string[];
  years_experience: number;
  education: string;
  highlights: string[];
}

export interface HiddenTextSpan {
  text: string;
  reason: "white_on_white" | "tiny_font" | "off_page";
  page: number;
}

export interface IntegrityCheck {
  checked: boolean;
  hidden_text_found: boolean;
  hidden_text_spans: HiddenTextSpan[];
  suspicious_phrases: string[];
}

export interface AnalyzeResponse {
  candidate_name: string | null;
  integrity: IntegrityCheck;
  match: MatchResult;
  jd_requirements: JDRequirements;
  resume_profile: ResumeProfile;
  interview_questions: InterviewQuestion[];
  links: { github: ExtractedLink[]; linkedin: ExtractedLink[]; sites: ExtractedLink[] };
  background_check: { github_profiles: GithubProfile[]; websites: WebsiteCheck[]; summary: string };
}

export interface BulkCandidateResult {
  filename: string;
  candidate_name: string | null;
  score: number | null;
  required_matched: string[];
  required_missing: string[];
  nice_to_have_matched: string[];
  nice_to_have_missing: string[];
  experience_ok: boolean | null;
  experience_detail: string;
  education_ok: boolean | null;
  years_experience: number | null;
  resume_skills: string[];
  hidden_text_found: boolean;
  suspicious_phrases_found: boolean;
  error: string | null;
}

export interface BulkAnalyzeResponse {
  jd_requirements: JDRequirements;
  candidates: BulkCandidateResult[];
  failed: BulkCandidateResult[];
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export class AnalyzeError extends Error {}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* response wasn't JSON; keep statusText */
    }
    throw new AnalyzeError(detail);
  }
  return resp.json();
}

export async function analyze(input: {
  jdText: string;
  resumeText: string;
  jdFile: File | null;
  resumeFile: File | null;
}): Promise<AnalyzeResponse> {
  const form = new FormData();
  if (input.jdFile) form.append("jd_file", input.jdFile);
  else if (input.jdText.trim()) form.append("jd_text", input.jdText);

  if (input.resumeFile) form.append("resume_file", input.resumeFile);
  else if (input.resumeText.trim()) form.append("resume_text", input.resumeText);

  return postForm<AnalyzeResponse>("/api/analyze", form);
}

export async function bulkAnalyze(input: {
  jdText: string;
  jdFile: File | null;
  resumeFiles: File[];
}): Promise<BulkAnalyzeResponse> {
  const form = new FormData();
  if (input.jdFile) form.append("jd_file", input.jdFile);
  else if (input.jdText.trim()) form.append("jd_text", input.jdText);

  for (const file of input.resumeFiles) form.append("resume_files", file);

  return postForm<BulkAnalyzeResponse>("/api/bulk-analyze", form);
}

export interface HealthResponse {
  app: string;
  ollama_url: string;
  model_name: string;
  ollama_reachable: boolean;
  model_loaded: boolean;
  models_available: string[];
  error: string | null;
}

export async function checkHealth(): Promise<HealthResponse> {
  const resp = await fetch(`${API_BASE}/api/health`);
  return resp.json();
}
