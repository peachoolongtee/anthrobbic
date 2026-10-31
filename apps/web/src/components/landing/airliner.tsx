/** Top-down airliner silhouette, nose pointing right (0 degrees heading). */
export function Airliner({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden fill="currentColor">
      <g transform="rotate(90 12 12)">
        {/* Fuselage */}
        <path d="M12 1.2c.85 0 1.35 1.3 1.35 2.8v16.6c0 .9-.6 1.8-1.35 1.8s-1.35-.9-1.35-1.8V4c0-1.5.5-2.8 1.35-2.8z" />
        {/* Swept wings */}
        <path d="M12.9 8.6 22.6 13.4v1.5l-9.7-2.3zM11.1 8.6 1.4 13.4v1.5l9.7-2.3z" />
        {/* Engines */}
        <rect x="16.2" y="10.6" width="1.3" height="2.6" rx=".6" />
        <rect x="6.5" y="10.6" width="1.3" height="2.6" rx=".6" />
        {/* Tailplane */}
        <path d="M12.6 18.4 16.8 20.6v1.1l-4.2-.9zM11.4 18.4 7.2 20.6v1.1l4.2-.9z" />
      </g>
    </svg>
  )
}
