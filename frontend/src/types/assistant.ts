export type AssistantLanguage = 'en' | 'es';

export interface AssistantPartyMember {
  name: string;
  vocation?: string | null;
  level?: number | null;
}

export interface AssistantConversationContext {
  conversation_id: string;
  language: AssistantLanguage;
  known_access_unlocks: string[];
  completed_quests: string[];
  owned_items: string[];
  current_location?: string | null;
  character: { vocation?: string | null; level?: number | null };
  party_members: AssistantPartyMember[];
}

export interface AssistantEntityReference {
  key: string;
  entity_type: 'creature' | 'item' | 'npc' | 'quest' | 'location' | 'area' | 'town' | 'hunt_zone';
  id: string;
  knowledge_entity_id?: string | null;
  canonical_name: string;
  slug: string;
  image_url?: string | null;
  detail_route: string;
  metadata: Record<string, string | number | boolean | null>;
}

export interface AssistantContentPart {
  kind: 'text' | 'entity';
  text?: string | null;
  entity_key?: string | null;
}

export interface AssistantSection {
  kind: 'summary' | 'details' | 'access' | 'travel' | 'hunt' | 'acquisition' | 'quest' | 'warning';
  title: string;
  content: AssistantContentPart[];
  entity_keys: string[];
}

export interface AssistantRouteStep {
  sequence: number;
  kind: string;
  instruction?: string | null;
  location_name?: string | null;
  x?: number | null;
  y?: number | null;
  z?: number | null;
}

export interface AssistantMapReference {
  id: string;
  name: string;
  image_url: string;
  verification_state: string;
  confidence: string;
}

export interface AssistantRouteReference {
  key: string;
  id: string;
  name: string;
  slug: string;
  start_location?: string | null;
  end_location?: string | null;
  verification_state: string;
  confidence: string;
  steps: AssistantRouteStep[];
  maps: AssistantMapReference[];
}

export interface AssistantPrerequisite {
  status: 'required' | 'satisfied' | 'unknown';
  content: AssistantContentPart[];
}

export interface AssistantResponse {
  conversation_id: string;
  language: AssistantLanguage;
  message: AssistantContentPart[];
  sections: AssistantSection[];
  entities: AssistantEntityReference[];
  entity_cards: string[];
  routes: AssistantRouteReference[];
  prerequisites: AssistantPrerequisite[];
  warnings: Array<{ code: string; severity: 'info' | 'warning' | 'error'; message: string }>;
  suggested_followups: string[];
  context: AssistantConversationContext;
  grounding: { tool_calls: number; evidence_keys: string[]; data_gaps: string[] };
}

export interface AssistantHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AssistantRequest {
  message: string;
  history: AssistantHistoryMessage[];
  context?: AssistantConversationContext | null;
}
