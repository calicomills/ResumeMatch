import type { InterviewQuestion } from "../api";

export function InterviewQuestions({ questions }: { questions: InterviewQuestion[] }) {
  if (questions.length === 0) {
    return (
      <p className="empty-note">
        No gaps found — this candidate matches every requirement extracted from the JD.
      </p>
    );
  }
  return (
    <ol className="question-list">
      {questions.map((q, i) => (
        <li key={i}>
          <p className="question-text">{q.question}</p>
          <span className="question-meta">targets: {q.gap_label}</span>
        </li>
      ))}
    </ol>
  );
}
