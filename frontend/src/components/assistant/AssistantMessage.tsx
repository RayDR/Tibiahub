import { AlertTriangle, CheckCircle2, CircleHelp, Info, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { AssistantContentPart, AssistantEntityReference, AssistantResponse } from '../../types/assistant';
import AssistantEntity from './AssistantEntity';
import AssistantRouteSteps from './AssistantRouteSteps';

function RichContent({ parts, entities }: { parts: AssistantContentPart[]; entities: Map<string, AssistantEntityReference> }) {
  return <>{parts.map((part, index) => {
    if (part.kind === 'entity' && part.entity_key) {
      const entity = entities.get(part.entity_key);
      return entity ? <AssistantEntity key={`${part.entity_key}:${index}`} entity={entity} /> : null;
    }
    return <span key={`text:${index}`}>{part.text}</span>;
  })}</>;
}

export default function AssistantMessage({ response, onFollowup }: { response: AssistantResponse; onFollowup: (value: string) => void }) {
  const { t } = useTranslation();
  const entities = new Map(response.entities.map((entity) => [entity.key, entity]));
  const cards = response.entity_cards.flatMap((key) => entities.get(key) ? [entities.get(key)!] : []);
  return <div className="space-y-4" data-testid="assistant-structured-response">
    <div className="flex gap-3">
      <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-primary/15 text-primary"><Sparkles className="size-4" /></span>
      <p className="min-w-0 whitespace-pre-wrap leading-7 text-content-primary"><RichContent parts={response.message} entities={entities} /></p>
    </div>

    {response.sections.map((section, index) => <section key={`${section.kind}:${index}`} className="rounded-r-xl border-l-2 border-primary/40 bg-surface-base/35 px-4 py-3">
      <h3 className="font-semibold text-content-primary">{section.title}</h3>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-content-secondary"><RichContent parts={section.content} entities={entities} /></p>
    </section>)}

    {response.prerequisites.length > 0 ? <section>
      <h3 className="mb-2 text-sm font-semibold text-content-primary">{t('assistant.prerequisites')}</h3>
      <ul className="space-y-2">{response.prerequisites.map((item, index) => {
        const Icon = item.status === 'satisfied' ? CheckCircle2 : item.status === 'unknown' ? CircleHelp : Info;
        return <li key={index} className="flex gap-2 rounded-lg bg-surface-base/50 p-3 text-sm text-content-secondary"><Icon className={`mt-0.5 size-4 shrink-0 ${item.status === 'satisfied' ? 'text-success' : 'text-primary'}`} /><span><RichContent parts={item.content} entities={entities} /></span></li>;
      })}</ul>
    </section> : null}

    {cards.length > 0 ? <div className="grid gap-2.5 sm:grid-cols-2" aria-label={t('assistant.entity.cards')}>{cards.map((entity) => <AssistantEntity key={entity.key} entity={entity} variant="card" />)}</div> : null}
    {response.routes.map((route) => <AssistantRouteSteps key={route.key} route={route} />)}

    {response.warnings.length > 0 ? <div className="space-y-2">{response.warnings.map((warning, index) => <div key={`${warning.code}:${index}`} className="flex gap-2 rounded-lg border border-warning/25 bg-warning/10 p-3 text-sm text-content-secondary"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" /><span>{warning.message}</span></div>)}</div> : null}

    {response.suggested_followups.length > 0 ? <div className="flex flex-wrap gap-2">{response.suggested_followups.map((value) => <button key={value} type="button" onClick={() => onFollowup(value)} className="app-button-secondary app-button-sm text-left">{value}</button>)}</div> : null}
  </div>;
}
