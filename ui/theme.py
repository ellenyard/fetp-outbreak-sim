"""UI theme injection for the investigation interface.

Provides CSS styling for the immersive investigation experience including
sidebar theming, animations, NPC cards, evidence cards, and scoring banners.
"""

import streamlit as st


def inject_investigation_theme():
    """Inject global CSS theme for an immersive investigation feel."""
    st.markdown("""
    <style>
    /* ── Dark Investigation Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: #334155;
    }

    /* ── Card & Container Styling ── */
    [data-testid="stExpander"] {
        border: 1px solid #334155;
        border-radius: 12px;
        overflow: hidden;
    }

    /* ── Animations ── */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes slideInLeft {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(245, 158, 11, 0); }
        100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
    }
    @keyframes slideDown {
        from { transform: translateY(-100%); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
    @keyframes progressFill {
        from { width: 0%; }
        to { width: var(--progress-width, 20%); }
    }
    @keyframes countUp {
        from { opacity: 0; transform: scale(0.5); }
        to { opacity: 1; transform: scale(1); }
    }

    /* ── NPC Chat Typing Indicator ── */
    .typing-indicator {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 8px 16px;
        background: #f1f5f9;
        border-radius: 16px;
        margin: 4px 0;
    }
    .typing-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #94a3b8;
        animation: typingBlink 1.4s infinite;
    }
    .typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .typing-dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes typingBlink {
        0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
        40% { opacity: 1; transform: scale(1); }
    }

    /* ── Achievement Toast Enhancement ── */
    .achievement-unlocked {
        animation: fadeInUp 0.6s ease-out;
        background: linear-gradient(135deg, #fef3c7, #fde68a);
        border: 2px solid #f59e0b;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        text-align: center;
    }

    /* ── Day Transition Banner ── */
    .day-banner {
        border-radius: 16px;
        padding: 48px 40px;
        color: white;
        text-align: center;
        animation: fadeInUp 0.8s ease-out;
        margin-bottom: 24px;
        background-size: cover;
        background-position: center;
        position: relative;
        overflow: hidden;
    }
    .day-banner::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: inherit;
        z-index: 0;
    }
    .day-banner > * { position: relative; z-index: 1; }
    .day-number {
        font-size: 4em;
        font-weight: 900;
        opacity: 0.3;
        line-height: 1;
    }
    .day-title {
        font-size: 1.8em;
        font-weight: 600;
        margin-top: -4px;
    }
    .day-subtitle {
        font-size: 1em;
        opacity: 0.8;
        margin-top: 4px;
    }
    .progress-track {
        background: rgba(255,255,255,0.2);
        border-radius: 8px;
        height: 8px;
        margin-top: 20px;
        overflow: hidden;
    }
    .progress-fill {
        background: #10b981;
        height: 8px;
        border-radius: 8px;
        animation: progressFill 1.5s ease-out forwards;
    }

    /* ── NPC Mood Portrait Card ── */
    .npc-portrait-card {
        border-radius: 16px;
        padding: 16px;
        text-align: center;
        transition: border-color 0.5s ease, box-shadow 0.5s ease;
        margin-bottom: 12px;
    }
    .npc-portrait-card img {
        border-radius: 12px;
        width: 100%;
        max-width: 200px;
    }
    .mood-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 600;
        color: white;
        margin-top: 8px;
    }
    .trust-bar-track {
        background: #e5e7eb;
        border-radius: 4px;
        height: 6px;
        margin-top: 8px;
        overflow: hidden;
    }
    .trust-bar-fill {
        height: 6px;
        border-radius: 4px;
        transition: width 0.5s ease, background 0.5s ease;
    }

    /* ── Evidence / Hint Cards ── */
    .hint-card {
        background: linear-gradient(135deg, #1e293b, #334155);
        border-left: 4px solid #f59e0b;
        border-radius: 8px;
        padding: 16px;
        margin: 12px 0;
        color: #e2e8f0;
        animation: slideInLeft 0.5s ease-out;
    }
    .hint-label {
        font-size: 0.75em;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #f59e0b;
        margin-bottom: 6px;
        font-weight: 600;
    }
    .hint-text {
        font-style: italic;
    }

    /* ── Scoring Hero Banner ── */
    .score-banner {
        border-radius: 20px;
        padding: 40px;
        text-align: center;
        margin: 20px 0;
        animation: fadeInUp 0.8s ease-out;
    }
    .score-tier-title {
        font-size: 1.5em;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    .score-number {
        font-size: 4em;
        font-weight: 900;
        margin: 8px 0;
        animation: countUp 0.6s ease-out 0.3s both;
    }
    .lives-saved {
        font-size: 1.3em;
        margin-top: 8px;
    }

    /* ── Timeline / Journal ── */
    .timeline-event {
        display: flex;
        margin-bottom: 12px;
        align-items: flex-start;
        animation: fadeIn 0.3s ease-out;
    }
    .timeline-bar {
        width: 4px;
        min-height: 44px;
        border-radius: 2px;
        margin-right: 16px;
        flex-shrink: 0;
    }
    .timeline-content {
        flex: 1;
    }
    .timeline-title {
        font-weight: 600;
        font-size: 0.95em;
    }
    .timeline-detail {
        font-size: 0.85em;
        color: #6b7280;
    }

    /* ── Achievement Badge Grid ── */
    .badge-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin: 16px 0;
    }
    .badge-item {
        background: linear-gradient(135deg, #fef3c7, #fff7ed);
        border: 2px solid #f59e0b;
        border-radius: 12px;
        padding: 12px 16px;
        text-align: center;
        min-width: 120px;
        flex: 0 0 auto;
        animation: fadeInUp 0.5s ease-out;
    }
    .badge-item.locked {
        background: #f1f5f9;
        border-color: #cbd5e1;
        opacity: 0.5;
    }
    .badge-emoji {
        font-size: 2em;
        display: block;
        margin-bottom: 4px;
    }
    .badge-name {
        font-weight: 700;
        font-size: 0.85em;
    }
    .badge-desc {
        font-size: 0.75em;
        color: #6b7280;
        margin-top: 2px;
    }

    /* ── Alert Banner Animation ── */
    .alert-banner {
        animation: slideDown 0.5s ease-out;
    }

    /* ── Mobile Responsiveness ── */
    @media (max-width: 768px) {
        .stColumns > div {
            min-width: 100% !important;
        }
        .day-banner .day-number {
            font-size: 2em !important;
        }
        .day-banner .day-title {
            font-size: 1.2em !important;
        }
        .npc-portrait-card {
            margin-bottom: 1em;
        }
        .score-banner .score-number {
            font-size: 2.5em !important;
        }
        [data-testid="stSidebar"] {
            min-width: 260px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
