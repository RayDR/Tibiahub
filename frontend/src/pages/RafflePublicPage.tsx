import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faGift, faSpinner, faTrophy, faUsers } from '@fortawesome/free-solid-svg-icons';
import { useTranslation } from 'react-i18next';

import { raffleApi, type Raffle } from '../services/raffle';

const STATUS_BANNER_CLASS: Record<string, string> = {
  open: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100',
  closed: 'border-amber-500/30 bg-amber-950/20 text-amber-100',
  completed: 'border-blue-500/30 bg-blue-950/20 text-blue-100',
  cancelled: 'border-red-500/30 bg-red-950/20 text-red-100',
};

export default function RafflePublicPage() {
  const { publicCode } = useParams<{ publicCode: string }>();
  const { t } = useTranslation();

  const [raffle, setRaffle] = useState<Raffle | null>(null);
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
      <div className="flex min-h-[50vh] items-center justify-center text-slate-300">
        <div className="flex items-center gap-3">
          <FontAwesomeIcon icon={faSpinner} spin className="h-8 w-8" />
          <span>{t('raffle.publicPage.loading')}</span>
        </div>
      </div>
    );
  }

  if (!raffle || error) {
    return (
      <div className="mx-auto mt-10 max-w-3xl rounded-xl border border-red-500/30 bg-red-950/30 p-6 text-red-100">
        {error || t('raffle.publicPage.notFound')}
      </div>
    );
  }

  return (
    <div className="min-h-screen space-y-8 pb-16 pt-10">
      <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
        <h1 className="text-3xl font-bold text-amber-200">{raffle.title}</h1>
        <p className="mt-2 text-slate-300">{raffle.description || t('raffle.publicPage.descriptionFallback')}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-sm text-slate-400">
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
        <form onSubmit={submitRegistration} className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-slate-100">
            <FontAwesomeIcon icon={faUsers} className="h-5 w-5 text-amber-400" /> {t('raffle.publicPage.joinTitle')}
          </h2>
          <p className="mb-4 text-sm text-slate-400">{t('raffle.publicPage.joinSubtitle')}</p>
          <input
            value={characterName}
            onChange={(e) => setCharacterName(e.target.value)}
            placeholder={t('raffle.publicPage.joinInputPlaceholder')}
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none focus:border-amber-500"
            disabled={registrationBlocked || busy}
            required
          />
          <button
            type="submit"
            disabled={busy || registrationBlocked}
            className="mt-4 rounded-xl bg-amber-500 px-4 py-3 font-semibold text-slate-950 disabled:opacity-50"
          >
            {busy ? t('raffle.publicPage.joining') : t('raffle.publicPage.joinButton')}
          </button>
          {success && <p className="mt-3 text-sm text-emerald-300">{success}</p>}
          {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
        </form>

        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-slate-100"><FontAwesomeIcon icon={faGift} className="text-amber-400" /> {t('raffle.publicPage.prizesTitle')}</h2>
          <div className="space-y-2 text-sm text-slate-300">
            {raffle.prizes.map((prize) => (
              <div key={prize.id} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
                {prize.name}: {prize.reward}
              </div>
            ))}
            {raffle.prizes.length === 0 && <div className="text-slate-500">{t('raffle.publicPage.noPrizes')}</div>}
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold text-slate-100"><FontAwesomeIcon icon={faUsers} className="text-amber-400" /> {t('raffle.publicPage.participantsTitle')}</h3>
          {raffle.show_participants ? (
            <>
              <div className="mb-3 text-sm text-slate-400">{t('raffle.publicPage.participantsVisible', { count: raffle.participant_count })}</div>
              <div className="max-h-72 space-y-2 overflow-y-auto pr-2 text-sm">
                {raffle.participants.map((participant) => (
                  <div key={participant.id} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-slate-300">
                    <div className="font-medium text-slate-100">{participant.character_name}</div>
                    <div className="text-xs text-slate-500">{participant.guild_rank || t('guild.member')}</div>
                  </div>
                ))}
                {raffle.participants.length === 0 && <div className="text-slate-500">{t('raffle.publicPage.noParticipants')}</div>}
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-slate-800 bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
              {t('raffle.publicPage.participantsHidden', { count: raffle.participant_count })}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
          <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold text-slate-100">
            <FontAwesomeIcon icon={faTrophy} className="h-5 w-5 text-amber-400" /> {t('raffle.publicPage.winnersTitle')}
          </h3>
          <div className="space-y-2 text-sm text-slate-300">
            {raffle.current_winners.map((winner) => (
              <div key={winner.id} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
                <div className="font-medium text-slate-100">{winner.prize_name}</div>
                <div>{winner.character_name}</div>
                <div className="text-xs text-slate-500">{t('raffle.publicPage.winnerRun', { run: winner.run_number })}</div>
              </div>
            ))}
            {raffle.current_winners.length === 0 && <div className="text-slate-500">{t('raffle.publicPage.winnersEmpty')}</div>}
          </div>
        </div>
      </section>
    </div>
  );
}
