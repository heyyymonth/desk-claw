import { Server } from 'lucide-react';
import type { HealthStatus } from '../types';

export function StatusIndicator({
  health,
  isLoading,
  error,
}: {
  health?: HealthStatus;
  isLoading: boolean;
  error: unknown;
}) {
  const modelState = health?.model_status ?? health?.ollama ?? 'unknown';
  const modelLabel = health?.model ? `${String(modelState)} (${health.model})` : String(modelState);
  const isHealthy = !error && !isLoading;

  return (
    <div className="flex items-center gap-2 rounded-md border border-[#c6d7ee] bg-white px-3 py-2 text-sm shadow-sm">
      <Server className="text-brand" size={16} aria-hidden="true" />
      <span className={isHealthy ? 'font-semibold text-greenRisk' : 'font-semibold text-amberRisk'}>
        Backend {isLoading ? 'checking' : error ? 'unavailable' : 'online'}
      </span>
      <span className="text-steel">Ollama: {modelLabel}</span>
    </div>
  );
}
