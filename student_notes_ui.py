"""Small optional supplementary-record panel shared by student and coach views."""
import streamlit as st
from food_catalogue import MEAL_LABELS
from student_notes import prepare_note, save_note, load_notes, download_attachment, mark_note_counted
from tracker_storage import load_day
_UNSET = object()


def show_notes(get_sheet, username, notes, prefix):
    for note in notes:
        st.markdown(f"**{note['Date']} · {MEAL_LABELS.get(note['Meal'], note['Meal'])}**")
        if note['Remarks']:
            st.text(note['Remarks'])
        if note['needs_calories']:
            st.caption('热量待补充 · Not included in calorie totals')
            if prefix == 'student_note' and st.button('已补齐饮食热量 · Mark counted', key=f"counted_{note['note_id']}"):
                try:
                    saved_day = load_day(get_sheet('main'), username, note['Date'])
                    if not saved_day['food_log'] or saved_day['legacy']:
                        raise ValueError('请先在 Food Log 补齐并保存当天饮食。 Add and save the food in Food Log first.')
                    mark_note_counted(get_sheet('student_notes'), username, note['note_id'])
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error('标记未确认，请稍后重试。 Could not confirm the update; please retry.')
                else:
                    st.rerun()
        for file in note['files']:
            key = f"{prefix}_{note['note_id']}_{file['file_id']}"
            st.text(f"📎 {file['name']} · {file['size'] / 1024:.0f} KB")
            if st.button('准备下载附件 · Get attachment', key=key):
                try:
                    data, verified = download_attachment(get_sheet('student_notes'), get_sheet('student_attachments'),
                        username, note['note_id'], file['file_id'])
                    st.download_button('下载附件 · Download', data=data, file_name=verified['name'], mime=verified['mime'],
                                       key=key + '_download', on_click='ignore')
                except Exception:
                    st.error('附件暂时无法读取，请重试；原记录仍保留。 Could not load attachment; please retry.')


def render_student_notes(get_sheet, username, day):
    try:
        all_notes = load_notes(get_sheet('student_notes'), username)
        notes = [note for note in all_notes if note['Date'] == str(day)]
        available = True
    except Exception:
        notes, available, all_notes = [], False, None
    with st.expander('找不到食物？写备注／附上文件 · Remarks & attachments'):
        st.caption('写下食物、品牌或想补充的内容；不知道热量也能保存。')
        if not available:
            st.warning('暂时无法读取已有补充记录；当前输入仍可填写。 Could not load previous supplementary records.')
        version_key = f'note_form_version_{day}'
        version = st.session_state.get(version_key, 0)
        with st.form(f'supplement_{day}_{version}'):
            meal = st.selectbox('餐次 · Meal', list(MEAL_LABELS) + ['Other'],
                               format_func=lambda value: MEAL_LABELS.get(value, '其他 Other'))
            remarks = st.text_area('备注 · Remarks', max_chars=2000, key=f'remarks_{day}_{version}',
                                   placeholder='例如：午餐吃了半碗板面，找不到对应食物；或附上包装标签。')
            uploads = st.file_uploader('照片或文件（选填） · Photos or files', type=['jpg', 'jpeg', 'png', 'webp', 'pdf'],
                                      accept_multiple_files=True, max_upload_size=2, key=f'note_files_{day}_{version}',
                                      help='最多两份，每份 2 MB · Up to two files, 2 MB each')
            pending = st.checkbox('这笔食物尚未计入热量 · Food not counted yet', value=True)
            submit = st.form_submit_button('保存补充记录 · Save remarks', type='primary', use_container_width=True)
        if submit:
            try:
                prepared = prepare_note(username, day, meal, remarks,
                    [(item.name, item.getvalue()) for item in uploads], pending)
                note_sheet = get_sheet('student_notes', create=True)
                file_sheet = get_sheet('student_attachments', create=True) if uploads else None
                save_note(note_sheet, file_sheet, prepared)
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error('保存未确认，文字和附件仍留在此页，请重试。 Save not confirmed; your input is kept here. Please retry.')
            else:
                st.session_state[version_key] = version + 1
                st.session_state['note_saved_notice'] = str(day)
                st.rerun()
        if st.session_state.pop('note_saved_notice', None) == str(day):
            st.success('补充记录已保存 · Remarks saved')
        if notes:
            st.markdown('**当天已保存的补充记录 · Saved remarks**')
            show_notes(get_sheet, username, notes, 'student_note')
    return notes, available, all_notes


def render_note_history(get_sheet, username, prefix='note_history', notes=_UNSET):
    with st.expander('补充记录与附件历史 · Remarks history'):
        try:
            if notes is _UNSET:
                notes = load_notes(get_sheet('student_notes'), username)
            if notes is None:
                raise ValueError('Supplementary records unavailable.')
            if not notes:
                st.write('暂无补充记录 · No supplementary records yet')
            else:
                dates = sorted({note['Date'] for note in notes}, reverse=True)
                selected_day = st.selectbox('补充记录日期 · Remark date', dates, key=f'{prefix}_date')
                show_notes(get_sheet, username, [note for note in notes if note['Date'] == selected_day], prefix)
        except Exception:
            st.warning('暂时无法读取补充记录，请稍后重试。 Could not load supplementary records.')
