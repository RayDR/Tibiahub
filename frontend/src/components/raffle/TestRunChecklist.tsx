import { CheckCircle2, Circle } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export type TestChecklistKey = 'schedulerHealthy' | 'snapshotFrozen' | 'participantsEligible' | 'drawOnce' | 'secondReveal' | 'firstReveal' | 'reruns' | 'delivery' | 'publication' | 'notifications' | 'cleanup';

export default function TestRunChecklist({ values, manualKeys, onToggle }: {
  values: Record<TestChecklistKey, boolean>;
  manualKeys: TestChecklistKey[];
  onToggle: (key: TestChecklistKey) => void;
}) {
  const { t } = useTranslation();
  const keys = Object.keys(values) as TestChecklistKey[];
  return <section className="rounded-2xl border border-violet-500/30 bg-violet-950/10 p-5">
    <h3 className="mb-3 font-semibold text-violet-100">{t('raffle.testRun.checklist.title')}</h3>
    <div className="grid gap-2 sm:grid-cols-2">
      {keys.map((key) => {
        const manual = manualKeys.includes(key);
        const content = <>{values[key] ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <Circle className="h-4 w-4 text-slate-500" />}<span>{t(`raffle.testRun.checklist.${key}`)}</span></>;
        return manual ? <button type="button" key={key} onClick={() => onToggle(key)} aria-pressed={values[key]} className="flex items-center gap-2 rounded-lg border border-slate-800 p-2 text-left text-sm">{content}</button> : <div key={key} className="flex items-center gap-2 rounded-lg border border-slate-800 p-2 text-sm">{content}</div>;
      })}
    </div>
  </section>;
}
