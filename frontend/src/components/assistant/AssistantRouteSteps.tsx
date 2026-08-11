import { ListOrdered, MapPin } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { AssistantRouteReference } from '../../types/assistant';
import AssistantMapReference from './AssistantMapReference';

export default function AssistantRouteSteps({ route }: { route: AssistantRouteReference }) {
  const { t } = useTranslation();
  return <article className="rounded-xl border border-line bg-surface-raised p-4">
    <header className="flex flex-wrap items-start justify-between gap-2">
      <div>
        <h3 className="flex items-center gap-2 font-semibold text-content-primary"><ListOrdered className="size-4 text-primary" />{route.name}</h3>
        {(route.start_location || route.end_location) ? <p className="mt-1 text-xs text-content-muted">{t('assistant.route.endpoints', { start: route.start_location || t('assistant.unknown'), end: route.end_location || t('assistant.unknown') })}</p> : null}
      </div>
      <span className="rounded-full bg-primary/10 px-2 py-1 text-xs text-primary">{t('assistant.route.verification', { state: route.verification_state, confidence: route.confidence })}</span>
    </header>
    {route.steps.length > 0 ? <ol className="mt-4 space-y-2">
      {route.steps.map((step) => <li key={`${route.key}:${step.sequence}`} className="flex gap-3 rounded-lg bg-surface-base/60 p-3 text-sm text-content-secondary">
        <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/15 text-xs font-bold text-primary">{step.sequence}</span>
        <span className="min-w-0">
          <span>{step.instruction || t('assistant.route.unresolvedStep')}</span>
          {step.location_name ? <span className="mt-1 flex items-center gap-1 text-xs text-content-muted"><MapPin className="size-3" />{step.location_name}</span> : null}
        </span>
      </li>)}
    </ol> : <p className="mt-4 rounded-lg border border-dashed border-line p-3 text-sm text-content-muted">{t('assistant.route.noSteps')}</p>}
    {route.maps.length > 0 ? <div className="mt-4 grid gap-3">{route.maps.map((map) => <AssistantMapReference key={map.id} map={map} />)}</div> : null}
  </article>;
}
