import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { MobileSectionTabs, WorkspaceHeader } from '../../components/workspace/WorkspacePrimitives';
import AutomaticRaffleOperations from './AutomaticRaffleOperations';
import Raffle from './Raffle';

export default function RafflesWorkspace() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const requested = params.get('section') || 'upcoming';
  const section = ['upcoming', 'participants', 'eligibility', 'draw', 'results', 'history'].includes(requested) ? requested : 'upcoming';
  const tabs = ['upcoming', 'participants', 'eligibility', 'draw', 'results', 'history'].map(id => ({ id, label: t(`workspace.raffles.tabs.${id}`) }));
  return <div className="space-y-4"><WorkspaceHeader title={t('workspace.raffles.title')} subtitle={t('workspace.raffles.subtitle')} /><MobileSectionTabs tabs={tabs} active={section} onChange={(value) => setParams({ section: value })} />{section === 'history' ? <Raffle /> : <AutomaticRaffleOperations />}</div>;
}
