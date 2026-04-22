import { useState, useEffect } from 'react';
import { ragService, LawSummary } from '@/lib/ragService';

interface UseRagSummaryReturn {
  summary: LawSummary | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Hook for fetching law summaries from RAG model
 * 
 * Usage:
 * const { summary, loading, error } = useRagSummary(lawText, 'romanian');
 */
export function useRagSummary(
  lawText: string,
  language: 'romanian' | 'english' = 'romanian'
): UseRagSummaryReturn {
  const [summary, setSummary] = useState<LawSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    if (!lawText) {
      setSummary(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await ragService.summarizeLaw(lawText, language);
      setSummary(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch summary');
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [lawText, language]);

  return {
    summary,
    loading,
    error,
    refetch: fetchSummary,
  };
}
