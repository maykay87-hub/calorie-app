"""May Bloom's calorie-first presentation; no stored nutrition is changed here."""
from nutrition_registry import format_energy

from pathlib import Path

MAY_BLOOM_CSS = '<style>' + (Path(__file__).parent / 'assets' / 'may_bloom.css').read_text(encoding='utf-8') + '</style>'


def brand_header():
    """The existing pink bloom, drawn as a quiet brand mark rather than an emoji."""
    petals = ''.join(f'<ellipse cx="24" cy="13" rx="7.3" ry="10.2" transform="rotate({angle} 24 24)"/>'
                     for angle in (0, 72, 144, 216, 288))
    return ('<div class="mb-brand">'
            f'<svg class="mb-bloom" viewBox="0 0 48 48" aria-hidden="true"><g fill="currentColor">{petals}</g>'
            '<circle cx="24" cy="24" r="4.5" fill="#fffafc"/></svg>'
            '<div><h1 class="mb-title">May Bloom</h1>'
            '<p class="mb-brand-subtitle">Lifestyle Tracker <span>生活记录</span></p></div></div>')


def progress_scale(net, target):
    return ('<div class="mb-progress-scale">'
            f'<span>净值 {format_energy(net)} kcal</span>'
            f'<span>目标 {format_energy(target)} kcal</span></div>')



def calorie_summary(intake, burned, net, remaining):
    badge = ''
    if remaining is not None:
        over = remaining < 0
        badge = f'<div class="mb-balance{" over" if over else ""}">{format_energy(abs(remaining))} {"over" if over else "left"}</div>'
    return ('<div class="mb-summary" role="group" aria-label="每日热量 Daily calories">'
            f'<dl class="mb-stat"><dt>Food Intake <span>摄入</span></dt><dd>{format_energy(intake)}<small>kcal</small></dd></dl>'
            f'<dl class="mb-stat mb-stat-exercise"><dt>Exercise Burn <span>消耗</span></dt><dd>{format_energy(burned)}<small>kcal</small></dd></dl>'
            f'<dl class="mb-stat mb-stat-net"><dt>Net Calories <span>净值</span></dt><dd>{format_energy(net)}<small>kcal</small></dd>{badge}</dl></div>')


def remaining_panel(remaining, provisional=False):
    over = remaining < 0
    label = "above target · 高于目标" if over else "remaining · 今日剩余"
    if provisional:
        label = "above target · 暂估高于目标" if over else "remaining · 暂估剩余"
    return (f'<div class="mb-remaining{" provisional" if provisional else " over" if over else ""}" role="status">'
            f'<span class="mb-check">{"≈" if provisional else "↗" if over else "✓"}</span>'
            f'<div><strong>{format_energy(abs(remaining))}</strong> '
            f'<span>kcal {label}</span></div></div>')
