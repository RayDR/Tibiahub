import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faGift, faSpinner, faTrophy, faUsers } from '@fortawesome/free-solid-svg-icons';
import { useTranslation } from 'react-i18next';

import { raffleApi, type PublicRaffle } from '../services/raffle';
import AutomaticRaffleDraw from '../components/raffle/AutomaticRaffleDraw';

const STATUS_BANNER_CLASS: Record<string, string> = {
  open: 'border-success/30 bg-success/20 text-success',
  closed: 'border-primary/30 bg-primary/20 text-primary',
  completed: 'border-info/30 bg-info/20 text-info',
  cancelled: 'border-danger/30 bg-danger/20 text-danger',
};

export default function RafflePublicPage() {
  const { publicCode } = useParams<{ publicCode: string }>();
  const { t } = useTranslation();

  const [raffle, setRaffle] = useState<PublicRaffle | null>(null);
  const [characterName, setCharacterName] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!publicCode) {
        setError(t('raffle.publicPage.invalidCode'));
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const data = await raffleApi.getPublicByCode(publicCode);
        setRaffle(data);
      } catch (loadError: any) {
        setError(loadError?.response?.data?.detail || loadError?.message || t('raffle.publicPage.loadError'));
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [publicCode, t]);

  const submitRegistration = async (event: FormEvent) => {
    event.preventDefault();
    if (!raffle) return;

    try {
      setBusy(true);
      setError(null);
      setSuccess(null);
      const updated = await raffleApi.registerPublicByCode(raffle.public_code, characterName);
      setRaffle(updated);
      setCharacterName('');
      setSuccess(t('raffle.publicPage.registered'));
    } catch (registerError: any) {
      setError(registerError?.response?.data?.detail || registerError?.message || t('raffle.publicPage.registerError'));
    } finally {
      setBusy(false);
    }
  };

  const registrationBlocked = raffle ? raffle.status !== 'open' : true;
  const bannerMessage = raffle?.status === 'draft'
    ? t('raffle.publicPage.draftBanner')
    : raffle?.status === 'cancelled'
    ? t('raffle.publicPage.cancelledBanner')
    : raffle?.status === 'completed'
    ? t('raffle.publicPage.completedBanner')
    : raffle?.status === 'closed'
    ? t('raffle.publicPage.closedBanner')
    : null;

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-content-secondary">
        <div className="flex items-center gap-3">
          <FontAwesomeIcon icon={faSpinner} spin className="h-8 w-8" />
          <span>{t('raffle.publicPage.loading')}</span>
        </div>
      </div>
    );
  }

  if (!raffle || error) {
    return (
      <div className="mx-auto mt-10 max-w-3xl rounded-xl border border-danger/30 bg-danger/15 p-6 text-danger">
        {error || t('raffle.publicPage.notFound')}
      </div>
    );
  }

  return (
    <div className="min-h-screen space-y-8 pb-16 pt-10">
      <section className="rounded-2xl border border-line bg-surface-base/70 p-6">
        <h1 className="text-3xl font-bold text-primary">{raffle.title}</h1>
        <p className="mt-2 text-content-secondary">{raffle.description || t('raffle.publicPage.descriptionFallback')}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-sm text-content-secondary">
          <span>{t('raffle.publicPage.guildLabel')}: {raffle.guild_name}</span>
          <span>&middot;</span>
          <span>{t('raffle.detail.accessMode')}: {t(`raffle.accessModes.${raffle.access_mode}`)}</span>
        </div>
        {bannerMessage && (
          <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${STATUS_BANNER_CLASS[raffle.status] || STATUS_BANNER_CLASS.closed}`}>
            {bannerMessage}
          </div>
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={submitRegistration} className="rounded-2xl border border-line bg-surface-base/70 p-6">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-content-primary">
            <FontAwesomeIcon icon={faUsers} className="h-5 w-5 text-primary" /> {t('raffle.publicPage.joinTitle')}
          </h2>
          <p className="mb-4 text-sm text-content-secondary">{t('raffle.publicPage.joinSubtitle')}</p>
          <input
            value={characterName}
            onChange={(e) => setCharacterName(e.target.value)}
            placeholder={t('raffle.publicPage.joinInputPlaceholder')}
            className="w-full rounded-xl border border-line bg-surface-base px-4 py-3 text-content-primary outline-none focus:border-primary"
            disabled={registrationBlocked || busy}
            required
          />
          <button
            type="submit"
            disabled={busy || registrationBlocked}
            className="mt-4 rounded-xl bg-primary px-4 py-3 font-semibold text-content-inverse disabled:opacity-50"
          >
            {busy ? t('raffle.publicPage.joining') : t('raffle.publicPage.joinButton')}
          </button>
          {success && <p className="mt-3 text-sm text-success">{success}</p>}
          {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        </form>

        <div className="rounded-2xl border border-line bg-surface-base/70 p-6">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-content-primary"><FontAwesomeIcon icon={faGift} className="text-primary" /> {t('raffle.publicPage.prizesTitle')}</h2>
          <div className="space-y-2 text-sm text-content-secondary">
            {raffle.prizes.map((prize) => (
              <div key={prize.id} className="rounded-lg border border-line bg-surface-base/50 px-3 py-2">
                {prize.name}: {prize.reward}
              </div>
            ))}
            {raffle.prizes.length === 0 && <div className="text-content-muted">{t('raffle.publicPage.noPrizes')}</div>}
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-line bg-surface-base/70 p-6">
          <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold text-content-primary"><FontAwesomeIcon icon={faUsers} className="text-primary" /> {t('raffle.publicPage.participantsTitle')}</h3>
          {raffle.show_participants ? (
            <>
              <div className="mb-3 text-sm text-content-secondary">{t('raffle.publicPage.participantsVisible', { count: raffle.participant_count })}</div>
              <div className="max-h-72 space-y-2 overflow-y-auto pr-2 text-sm">
                {raffle.participants.map((participant) => (
                  <div key={participant.character_name} className="rounded-lg border border-line bg-surface-base/50 px-3 py-2 text-content-secondary">
                    <div className="font-medium text-content-primary">{participant.character_name}</div>
                    <div className="text-xs text-content-muted">{participant.guild_rank || t('guild.member')}</div>
                  </div>
                ))}
                {raffle.participants.length === 0 && <div className="text-content-muted">{t('raffle.publicPage.noParticipants')}</div>}
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-line bg-surface-base/40 px-4 py-3 text-sm text-content-secondary">
              {t('raffle.publicPage.participantsHidden', { count: raffle.participant_count })}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-line bg-surface-base/70 p-6">
          <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold text-content-primary">
            <FontAwesomeIcon icon={faTrophy} className="h-5 w-5 text-primary" /> {t('raffle.publicPage.winnersTitle')}
          </h3>
          <div className="space-y-2 text-sm text-content-secondary">
            {raffle.winners.length > 0 && <AutomaticRaffleDraw published testMode={raffle.purpose === 'test'} participantNames={[...raffle.participants.map(item => item.character_name), ...raffle.winners.map(item => item.character_name)]} results={raffle.winners.map((winner, index) => ({ id: -(index + 1), prize_id: -(index + 1), prize_position: winner.prize_position, prize_name: winner.prize_name, amount: winner.amount, currency: winner.currency, character_name: winner.character_name, selection_index: index, candidate_count: raffle.participant_count, delivery_status: winner.delivery_status, delivery_deadline_at: winner.delivery_deadline_at }))} />}
            {raffle.winners.length === 0 && <div className="text-content-muted">{t('raffle.publicPage.winnersEmpty')}</div>}
          </div>
        </div>
      </section>
    </div>
  );
}
