import { useParams } from 'react-router-dom';
import Leadership from '../guild/Leadership';
import LeadershipRecruitment from '../guild/LeadershipRecruitment';

export default function AdminGuildLeadership({ recruitment = false }: { recruitment?: boolean }) {
  const { guildKey = '' } = useParams();
  return recruitment ? <LeadershipRecruitment guildKey={guildKey} /> : <Leadership guildKey={guildKey} />;
}
