"""May Bloom's calorie-first presentation; no stored nutrition is changed here."""
from nutrition_registry import format_energy

MAY_BLOOM_CSS = '''<style>
:root { --mb-rose:#b94e73; --mb-ink:#4c3941; }
.stApp { background:#fffdfd; color:var(--mb-ink); }
.block-container { max-width:1180px; padding-top:3.4rem; padding-bottom:3rem; }
[data-testid="stSidebar"] { background:#edf5f5; border-right:1px solid #d5e6e6; }
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 { color:#376568; }
.mb-profile-kicker { color:#376568; font-size:.75rem; font-weight:700; letter-spacing:.12em; margin-top:.4rem; }
.mb-title { font-size:clamp(1.8rem,3.1vw,2.8rem)!important; line-height:1.22!important; font-weight:700; color:#a44b68!important; margin:0 0 1rem!important; padding:0!important; }
.mb-title span { color:#d15f88; }
.mb-summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1rem; margin:.45rem 0 1.2rem; }
.mb-stat { margin:0; padding:1.1rem 1.2rem; border:1px solid #f0d4c3; border-radius:16px; background:#fff3e9; min-width:0; }
.mb-stat dt { font-size:.95rem; color:#7b4933; font-weight:600; margin:0 0 .55rem; }
.mb-stat dt span { font-size:.8em; font-weight:400; margin-left:.25rem; }
.mb-stat dd { font-size:clamp(1.65rem,3vw,2.4rem); font-weight:650; color:#71432f; line-height:1.2; margin:0; overflow-wrap:anywhere; }
.mb-stat small { font-size:.85rem; font-weight:400; margin-left:.3rem; }
.mb-stat-exercise { background:#edf6f0; border-color:#cfe2d5; }
.mb-stat-exercise dt,.mb-stat-exercise dd { color:#36654b; }
.mb-stat-net { background:#fceaf0; border-color:#eab3c7; }
.mb-stat-net dt,.mb-stat-net dd { color:#9d3e60; }
.mb-balance { display:inline-block; margin-top:.65rem; padding:.25rem .6rem; font-size:.8rem; font-weight:600; background:#e2f0e6; border-radius:30px; color:#2d6748; }
.mb-balance.over { background:#fae4db; color:#974b32; }
.mb-progress-title { color:#6f535e; font-size:.95rem; font-weight:600; margin:.2rem 0 .5rem; }
[data-testid="stProgress"] [role="progressbar"]>div { background:#d17493; }
.mb-remaining { display:flex; gap:.8rem; align-items:center; border:1px solid #cfe6df; background:#edf8f3; border-radius:12px; padding:.8rem 1.1rem; margin:.45rem 0 1rem; color:#2d6748; }
.mb-remaining strong { font-size:1.65rem; }
.mb-remaining span { font-size:1rem; }
.mb-remaining .mb-check { font-size:1.5rem; }
.mb-remaining.over { border-color:#f0d2bd; background:#fff2e8; color:#8b492d; }
.mb-section-title { color:#b34c72!important; font-size:1.55rem!important; margin:.7rem 0 .8rem!important; padding:0!important; }
.mb-section-title small { color:#8b6875; font-size:.85rem; font-weight:400; margin-left:.6rem; }
[data-testid="stForm"] { background:#fff; border:1px solid #efdce4; border-radius:14px; }
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input { color:#4c3941; }
[data-testid="stSidebar"] [data-baseweb="input"],[data-testid="stSidebar"] [data-baseweb="select"]>div { background:#fff; }
[data-testid="stTabs"] [role="tablist"] { gap:1.3rem; border-bottom:1px solid #f0dce4; }
[data-testid="stTabs"] [role="tab"] { min-height:48px; font-weight:600; color:#875669; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color:#bd4e78; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background:#cf6d8b; }
[data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button { min-height:44px; border-radius:10px; }
[data-testid="stButton"] button[kind="primary"],button[data-testid="baseButton-primary"],[data-testid="stFormSubmitButton"] button { background:#c45f82!important; border-color:#c45f82!important; color:#fff!important; }
[data-testid="stButton"] button[kind="primary"]:hover,[data-testid="stFormSubmitButton"] button:hover { background:#ac466c!important; border-color:#ac466c!important; }
[data-testid="stButton"] button:disabled,[data-testid="stFormSubmitButton"] button:disabled { background:#f1e7eb!important; border-color:#e3d4db!important; color:#77646e!important; }
[data-testid="stSidebar"] button[kind="primary"] { background:#477c7d!important; border-color:#477c7d!important; }
@media (max-width:640px) {
 .block-container { padding-left:1rem; padding-right:1rem; padding-top:3.3rem; }
 .mb-title { font-size:1.85rem!important; }
 .mb-summary { gap:.45rem; }
 .mb-stat { padding:.8rem .6rem; border-radius:12px; }
 .mb-stat dt { font-size:.76rem; min-height:2.4em; margin-bottom:.3rem; }
 .mb-stat dt span { display:block; margin:.15rem 0 0; font-size:.85em; }
 .mb-stat dd { font-size:1.55rem; }
 .mb-stat small { display:block; margin:.15rem 0 0; font-size:.7rem; }
 .mb-balance { font-size:.66rem; padding:.2rem .35rem; }
 .mb-remaining { padding:.7rem .8rem; gap:.55rem; }
 .mb-remaining strong { font-size:1.5rem; }
 .mb-remaining span { font-size:.88rem; }
 [data-testid="stTabs"] [role="tablist"] { gap:.2rem; }
 [data-testid="stTabs"] [role="tab"] { padding-left:.3rem; padding-right:.3rem; }
 [data-testid="stTabs"] [role="tab"] p { font-size:.78rem; }
 [data-testid="stForm"] { padding:.8rem; }
 [data-testid="stForm"] [data-testid="stHorizontalBlock"] { flex-wrap:wrap!important; }
 [data-testid="stForm"] [data-testid="stColumn"] { flex:1 1 100%!important; width:100%!important; min-width:100%!important; }
}
</style>'''


def calorie_summary(intake, burned, net, remaining):
    badge = ''
    if remaining is not None:
        over = remaining < 0
        badge = f'<div class="mb-balance{" over" if over else ""}">{format_energy(abs(remaining))} {"over" if over else "left"}</div>'
    return ('<div class="mb-summary" role="group" aria-label="每日热量 Daily calories">'
            f'<dl class="mb-stat"><dt>🍽️ Food Intake <span>摄入</span></dt><dd>{format_energy(intake)}<small>kcal</small></dd></dl>'
            f'<dl class="mb-stat mb-stat-exercise"><dt>🔥 Exercise Burn <span>消耗</span></dt><dd>{format_energy(burned)}<small>kcal</small></dd></dl>'
            f'<dl class="mb-stat mb-stat-net"><dt>⚖️ Net Calories <span>净值</span></dt><dd>{format_energy(net)}<small>kcal</small></dd>{badge}</dl></div>')


def remaining_panel(remaining):
    over = remaining < 0
    return (f'<div class="mb-remaining{" over" if over else ""}" role="status">'
            f'<span class="mb-check">{"↗" if over else "✓"}</span>'
            f'<div><strong>{format_energy(abs(remaining))}</strong> '
            f'<span>kcal {"above target · 高于目标" if over else "remaining · 今日剩余"}</span></div></div>')
