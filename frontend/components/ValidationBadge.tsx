import type { ValidationStatus } from "@/types";

const STYLES: Record<ValidationStatus, string> = {
  valid: "text-good border-good/40 bg-good/10",
  needs_review: "text-warn border-warn/40 bg-warn/10",
  invalid: "text-crit border-crit/40 bg-crit/10",
};

const LABELS: Record<ValidationStatus, string> = {
  valid: "Validated",
  needs_review: "Needs review",
  invalid: "Invalid",
};

export default function ValidationBadge({ status }: { status: ValidationStatus }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
