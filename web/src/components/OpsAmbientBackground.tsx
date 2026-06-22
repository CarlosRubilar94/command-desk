/**
 * Subtle ambient gradient orbs behind the ops console.
 * Reference: dark glassmorphism dashboards (cyan/violet light leaks on deep navy).
 */
export function OpsAmbientBackground() {
  return (
    <div className="deck-ambient-layer" aria-hidden>
      <div className="deck-ambient-orb deck-ambient-orb--cyan" />
      <div className="deck-ambient-orb deck-ambient-orb--violet" />
      <div className="deck-ambient-orb deck-ambient-orb--emerald" />
    </div>
  );
}
