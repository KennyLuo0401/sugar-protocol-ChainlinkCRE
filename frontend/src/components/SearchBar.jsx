import { useState } from 'react';
import { search } from '../api';

export default function SearchBar({ onResults }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      if (onResults) onResults(null);
      return;
    }

    setLoading(true);
    try {
      const result = await search(trimmed);
      if (onResults) onResults(result);
    } catch {
      // silently fail search
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setQuery('');
    if (onResults) onResults(null);
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search entities or claims..."
        disabled={loading}
      />
      {query && (
        <button type="button" className="search-clear" onClick={handleClear}>
          &times;
        </button>
      )}
      <button type="submit" disabled={loading || !query.trim()}>
        {loading ? '...' : 'Search'}
      </button>
    </form>
  );
}
