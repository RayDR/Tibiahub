import i18n from '../i18n';

const questEnhancement = {
  en: {
    duration: 'Duration',
    missionIndex: 'Mission index',
    rewardItems: 'Rewards',
    requirementItems: 'Required items',
    prerequisiteQuests: 'Prerequisite quests',
    noRewardItems: 'No item rewards are documented.',
    noRequirements: 'No item or quest requirements are documented.',
    itemPreview: 'Item preview',
    questPreview: 'Quest preview',
    loadingPreview: 'Loading local summary…',
    previewUnavailable: 'No local summary is available yet.',
    progress: 'Quest progress',
    markComplete: 'Mark completed',
    markIncomplete: 'Mark incomplete',
    completed: 'Completed',
    savedFor: 'Saved for {{character}}',
    sessionOnly: 'Saved for this browser session',
    sessionHelp: 'Sign in and verify a character to save completion per character.',
    selectCharacter: 'Character',
    noVerifiedCharacter: 'No verified character is available, so progress is stored only for this session.',
    progressLoadError: 'Character progress could not be loaded. Session progress is still available.',
    progressSaveError: 'Quest progress could not be saved.',
    itemAmount: '×{{amount}}',
  },
  es: {
    duration: 'Duración',
    missionIndex: 'Índice de etapas',
    rewardItems: 'Recompensas',
    requirementItems: 'Objetos requeridos',
    prerequisiteQuests: 'Quests requeridas',
    noRewardItems: 'No hay recompensas de objetos documentadas.',
    noRequirements: 'No hay objetos ni quests requeridas documentadas.',
    itemPreview: 'Vista previa del objeto',
    questPreview: 'Vista previa de la quest',
    loadingPreview: 'Cargando resumen local…',
    previewUnavailable: 'Aún no hay un resumen local disponible.',
    progress: 'Progreso de la quest',
    markComplete: 'Marcar como completada',
    markIncomplete: 'Marcar como pendiente',
    completed: 'Completada',
    savedFor: 'Guardado para {{character}}',
    sessionOnly: 'Guardado durante esta sesión del navegador',
    sessionHelp: 'Inicia sesión y verifica un personaje para guardar el progreso por personaje.',
    selectCharacter: 'Personaje',
    noVerifiedCharacter: 'No hay un personaje verificado disponible, así que el progreso se guarda solo durante esta sesión.',
    progressLoadError: 'No se pudo cargar el progreso del personaje. El progreso de sesión sigue disponible.',
    progressSaveError: 'No se pudo guardar el progreso de la quest.',
    itemAmount: '×{{amount}}',
  },
} as const;

for (const locale of ['en', 'es'] as const) {
  i18n.addResourceBundle(
    locale,
    'translation',
    { questEnhancement: questEnhancement[locale] },
    true,
    true,
  );
}

export default questEnhancement;
