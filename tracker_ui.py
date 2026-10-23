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


def usage_instructions(demo=False):
    """Use the same compact guide in the demo and the signed-in tracker."""
    save_label = '体验保存 Try save' if demo else '保存当天记录 Save'
    return ('1. **饮食 Food Log：**选日期、餐次、食物与份数 → **Add Meal**。\n'
            '   「自己搭配」可把饭、肉、菜和油分次加入同一餐；也可直接选整份餐点。\n'
            '2. **运动 Exercise Log：**选运动、填分钟 → **Add activity**。\n'
            f'3. 记录后按 **{save_label}**。\n'
            '4. **Wellness History：**回看记录，或打开某天继续修改。\n\n'
            '**今日剩余 = 今日目标 − 饮食摄入 + 运动消耗。**高于目标表示当日净值超过当前目标。\n\n'
            '找不到食物时，可写备注或附上文件；未计入热量时，余额会注明「暂估」。')


def _balance_state(remaining):
    # Match the displayed precision so floating-point noise cannot show "0 over".
    shown = round(float(remaining), 1)
    return 'over' if shown < 0 else 'met' if shown == 0 else 'remaining'



def calorie_summary(intake, burned, net, remaining):
    badge = ''
    if remaining is not None:
        state = _balance_state(remaining)
        text = '已达目标 · At target' if state == 'met' else f'{format_energy(abs(remaining))} {"over" if state == "over" else "left"}'
        badge = f'<div class="mb-balance {state}">{text}</div>'
    return ('<div class="mb-summary" role="group" aria-label="每日热量 Daily calories">'
            f'<dl class="mb-stat"><dt>Food Intake <span>摄入</span></dt><dd>{format_energy(intake)}<small>kcal</small></dd></dl>'
            f'<dl class="mb-stat mb-stat-exercise"><dt>Exercise Burn <span>消耗</span></dt><dd>{format_energy(burned)}<small>kcal</small></dd></dl>'
            f'<dl class="mb-stat mb-stat-net"><dt>Net Calories <span>净值</span></dt><dd>{format_energy(net)}<small>kcal</small></dd>{badge}</dl></div>')


def remaining_panel(remaining, provisional=False):
    state = _balance_state(remaining)
    label = {'over': 'above target · 高于今日目标',
             'met': 'at target · 已达到今日目标',
             'remaining': 'remaining · 今日剩余'}[state]
    if provisional:
        label = {'over': 'above target · 暂估高于目标',
                 'met': 'balance · 暂估余额',
                 'remaining': 'remaining · 暂估剩余'}[state]
    icon = '<span class="mb-check" aria-hidden="true">≈</span>' if provisional else ''
    return (f'<div class="mb-remaining {state}{" provisional" if provisional else ""}" role="status">'
            f'{icon}'
            f'<div><strong>{format_energy(abs(remaining))}</strong> '
            f'<span>kcal {label}</span></div></div>')
