import { Loader2, RotateCcw, Send, UserRound } from 'lucide-react';
import { FormEvent, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { assistantApi } from '../../services/assistant';
import type { AssistantConversationContext, AssistantHistoryMessage, AssistantResponse } from '../../types/assistant';
import AssistantMessage from './AssistantMessage';

type ChatEntry = { role: 'user'; content: string } | { role: 'assistant'; response: AssistantResponse };
interface StoredChat { entries: ChatEntry[]; context: AssistantConversationContext; }

const STORAGE_KEY = 'tibiahub:assistant:v1';

function conversationId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `assistant-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function initialContext(language: string): AssistantConversationContext {
  return {
    conversation_id: conversationId(), language: language.startsWith('es') ? 'es' : 'en',
    known_access_unlocks: [], completed_quests: [], owned_items: [], current_location: null,
    character: { vocation: null, level: null }, party_members: [],
  };
}

function responseText(response: AssistantResponse): string {
  const entities = new Map(response.entities.map((entity) => [entity.key, entity.canonical_name]));
  return response.message.map((part) => part.kind === 'entity' && part.entity_key ? entities.get(part.entity_key) || '' : part.text || '').join('');
}

function loadStored(language: string): StoredChat {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '') as StoredChat;
    if (Array.isArray(value.entries) && value.context?.conversation_id) return value;
  } catch {
    // Start a clean conversation when session storage is unavailable or stale.
  }
  return { entries: [], context: initialContext(language) };
}

function errorCode(error: unknown): string {
  const value = error as { response?: { data?: { detail?: { code?: string } } } };
  return value.response?.data?.detail?.code || 'unavailable';
}

export default function AssistantChat() {
  const { t, i18n } = useTranslation();
  const [initial] = useState(() => loadStored(i18n.language));
  const [entries, setEntries] = useState<ChatEntry[]>(initial.entries);
  const [context, setContext] = useState<AssistantConversationContext>(initial.context);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ entries: entries.slice(-20), context })); } catch { /* restricted storage */ }
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [context, entries, loading]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const history = (): AssistantHistoryMessage[] => entries.slice(-12).map((entry) => entry.role === 'user'
    ? { role: 'user', content: entry.content }
    : { role: 'assistant', content: responseText(entry.response) });

  const send = async (value: string) => {
    const content = value.trim();
    if (!content || loading) return;
    const priorHistory = history();
    setEntries((current) => [...current, { role: 'user', content }]);
    setMessage(''); setError(null); setLoading(true);
    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      const response = await assistantApi.ask({ message: content, history: priorHistory, context }, controller.signal);
      setEntries((current) => [...current, { role: 'assistant', response }]);
      setContext(response.context);
    } catch (caught) {
      if (!controller.signal.aborted) setError(errorCode(caught));
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
      setLoading(false);
    }
  };

  const submit = (event: FormEvent) => { event.preventDefault(); void send(message); };
  const reset = () => {
    controllerRef.current?.abort();
    setEntries([]); setContext(initialContext(i18n.language)); setMessage(''); setError(null); setLoading(false);
    try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* restricted storage */ }
  };
  const starters = [t('assistant.starters.hunt'), t('assistant.starters.item'), t('assistant.starters.access')];

  return <div className="overflow-hidden rounded-2xl border border-line bg-surface-overlay shadow-sm">
    <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
      <p className="text-xs text-content-muted">{t('assistant.localOnly')}</p>
      {entries.length > 0 ? <button type="button" onClick={reset} className="app-button-ghost app-button-sm shrink-0"><RotateCcw className="size-3.5" />{t('assistant.newConversation')}</button> : null}
    </div>

    <div className="max-h-[38rem] min-h-56 space-y-5 overflow-y-auto p-4 sm:p-5" role="log" aria-live="polite" aria-label={t('assistant.conversation')}>
      {entries.length === 0 ? <div className="py-4 text-center">
        <p className="text-sm text-content-secondary">{t('assistant.empty')}</p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">{starters.map((value) => <button key={value} type="button" onClick={() => void send(value)} className="app-button-secondary app-button-sm">{value}</button>)}</div>
      </div> : entries.map((entry, index) => entry.role === 'user'
        ? <div key={index} className="ml-auto flex max-w-[90%] items-start justify-end gap-2 sm:max-w-[78%]"><p className="rounded-2xl rounded-tr-sm bg-primary px-4 py-3 text-sm leading-6 text-content-on-primary">{entry.content}</p><span className="mt-1 grid size-7 shrink-0 place-items-center rounded-full bg-surface-active"><UserRound className="size-3.5" /></span></div>
        : <AssistantMessage key={index} response={entry.response} onFollowup={(value) => void send(value)} />)}
      {loading ? <div role="status" className="flex items-center gap-2 text-sm text-content-secondary"><Loader2 className="size-4 animate-spin text-primary" />{t('assistant.loading')}</div> : null}
      {error ? <div role="alert" className="rounded-xl border border-danger/25 bg-danger/10 p-3 text-sm text-danger">{t(`assistant.errors.${error}`, { defaultValue: t('assistant.errors.unavailable') })}</div> : null}
      <div ref={endRef} />
    </div>

    <form onSubmit={submit} className="border-t border-line bg-surface-raised p-3 sm:p-4">
      <label htmlFor="assistant-message" className="sr-only">{t('assistant.inputLabel')}</label>
      <div className="flex items-end gap-2">
        <textarea id="assistant-message" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); if (message.trim()) void send(message); }
        }} maxLength={2000} rows={2} disabled={loading} placeholder={t('assistant.placeholder')} className="app-input min-h-12 flex-1 resize-none" />
        <button type="submit" disabled={loading || !message.trim()} className="app-button-primary min-h-12 px-4" aria-label={t('assistant.send')}><Send className="size-4" /><span className="hidden sm:inline">{t('assistant.send')}</span></button>
      </div>
      <p className="mt-2 text-xs text-content-muted">{t('assistant.disclaimer')}</p>
    </form>
  </div>;
}
