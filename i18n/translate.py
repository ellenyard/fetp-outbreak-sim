"""Translation / internationalisation (i18n) system.

Provides ``t()`` for looking up UI and story strings by key, with
fallback through: locale JSON bundle -> in-code fallback dict -> English
fallback -> raw key.

Design goals:
- Keep UI and scenario text out of logic as much as possible.
- Support multiple languages via JSON locale bundles:
      locales/<lang>/ui.json
      locales/<lang>/story.json
- Provide a safe fallback to minimal in-code English defaults when files
  are missing.

NOTE: This is an incremental migration.  Not every string in the app uses
``t()`` yet.  New/edited UI strings should always use ``t()``.
"""

import json
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LANG = "en"
SUPPORTED_LANGS = ["en", "es", "fr", "pt"]

# Minimal fallback strings (UI)
_FALLBACK_UI = {
    "en": {
        "title": "AES Outbreak Investigation – Sidero Valley",
        "language_header": "Language",
        "language_select": "Select language:",
        "facilitator_header": "Facilitator",
        "facilitator_mode": "Facilitator mode",
        "facilitator_code": "Facilitator code",
        "facilitator_bad_code": "Incorrect facilitator code.",
        "day": "Day",
        "budget": "Budget",
        "time_remaining": "Time remaining",
        "hours": "hours",
        "lab_credits": "Lab credits",
        "progress": "Progress",
        "go_to": "Go to",
        "overview": "Overview / Briefing",
        "casefinding": "Case Finding",
        "descriptive": "Descriptive Epi",
        "interviews": "Interviews",
        "spotmap": "Spot Map",
        "study": "Data & Study Design",
        "lab": "Lab & Environment",
        "outcome": "Interventions & Outcome",
        "villages": "Village Profiles",
        "notebook": "Investigation Notebook",
        "map": "Map",
        "medical_records": "Medical Records",
        "clinic_register": "Clinic Register Scan",
        "clinic_log_abstraction": "Clinic Log Abstraction",
        "case_finding_debrief": "Case-finding Debrief",
        "day1_lab_brief": "Day 1 Lab Brief",
        "triangulation_checkpoint": "Triangulation Checkpoint",
        "advance_day": "Advance to Day",
        "cannot_advance": "Cannot advance yet. See missing tasks on Overview.",
        "missing_tasks_title": "Missing tasks before you can advance:",
        "locked_until_day": "Locked until Day {day}.",
        "chat_prompt": "Ask your question...",
        "save": "Save",
        "submit": "Submit",
        "download": "Download",
        "begin_investigation": "Begin investigation",
        # Day briefing labels
        "day1_briefing": "Day 1: Situation Assessment",
        "day2_briefing": "Day 2: Study Design",
        "day3_briefing": "Day 3: Data Collection",
        "day4_briefing": "Day 4: Analysis & Laboratory",
        "day5_briefing": "Day 5: Recommendations",
        "key_tasks": "Key tasks",
        "key_outputs": "Key outputs",
        "review_line_list": "Review initial line list and epi curve",
        "review_clinic_records": "Search clinic records for additional cases",
        "describe_cases": "Describe cases by person, place, and time",
        "conduct_interviews": "Conduct hypothesis-generating interviews",
        "find_additional_cases": "Expand case finding",
        "develop_case_def": "Refine the case definition",
        "develop_hypotheses": "Document hypotheses and plan next steps",
        "output_updated_line_list": "Updated line list",
        "output_working_case_def": "Working case definition",
        "output_initial_hypotheses": "Initial hypotheses",
        # Prerequisite messages (human-readable)
        "prereq.day1.case_definition": "Save a working case definition (Overview).",
        "prereq.day1.hypothesis": "Document at least one hypothesis (Overview).",
        "prereq.day1.interviews": "Complete at least 2 hypothesis-generating interviews (Interviews).",
        "prereq.day2.study_design": "Select a study design (Data & Study Design).",
        "prereq.day2.questionnaire": "Upload and save your questionnaire (XLSForm) (Data & Study Design).",
        "prereq.day2.dataset": "Generate your simulated dataset for analysis (Data & Study Design).",
        "prereq.day3.analysis": "Confirm you completed analysis and summarize key results (Overview / Day 3).",
        "prereq.day4.lab_order": "Place at least one lab order (Lab & Environment).",
        "prereq.day4.environment": "Record at least one environmental action (Lab & Environment).",
        "prereq.day4.draft_interventions": "Record draft interventions (Outcome tab, draft section).",
        # Lab labels (anti-spoiler)
        "lab_test": "Test",
        "lab_results": "Lab results",
        "lab_pending": "PENDING",
    },
    "es": {
        "title": "Investigación de Brote de AES – Valle de Sidero",
        "language_header": "Idioma",
        "language_select": "Seleccionar idioma:",
        "facilitator_header": "Facilitador",
        "facilitator_mode": "Modo facilitador",
        "facilitator_code": "Código de facilitador",
        "facilitator_bad_code": "Código incorrecto.",
        "day": "Día",
        "budget": "Presupuesto",
        "time_remaining": "Tiempo restante",
        "hours": "horas",
        "lab_credits": "Créditos de laboratorio",
        "progress": "Progreso",
        "go_to": "Ir a",
        "overview": "Resumen / Briefing",
        "casefinding": "Búsqueda de casos",
        "descriptive": "Epi descriptiva",
        "interviews": "Entrevistas",
        "spotmap": "Mapa de puntos",
        "study": "Datos y diseño",
        "lab": "Laboratorio y ambiente",
        "outcome": "Intervenciones",
        "villages": "Perfiles de aldeas",
        "notebook": "Cuaderno",
        "map": "Mapa",
        "medical_records": "Registros médicos",
        "clinic_register": "Registro de clínica",
        "advance_day": "Avanzar al día",
        "cannot_advance": "Aún no puede avanzar. Consulte las tareas pendientes en Resumen.",
        "missing_tasks_title": "Tareas pendientes antes de avanzar:",
        "locked_until_day": "Bloqueado hasta el Día {day}.",
        "chat_prompt": "Escribe tu pregunta...",
        "save": "Guardar",
        "submit": "Enviar",
        "download": "Descargar",
        "begin_investigation": "Iniciar investigación",
        "lab_test": "Prueba",
        "lab_results": "Resultados de laboratorio",
        "lab_pending": "PENDIENTE",
    },
    "fr": {
        "title": "Investigation d'épidémie AES – Vallée de Sidero",
        "language_header": "Langue",
        "language_select": "Choisir la langue :",
        "facilitator_header": "Facilitateur",
        "facilitator_mode": "Mode facilitateur",
        "facilitator_code": "Code facilitateur",
        "facilitator_bad_code": "Code incorrect.",
        "day": "Jour",
        "budget": "Budget",
        "time_remaining": "Temps restant",
        "hours": "heures",
        "lab_credits": "Crédits labo",
        "progress": "Progrès",
        "go_to": "Aller à",
        "overview": "Aperçu / Briefing",
        "casefinding": "Recherche de cas",
        "descriptive": "Épi descriptive",
        "interviews": "Entretiens",
        "spotmap": "Carte des points",
        "study": "Données et conception",
        "lab": "Labo et environnement",
        "outcome": "Interventions",
        "villages": "Profils des villages",
        "notebook": "Carnet",
        "map": "Carte",
        "medical_records": "Dossiers médicaux",
        "clinic_register": "Registre de la clinique",
        "advance_day": "Passer au jour",
        "cannot_advance": "Impossible d'avancer. Voir les tâches manquantes dans Aperçu.",
        "missing_tasks_title": "Tâches manquantes avant d'avancer :",
        "locked_until_day": "Bloqué jusqu'au Jour {day}.",
        "chat_prompt": "Posez votre question...",
        "save": "Enregistrer",
        "submit": "Soumettre",
        "download": "Télécharger",
        "begin_investigation": "Commencer l'investigation",
        "lab_test": "Test",
        "lab_results": "Résultats de laboratoire",
        "lab_pending": "EN ATTENTE",
    },
    "pt": {
        "title": "Investigação de Surto de AES – Vale de Sidero",
        "language_header": "Idioma",
        "language_select": "Selecionar idioma:",
        "facilitator_header": "Facilitador",
        "facilitator_mode": "Modo facilitador",
        "facilitator_code": "Código do facilitador",
        "facilitator_bad_code": "Código incorreto.",
        "day": "Dia",
        "budget": "Orçamento",
        "time_remaining": "Tempo restante",
        "hours": "horas",
        "lab_credits": "Créditos de laboratório",
        "progress": "Progresso",
        "go_to": "Ir para",
        "overview": "Visão geral / briefing",
        "casefinding": "Busca de casos",
        "descriptive": "Epi descritiva",
        "interviews": "Entrevistas",
        "spotmap": "Mapa de pontos",
        "study": "Dados e desenho",
        "lab": "Laboratório e ambiente",
        "outcome": "Intervenções",
        "villages": "Perfis das aldeias",
        "notebook": "Caderno",
        "map": "Mapa",
        "medical_records": "Registros médicos",
        "clinic_register": "Registro da clínica",
        "advance_day": "Avançar para o dia",
        "cannot_advance": "Ainda não é possível avançar. Veja as tarefas pendentes em Visão geral.",
        "missing_tasks_title": "Tarefas pendentes antes de avançar:",
        "locked_until_day": "Bloqueado até o Dia {day}.",
        "chat_prompt": "Digite sua pergunta...",
        "save": "Salvar",
        "submit": "Enviar",
        "download": "Baixar",
        "begin_investigation": "Iniciar investigação",
        "lab_test": "Teste",
        "lab_results": "Resultados laboratoriais",
        "lab_pending": "PENDENTE",
    },
}

# ---------------------------------------------------------------------------
# Locale bundle loader
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_locale_bundle(lang: str, bundle: str) -> dict:
    # Locale files live next to app.py in Streamlit Cloud
    app_root = Path(__file__).resolve().parent.parent
    locale_candidates = [
        app_root / "locales" / lang,
        app_root / "Locales" / lang,
    ]
    for base in locale_candidates:
        fp = base / f"{bundle}.json"
        if fp.exists():
            try:
                return json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


def _get_from_dict(d: dict, key: str):
    # Supports both flat keys and dotted paths
    if key in d:
        return d[key]
    cur = d
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def t(key: str, default: str = None, bundle: str = "ui", **kwargs) -> str:
    """Translate key using the current session language.

    - Falls back to English and then to provided ``default`` and finally to the key itself.
    - Supports ``.format(**kwargs)`` interpolation.
    """
    lang = st.session_state.get("language", DEFAULT_LANG) or DEFAULT_LANG
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG

    # Try file-based bundle first
    data = _load_locale_bundle(lang, bundle) or {}
    val = _get_from_dict(data, key)

    # Fallback to minimal in-code strings
    if val is None:
        val = _FALLBACK_UI.get(lang, {}).get(key)
    if val is None:
        val = _FALLBACK_UI.get(DEFAULT_LANG, {}).get(key)
    if val is None:
        val = default if default is not None else key

    try:
        return str(val).format(**kwargs)
    except Exception:
        return str(val)
