"""Generate synthetic-only SQL checks from the application schema.

This command emits a plan; it never connects or reads credentials. Execute only
on a dedicated empty test branch/database, with the explicit Neon project and
branch selected. It contains no DROP, DELETE, TRUNCATE or production records.
"""
import argparse
import json
import re
import time
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert
from .store import meta, guard, accounts, grants, events, slots

DIALECT = postgresql.dialect()
TEST_GUARD = "DO $$ BEGIN IF right(current_database(),5) <> '_test' THEN RAISE EXCEPTION 'A dedicated test database is required'; END IF; END $$"


def literal(statement):
    return str(statement.compile(dialect=DIALECT,compile_kwargs={'literal_binds':True}))


def schema_statements():
    return [TEST_GUARD] + [str(CreateTable(t,if_not_exists=True).compile(dialect=DIALECT)) for t in meta.sorted_tables]


def build_plan(run_id, now=None):
    if not re.fullmatch('[a-f0-9]{8,24}',run_id):
        raise ValueError('Use an 8-24 character hexadecimal test run identity.')
    now=int(time.time()) if now is None else int(now)
    prefix='pgqa-'+run_id
    alice,bob=prefix+'-alice',prefix+'-bob'
    grant_a,grant_b=prefix+'-grant-a',prefix+'-grant-b'
    event_id,slot_id=prefix+'-event',prefix+'-slot'
    seed=[TEST_GUARD,literal(insert(guard).values(id=1).on_conflict_do_nothing())]
    for aid in [alice,bob]:
        seed.append(literal(accounts.insert().values(id=aid,email=aid+'@example.invalid',username=aid,
            password_hash=None,verified_at=now,created_at=now,tracker_used=False)))
    def grant(gid,aid):
        return insert(grants).values(id=gid,account_id=aid,plan='consultation-initial',
            subscription_id=None,payment_intent=None,starts_at=now,ends_at=now+7*86400,
            paid_at=now,credits=1,revoked=False).on_conflict_do_nothing()
    seed += [literal(grant(grant_b,bob)),literal(slots.insert().values(id=slot_id,
             starts_at=now+2*86400,ends_at=now+2*86400+2700,status='available'))]
    payment=[TEST_GUARD,'SELECT id FROM mb_write_guard WHERE id=1 FOR UPDATE',
             literal(insert(events).values(id=event_id,kind='synthetic.paid',processed_at=now).on_conflict_do_nothing()),
             literal(grant(grant_a,alice))]
    def booking(aid,gid,label):
        bid=prefix+'-booking-'+label
        rid=prefix+'-request-'+label
        statement=f"""WITH taken AS (
 UPDATE mb_slots SET status='booked' WHERE id='{slot_id}' AND status='available'
 AND EXISTS (SELECT 1 FROM mb_grants WHERE id='{gid}' AND account_id='{aid}' AND credits>0)
 AND NOT EXISTS (SELECT 1 FROM mb_bookings WHERE account_id='{aid}' AND request_id='{rid}') RETURNING id
), debited AS (
 UPDATE mb_grants SET credits=credits-1 WHERE id='{gid}' AND EXISTS(SELECT 1 FROM taken) RETURNING id
), inserted AS (
 INSERT INTO mb_bookings(id,slot_id,account_id,grant_id,request_id,created_at)
 SELECT '{bid}','{slot_id}','{aid}','{gid}','{rid}',{now} WHERE EXISTS(SELECT 1 FROM debited) RETURNING id
) SELECT id FROM inserted"""
        return [TEST_GUARD,'SELECT id FROM mb_write_guard WHERE id=1 FOR UPDATE',statement]
    summary=f"""SELECT
 (SELECT count(*) FROM mb_grants WHERE id='{grant_a}') AS payment_grants,
 (SELECT count(*) FROM mb_events WHERE id='{event_id}') AS payment_events,
 (SELECT count(*) FROM mb_bookings WHERE slot_id='{slot_id}') AS bookings,
 (SELECT sum(credits) FROM mb_grants WHERE id IN ('{grant_a}','{grant_b}')) AS remaining_credits,
 (SELECT count(*) FROM mb_accounts WHERE id='{prefix}-rollback') AS rollback_candidates"""
    rollback=[TEST_GUARD,literal(accounts.insert().values(id=prefix+'-rollback',email=prefix+'-rollback@example.invalid',
        username=prefix+'-rollback',created_at=now,tracker_used=False)),
        literal(events.insert().values(id=event_id,kind='synthetic.duplicate',processed_at=now))]
    export=[]
    for table in meta.sorted_tables:
        columns=','.join('t.'+c.name for c in table.primary_key.columns)
        export.append(f"SELECT '{table.name}' AS table_name, COALESCE(jsonb_agg(to_jsonb(t) ORDER BY {columns}), '[]'::jsonb) AS records FROM {table.name} t")
    return dict(run_id=run_id,synthetic_only=True,schema=schema_statements(),seed=seed,
                payment=payment,booking_a=booking(alice,grant_a,'a'),booking_b=booking(bob,grant_b,'b'),
                expected_rollback_failure=rollback,summary=summary,export=' UNION ALL '.join(export))


def restore_statements(backup):
    """Rebuild an independent EMPTY test database; never overwrite existing rows."""
    by_name={item['table_name']:item['records'] for item in backup}
    if set(by_name)!=set(meta.tables):
        raise ValueError('Backup must contain the complete application table set.')
    statements=schema_statements()
    for table in meta.sorted_tables:
        statements.append(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {table.name}) THEN RAISE EXCEPTION 'Restore requires an empty test database'; END IF; END $$")
    for table in meta.sorted_tables:
        rows=by_name[table.name]
        if isinstance(rows,str): rows=json.loads(rows)
        if not isinstance(rows,list): raise ValueError('Unexpected backup data.')
        for row in rows:
            if table.name=='mb_accounts' and not row['email'].endswith('@example.invalid'):
                raise ValueError('Only synthetic records may be restored by this validation helper.')
            statements.append(literal(table.insert().values(**row)))
    return statements


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    print(json.dumps(build_plan(args.run_id),ensure_ascii=False))


if __name__=='__main__': main()
