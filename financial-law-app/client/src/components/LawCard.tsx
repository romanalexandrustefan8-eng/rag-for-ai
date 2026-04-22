import { useState } from 'react';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, CheckCircle2, ChevronDown, Loader2 } from 'lucide-react';
import { useRagSummary } from '@/hooks/useRagSummary';

interface LawCardProps {
  id: string;
  title: string;
  category: string;
  fullText: string; // Full law text for RAG processing
  minCompliance: number;
  maxCompliance: number;
  currentCompliance: number;
  complianceThreshold: number;
  isNew?: boolean;
  datePublished?: string;
  onComplianceChange?: (value: number) => void;
}

export function LawCard({
  id,
  title,
  category,
  fullText,
  minCompliance,
  maxCompliance,
  currentCompliance,
  complianceThreshold,
  isNew = false,
  datePublished,
  onComplianceChange,
}: LawCardProps) {
  const [compliance, setCompliance] = useState(currentCompliance);
  const [expanded, setExpanded] = useState(false);
  
  // Fetch simplified summary from RAG model
  const { summary, loading: summaryLoading } = useRagSummary(fullText, 'romanian');
  
  const isCompliant = compliance >= complianceThreshold;
  
  const handleSliderChange = (value: number[]) => {
    setCompliance(value[0]);
    onComplianceChange?.(value[0]);
  };

  const getCategoryIcon = (cat: string) => {
    switch (cat.toLowerCase()) {
      case 'fiscal':
        return '💰';
      case 'muncă':
        return '👥';
      case 'valori mobiliare':
        return '📊';
      case 'bancar':
        return '🏦';
      case 'aml':
        return '🔍';
      default:
        return '⚖️';
    }
  };

  return (
    <div className="law-card">
      {/* Card Header */}
      <div className="law-card-header">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">{getCategoryIcon(category)}</span>
            <Badge variant="outline" className="law-badge">
              {category}
            </Badge>
            {isNew && (
              <Badge className="bg-amber-500 text-white hover:bg-amber-600">
                NOUA
              </Badge>
            )}
          </div>
          <h3 className="law-card-title line-clamp-2">{title}</h3>
          {datePublished && (
            <p className="text-xs text-muted-foreground mt-1">
              Publicată: {datePublished}
            </p>
          )}
        </div>
        <div className="flex-shrink-0">
          {isCompliant ? (
            <CheckCircle2 className="w-6 h-6 text-green-500" />
          ) : (
            <AlertCircle className="w-6 h-6 text-amber-500" />
          )}
        </div>
      </div>

      {/* Card Content */}
      <div className="law-card-content">
        {/* Simplified Summary from RAG */}
        <div className="bg-secondary/30 rounded-lg p-3 mb-4">
          {summaryLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Se generează rezumatul...</span>
            </div>
          ) : summary ? (
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">Rezumat Simplificat:</p>
              <p className="text-sm text-muted-foreground">{summary.simplified}</p>
              
              {/* Key Points */}
              {summary.keyPoints && summary.keyPoints.length > 0 && (
                <div className="mt-3 pt-3 border-t border-border/50">
                  <p className="text-xs font-semibold text-foreground mb-2">Puncte Cheie:</p>
                  <ul className="space-y-1">
                    {summary.keyPoints.slice(0, 3).map((point, idx) => (
                      <li key={idx} className="text-xs text-muted-foreground flex gap-2">
                        <span className="text-primary">•</span>
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Applicable To */}
              {summary.applicableTo && summary.applicableTo.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-semibold text-foreground mb-1">Se Aplică La:</p>
                  <div className="flex flex-wrap gap-1">
                    {summary.applicableTo.slice(0, 2).map((entity, idx) => (
                      <Badge key={idx} variant="secondary" className="text-xs">
                        {entity}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Deadline */}
              {summary.deadline && (
                <div className="mt-2 p-2 bg-amber-50 dark:bg-amber-950/20 rounded border border-amber-200 dark:border-amber-800">
                  <p className="text-xs font-semibold text-amber-900 dark:text-amber-200">
                    Termen: {summary.deadline}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Consultați textul complet pentru detalii
            </p>
          )}
        </div>

        {/* Compliance Slider */}
        <div className="compliance-slider">
          <div className="compliance-label">
            <span className="text-sm font-medium">Nivel Conformitate</span>
            <span className="compliance-range">{Math.round(compliance)}%</span>
          </div>

          {/* Slider */}
          <div className="relative pt-2 pb-1">
            <Slider
              value={[compliance]}
              onValueChange={handleSliderChange}
              min={minCompliance}
              max={maxCompliance}
              step={1}
              className="w-full"
            />
          </div>

          {/* Compliance Status */}
          <div className="flex items-center justify-between text-xs mt-3">
            <span className="text-muted-foreground">
              Prag: {complianceThreshold}%
            </span>
            <span
              className={`font-semibold ${
                isCompliant
                  ? 'text-green-600 dark:text-green-400'
                  : 'text-amber-600 dark:text-amber-400'
              }`}
            >
              {isCompliant ? '✓ Conform' : '⚠ Revizuire'}
            </span>
          </div>
        </div>

        {/* Compliance Bar Visual */}
        <div className="mt-4 pt-3 border-t border-border/50">
          <div className="h-1.5 w-full bg-gradient-to-r from-green-400 via-yellow-400 to-red-500 rounded-full overflow-hidden">
            <div
              className="h-full bg-white/30 transition-all duration-300"
              style={{ width: `${100 - ((compliance - minCompliance) / (maxCompliance - minCompliance)) * 100}%` }}
            />
          </div>
        </div>

        {/* Expand Button */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-4 w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-primary hover:bg-primary/5 rounded-lg transition-colors"
        >
          <span>{expanded ? 'Ascunde' : 'Citeste'} textul complet</span>
          <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </button>

        {/* Full Text (Expandable) */}
        {expanded && (
          <div className="mt-4 pt-4 border-t border-border/50 max-h-64 overflow-y-auto">
            <div className="text-sm text-muted-foreground whitespace-pre-wrap break-words">
              {fullText}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
