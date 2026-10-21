'use strict';
const $=id=>document.getElementById(id);
let activationToken=new URLSearchParams(location.hash.slice(1)).get('activate');
if(activationToken){history.replaceState(null,'',location.pathname);$('activate').hidden=false;$('login').hidden=true;}
const dateText=epoch=>new Intl.DateTimeFormat('en-MY',{timeZone:'Asia/Kuala_Lumpur',dateStyle:'medium',timeStyle:'short'}).format(new Date(epoch*1000))+' MYT';
function notice(text){$('notice').textContent=text;}
async function api(path,body){
  const response=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data=await response.json();if(!response.ok){const error=new Error(data.error||data.detail||'暂时无法完成，请重试。 Please retry.');error.status=response.status;throw error;}return data;
}
async function action(button,fn){button.disabled=true;notice('');try{await fn();}catch(error){notice(typeof error.message==='string'?error.message:'请重试。 Please retry.');}finally{button.disabled=false;}}
function safeLink(element,url,hosts){try{const target=new URL(url);if(target.protocol!=='https:'||!hosts.includes(target.hostname)||target.username||target.password)throw Error();element.href=target.href;element.hidden=false;}catch{element.hidden=true;}}
async function member(){
  const me=await api('/api/me');$('login').hidden=true;$('activate').hidden=true;$('member').hidden=false;
  $('coach').hidden=!me.is_coach;$('member-cards').hidden=!!me.is_coach;$('member-title').textContent=me.is_coach?'May 的预约管理':'欢迎回来';
  $('student-booking').hidden=!!me.is_coach;
  if(me.is_coach){await coachSummary();return;}
  $('access-status').textContent=me.active?'使用中 · Active':'暂未开通／已到期';
  $('access-end').textContent=me.ends_at?'有效至 · Until '+dateText(me.ends_at):'查看账单或联系 May · Check billing or contact May';
  $('credits').textContent=String(me.credits);
  if(me.active)safeLink($('tracker-link'),me.tracker_url,['maybloom-lifestyle-tracker.streamlit.app','may-bloom-lab.streamlit.app']);else $('tracker-link').hidden=true;
  safeLink($('billing-link'),me.billing_portal_url,['billing.stripe.com']);
  $('appointments').replaceChildren();for(const appointment of me.appointments){const p=document.createElement('p');p.className='appointment';p.textContent=dateText(appointment.starts_at)+ (appointment.ends_at*1000<Date.now()?' · 已结束 / Past':' · 已预约 / Booked');$('appointments').append(p);}
  if(!me.appointments.length)$('appointments').textContent='暂无预约 · No appointments yet';
  $('slots').replaceChildren();
  if(!me.booking_enabled){$('booking-status').textContent='预约时段尚未开放，请联系 May。 Booking is not open; please contact May.';return;}
  if(!me.credits){$('booking-status').textContent='你的方案目前没有可用咨询次数。 No consultation credits are currently available.';return;}
  const {slots}=await api('/api/slots');$('booking-status').textContent=slots.length?'':'目前没有开放时段，请稍后查看或联系 May。 No published availability; check later or contact May.';
  for(const slot of slots){const button=document.createElement('button');button.type='button';button.textContent=dateText(slot.starts_at);const requestId=crypto.randomUUID?.()||Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');button.addEventListener('click',()=>action(button,async()=>{if(!confirm('确认预约 / Confirm booking:\n'+dateText(slot.starts_at)+'\n45 minutes'))return;await api('/api/book',{slot_id:slot.id,request_id:requestId});await member();notice('预约已记录，请留意确认邮件。 Booking recorded; look out for your confirmation email.');}));$('slots').append(button);}
}
$('login-form').addEventListener('submit',event=>{event.preventDefault();action(event.submitter,async()=>{await api('/api/login',{email:$('email').value,password:$('password').value});$('password').value='';await member();});});
$('activate-form').addEventListener('submit',event=>{event.preventDefault();action(event.submitter,async()=>{await api('/api/activate',{token:activationToken,password:$('new-password').value});activationToken=null;$('new-password').value='';await member();});});
$('request-activation').addEventListener('click',event=>action(event.currentTarget,async()=>{if(!$('email').reportValidity()||!$('email').value)return;const result=await api('/api/request-activation',{email:$('email').value});notice(result.message);}));
$('logout').addEventListener('click',event=>action(event.currentTarget,async()=>{await api('/api/logout',{});location.replace('/');}));
async function coachSummary(){
  const summary=await api('/api/coach/summary');const accounts=new Map(summary.accounts.map(a=>[a.id,a]));const slots=new Map(summary.slots.map(s=>[s.id,s]));
  $('coach-slots').replaceChildren();for(const slot of summary.slots.filter(s=>s.status==='available').sort((a,b)=>a.starts_at-b.starts_at)){const row=document.createElement('p');row.className='appointment';row.textContent=dateText(slot.starts_at)+' ';const button=document.createElement('button');button.type='button';button.className='text-button';button.textContent='关闭此时段 · Close';button.addEventListener('click',()=>action(button,async()=>{await api('/api/coach/close-slot',{slot_id:slot.id});await coachSummary();}));row.append(button);$('coach-slots').append(row);}
  if(!$('coach-slots').children.length)$('coach-slots').textContent='暂无开放时段 · No published slots';
  $('coach-bookings').replaceChildren();for(const booking of summary.appointments){const slot=slots.get(booking.slot_id);const row=document.createElement('p');row.className='appointment';row.textContent=(accounts.get(booking.account_id)?.email||'Member')+' · '+dateText(slot.starts_at);$('coach-bookings').append(row);}
  if(!$('coach-bookings').children.length)$('coach-bookings').textContent='暂无预约 · No bookings';
  $('coach-issues').replaceChildren();for(const issue of summary.issues){const row=document.createElement('p');row.textContent=issue.kind+' · '+issue.id;$('coach-issues').append(row);}
  const failed=summary.mail.filter(m=>m.status==='uncertain').length;const line=document.createElement('p');line.textContent=failed?'待检查邮件 · Uncertain email deliveries: '+failed:'暂无邮件异常 · No email exceptions';$('coach-issues').append(line);
}
$('slot-form').addEventListener('submit',event=>{event.preventDefault();action(event.submitter,async()=>{const starts=new Date($('slot-time').value+':00+08:00').getTime()/1000;if(!Number.isFinite(starts))throw new Error('请选择日期与时间。 Select a date and time.');await api('/api/coach/slots',{starts_at:starts});$('slot-time').value='';await coachSummary();notice('已开放预约时段 · Availability published');});});
if(!activationToken)member().catch(error=>{if(error.status!==401)notice('暂时无法读取服务状态，请稍后重试。 Service status is temporarily unavailable.');});
