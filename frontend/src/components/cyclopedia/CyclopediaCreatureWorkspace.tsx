import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

import { Container } from '../ui';
import { CreatureBrowserProvider, useCreatureBrowser } from './CreatureBrowserContext';
import CreaturePreviewPanel from './CreaturePreviewPanel';

export default function CyclopediaCreatureWorkspace({ children }: { children: ReactNode }) {
  return (
    <CreatureBrowserProvider>
      <CyclopediaCreatureWorkspaceInner>{children}</CyclopediaCreatureWorkspaceInner>
    </CreatureBrowserProvider>
  );
}

function CyclopediaCreatureWorkspaceInner({ children }: { children: ReactNode }) {
  const location = useLocation();
  const browser = useCreatureBrowser();
  const tab = new URLSearchParams(location.search).get('tab') || 'creatures';
  const supportsPreview = tab === 'creatures';
  const showPreview = supportsPreview && browser?.selectedCreatureId != null;

  return (
    <div className="cyclopedia-reference-frame" data-preview-open={showPreview ? 'true' : 'false'}>
      <main className="relative min-h-0 min-w-0 flex-1" data-workspace-main="cyclopedia">
        <Container>{children}</Container>
      </main>
      {showPreview && browser?.selectedCreatureId != null ? (
        <aside className="cyclopedia-creature-preview-dock" aria-label="Selected creature preview">
          <CreaturePreviewPanel creatureId={browser.selectedCreatureId} />
        </aside>
      ) : null}
    </div>
  );
}
