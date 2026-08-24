export function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <path
        d="M6.4 24.2 16 7.6l9.6 16.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.15"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="16" cy="7.6" r="2.05" fill="#10a37f" />
      <path d="M10.2 26.4h11.6" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" opacity="0.32" />
    </svg>
  );
}
