import { useParams } from 'react-router-dom';
import { AssistanceBanner } from '../../components/workspace/WorkspacePrimitives';
import Leadership from '../guild/Leadership';
import LeadershipRecruitment from '../guild/LeadershipRecruitment';

export default function AdminGuildLeadership({ recruitment = false }: { recruitment?: boolean }) {
  const { guildKey = '' } = useParams();
  return <div className="space-y-4"><AssistanceBanner guildName={guildKey} />{recruitment ? <LeadershipRecruitment guildKey={guildKey} /> : <Leadership guildKey={guildKey} />}</div>;
}
