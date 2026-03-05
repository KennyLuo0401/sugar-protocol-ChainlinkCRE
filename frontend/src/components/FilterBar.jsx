const TIERS = ['country', 'domain', 'event', 'organization', 'person', 'asset'];

export default function FilterBar({ activeTiers, onChange }) {
  const allActive = activeTiers.length === TIERS.length;

  const toggleAll = () => {
    onChange(allActive ? [] : [...TIERS]);
  };

  const toggleTier = (tier) => {
    if (activeTiers.includes(tier)) {
      onChange(activeTiers.filter((t) => t !== tier));
    } else {
      onChange([...activeTiers, tier]);
    }
  };

  return (
    <div className="filter-bar">
      <button
        className={`filter-chip ${allActive ? 'active' : ''}`}
        onClick={toggleAll}
      >
        All
      </button>
      {TIERS.map((tier) => (
        <button
          key={tier}
          className={`filter-chip tier-${tier} ${activeTiers.includes(tier) ? 'active' : ''}`}
          onClick={() => toggleTier(tier)}
        >
          {tier}
        </button>
      ))}
    </div>
  );
}
