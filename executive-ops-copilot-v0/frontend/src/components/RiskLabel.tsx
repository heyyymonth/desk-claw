import type { RiskLevel } from '../types';

const riskClass: Record<RiskLevel, string> = {
  low: 'border-green-200 bg-green-50 text-greenRisk',
  medium: 'border-amber-200 bg-amber-50 text-amberRisk',
  high: 'border-red-200 bg-red-50 text-redRisk',
};

export function RiskLabel({ level }: { level: RiskLevel }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-bold uppercase ${riskClass[level]}`}>
      {level} risk
    </span>
  );
}
