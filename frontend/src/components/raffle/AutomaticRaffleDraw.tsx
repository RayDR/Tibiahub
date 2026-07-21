import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { AutomaticResult } from '../../services/raffle';

type Phase = 'preparing' | 'secondRolling' | 'secondReveal' | 'pause' | 'firstRolling' | 'complete';

export default function AutomaticRaffleDraw({ results, participantNames, testMode = false, published = false }: {
  results: AutomaticResult[]; participantNames: string[]; testMode?: boolean; published?: boolean;
}) {
  const { t } = useTranslation();
  const [phase, setPhase] = useState<Phase>('preparing');
  const [replay, setReplay] = useState(0);
  const [rollingIndex, setRollingIndex] = useState(0);
  const reducedMotion = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, []);
  const second = results.find((result) => result.prize_position === 'second');
  const first = results.find((result) => result.prize_position === 'first');

  useEffect(() => {
    setPhase('preparing');
    const delays = reducedMotion ? [250, 700, 1100, 1550, 2000] : [600, 2600, 3900, 5900, 7200];
    const phases: Phase[] = ['secondRolling', 'secondReveal', 'pause', 'firstRolling', 'complete'];
    const timers = phases.map((next, index) => window.setTimeout(() => setPhase(next), delays[index]));
    return () => timers.forEach(window.clearTimeout);
  }, [results, reducedMotion, replay]);

  useEffect(() => {
    if (reducedMotion || !phase.endsWith('Rolling') || participantNames.length === 0) return;
    const timer = window.setInterval(() => setRollingIndex((value) => (value + 1) % participantNames.length), 120);
    return () => window.clearInterval(timer);
  }, [phase, participantNames, reducedMotion]);

  const rollingName = participantNames[rollingIndex] || t('raffle.operations.draw.preparing');
  const showSecond = ['secondReveal', 'pause', 'firstRolling', 'complete'].includes(phase);
  const showFirst = phase === 'complete';

  return (
    <section aria-live="polite" aria-atomic="true" className="rounded-2xl border border-amber-500/30 bg-slate-950/80 p-5">
      {testMode && <div className="mb-3 inline-flex rounded-full bg-violet-500/20 px-3 py-1 text-xs font-bold text-violet-200">{t('raffle.operations.testLabel')}</div>}
      <h3 className="text-lg font-semibold text-slate-100">{t(`raffle.operations.draw.${phase === 'complete' && published ? 'publicComplete' : phase}`)}</h3>
      {(phase === 'secondRolling' || phase === 'firstRolling') && !reducedMotion && <p className="mt-4 text-2xl text-amber-300">{rollingName}</p>}
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className={`rounded-xl border p-4 ${showSecond ? 'border-amber-500/50' : 'border-slate-800 opacity-50'}`}>
          <span className="text-xs text-slate-400">{t('raffle.operations.secondPlace')}</span>
          <strong className="mt-1 block text-xl text-slate-100">{showSecond ? second?.character_name : '—'}</strong>
          <span className="text-amber-300">100 TC</span>
        </div>
        <div className={`rounded-xl border p-4 ${showFirst ? 'border-amber-500/50' : 'border-slate-800 opacity-50'}`}>
          <span className="text-xs text-slate-400">{t('raffle.operations.firstPlace')}</span>
          <strong className="mt-1 block text-xl text-slate-100">{showFirst ? first?.character_name : '—'}</strong>
          <span className="text-amber-300">250 TC</span>
        </div>
      </div>
      {phase === 'complete' && <button type="button" onClick={() => setReplay(value => value + 1)} className="mt-4 min-h-11 rounded-lg border border-slate-700 px-4 text-sm">{t('raffle.operations.draw.replay')}</button>}
    </section>
  );
}
