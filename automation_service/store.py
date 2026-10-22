"""Durable transactional state; one DB lock serializes this small service's writes."""
from contextlib import contextmanager
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer, Text,
                        Boolean, ForeignKey, UniqueConstraint, select)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

meta = MetaData()
guard = Table('mb_write_guard', meta, Column('id', Integer, primary_key=True))
accounts = Table('mb_accounts', meta,
    Column('id', String(64), primary_key=True), Column('email', String(320), unique=True, nullable=False),
    Column('username', String(100), unique=True, nullable=False), Column('password_hash', Text),
    Column('verified_at', Integer), Column('created_at', Integer, nullable=False),
    Column('tracker_used', Boolean, nullable=False, default=False))
customers = Table('mb_customers', meta, Column('id', String(128), primary_key=True),
    Column('account_id', String(64), ForeignKey('mb_accounts.id'), nullable=False))
grants = Table('mb_grants', meta,
    Column('id', String(160), primary_key=True), Column('account_id', String(64), ForeignKey('mb_accounts.id'), nullable=False),
    Column('plan', String(60), nullable=False), Column('subscription_id', String(128)),
    Column('payment_intent', String(128)), Column('starts_at', Integer), Column('ends_at', Integer),
    Column('paid_at', Integer, nullable=False), Column('credits', Integer, nullable=False),
    Column('revoked', Boolean, nullable=False, default=False))
subscriptions = Table('mb_subscriptions', meta, Column('id', String(128), primary_key=True),
    Column('cap_at', Integer), Column('event_time', Integer, nullable=False))
events = Table('mb_events', meta, Column('id', String(128), primary_key=True),
    Column('kind', String(100), nullable=False), Column('processed_at', Integer, nullable=False))
tokens = Table('mb_tokens', meta, Column('hash', String(64), primary_key=True),
    Column('account_id', String(64), ForeignKey('mb_accounts.id'), nullable=False),
    Column('kind', String(20), nullable=False), Column('expires_at', Integer, nullable=False))
outbox = Table('mb_outbox', meta, Column('id', String(200), primary_key=True),
    Column('payload', Text, nullable=False), Column('status', String(20), nullable=False),
    Column('created_at', Integer, nullable=False), Column('claimed_at', Integer), Column('sent_at', Integer))
slots = Table('mb_slots', meta, Column('id', String(64), primary_key=True),
    Column('starts_at', Integer, nullable=False, unique=True), Column('ends_at', Integer, nullable=False),
    Column('status', String(20), nullable=False))
bookings = Table('mb_bookings', meta, Column('id', String(64), primary_key=True),
    Column('slot_id', String(64), ForeignKey('mb_slots.id'), unique=True, nullable=False),
    Column('account_id', String(64), ForeignKey('mb_accounts.id'), nullable=False),
    Column('grant_id', String(160), ForeignKey('mb_grants.id'), nullable=False),
    Column('request_id', String(100), nullable=False), Column('created_at', Integer, nullable=False),
    UniqueConstraint('account_id', 'request_id'))
limits = Table('mb_limits', meta, Column('key', String(64), primary_key=True),
    Column('window', Integer, nullable=False), Column('count', Integer, nullable=False))
issues = Table('mb_issues', meta, Column('id', String(160), primary_key=True),
    Column('kind', String(100), nullable=False), Column('created_at', Integer, nullable=False))
renewals = Table('mb_renewal_checkouts', meta,
    Column('account_id', String(64), ForeignKey('mb_accounts.id'), primary_key=True),
    Column('request_key', String(64), nullable=False), Column('created_at', Integer, nullable=False),
    Column('expires_at', Integer, nullable=False), Column('checkout_id', String(160)), Column('customer_id', String(128)),
    Column('checkout_url', Text))

class Store:
    def __init__(self, url):
        options = {'connect_args': {'check_same_thread':False, 'timeout':30}} if url.startswith('sqlite') else {}
        if url in {'sqlite://', 'sqlite:///:memory:'}: options['poolclass'] = StaticPool
        self.engine = create_engine(url, **options)
        meta.create_all(self.engine)
        try:
            with self.engine.begin() as c: c.execute(guard.insert().values(id=1))
        except IntegrityError: pass

    @contextmanager
    def write(self):
        with self.engine.connect() as c:
            # SQLite ignores FOR UPDATE; take its write lock before the first read.
            if self.engine.dialect.name == 'sqlite': c.exec_driver_sql('BEGIN IMMEDIATE')
            else: c.begin()
            try:
                c.execute(select(guard).where(guard.c.id == 1).with_for_update()).first()
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise

    @contextmanager
    def read(self):
        with self.engine.connect() as c: yield c

def one(c, table, *conditions):
    return c.execute(select(table).where(*conditions)).mappings().first()

def rows(c, table, *conditions):
    return list(c.execute(select(table).where(*conditions)).mappings())
