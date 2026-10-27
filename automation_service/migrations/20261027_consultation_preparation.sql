-- Additive migration for consultation checkout and private preparation.
-- Apply to the isolated test database first; no existing rows are rewritten.

CREATE TABLE IF NOT EXISTS mb_consultation_holds (
	id VARCHAR(64) NOT NULL, 
	slot_id VARCHAR(64) NOT NULL, 
	owner_hash VARCHAR(64) NOT NULL, 
	request_id VARCHAR(100) NOT NULL, 
	email VARCHAR(320) NOT NULL, 
	plan VARCHAR(60) NOT NULL, 
	created_at INTEGER NOT NULL, 
	expires_at INTEGER NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	checkout_id VARCHAR(160), 
	checkout_url TEXT, 
	booking_id VARCHAR(64), 
	PRIMARY KEY (id), 
	UNIQUE (owner_hash, request_id), 
	FOREIGN KEY(slot_id) REFERENCES mb_slots (id), 
	UNIQUE (checkout_id)
);

CREATE TABLE IF NOT EXISTS mb_consultation_intakes (
	id VARCHAR(64) NOT NULL, 
	account_id VARCHAR(64) NOT NULL, 
	booking_id VARCHAR(64) NOT NULL, 
	request_id VARCHAR(100) NOT NULL, 
	payload TEXT NOT NULL, 
	created_at INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	consent_version VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (account_id, request_id), 
	FOREIGN KEY(account_id) REFERENCES mb_accounts (id), 
	FOREIGN KEY(booking_id) REFERENCES mb_bookings (id)
);
