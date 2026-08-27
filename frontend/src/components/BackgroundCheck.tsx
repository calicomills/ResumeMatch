import type { ExtractedLink, GithubProfile, WebsiteCheck } from "../api";

interface Props {
  githubProfiles: GithubProfile[];
  websites: WebsiteCheck[];
  summary: string;
  linkedinLinks: ExtractedLink[];
}

export function BackgroundCheck({ githubProfiles, websites, summary, linkedinLinks }: Props) {
  const hasAny = githubProfiles.length > 0 || websites.length > 0 || linkedinLinks.length > 0;
  if (!hasAny) {
    return <p className="empty-note">No GitHub or personal site links were found in the resume.</p>;
  }

  return (
    <div className="background-check">
      <p className="bg-summary">{summary}</p>
      <div className="bg-cards">
        {githubProfiles.map((g) => (
          <GithubCard key={g.username} profile={g} />
        ))}
        {websites.map((w) => (
          <SiteCard key={w.url} site={w} />
        ))}
        {linkedinLinks.map((l) => (
          <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className="bg-card link-only">
            <strong>LinkedIn</strong>
            <span>{l.url}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

function GithubCard({ profile }: { profile: GithubProfile }) {
  if (!profile.found) {
    return (
      <div className="bg-card bg-card-error">
        <strong>GitHub: {profile.username}</strong>
        <span>{profile.error ?? "Could not verify"}</span>
      </div>
    );
  }
  return (
    <a href={profile.profile_url} target="_blank" rel="noreferrer" className="bg-card">
      <strong>GitHub: {profile.username}</strong>
      {profile.bio && <span className="bg-bio">{profile.bio}</span>}
      <span>
        {profile.public_repos} public repos · {profile.followers} followers
      </span>
      {profile.top_languages.length > 0 && <span>Top languages: {profile.top_languages.join(", ")}</span>}
      {profile.most_recent_push && (
        <span>Last push: {new Date(profile.most_recent_push).toLocaleDateString()}</span>
      )}
    </a>
  );
}

function SiteCard({ site }: { site: WebsiteCheck }) {
  if (!site.reachable) {
    return (
      <div className="bg-card bg-card-error">
        <strong>{site.url}</strong>
        <span>Unreachable: {site.error}</span>
      </div>
    );
  }
  return (
    <a href={site.final_url ?? site.url} target="_blank" rel="noreferrer" className="bg-card">
      <strong>{site.title ?? site.url}</strong>
      {site.description && <span>{site.description}</span>}
    </a>
  );
}
