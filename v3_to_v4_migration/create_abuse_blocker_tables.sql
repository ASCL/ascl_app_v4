-- Migration: Create abuse blocker tables
-- Date: 2026-04-30
-- Description: Per-IP error counters and blocklist for the in-app abuse
--              detector. Sliding-window rate limiting on unhandled exceptions.

CREATE TABLE IF NOT EXISTS ip_error_event (
	pk INT UNSIGNED NOT NULL AUTO_INCREMENT,
	ip VARCHAR(45) NOT NULL COMMENT 'IPv4 or IPv6 source address',
	ts DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
	PRIMARY KEY (pk),
	KEY idx_ip_ts (ip, ts),
	KEY idx_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Sliding-window log of unhandled-exception events per source IP';

CREATE TABLE IF NOT EXISTS ip_block (
	pk INT UNSIGNED NOT NULL AUTO_INCREMENT,
	ip VARCHAR(45) NOT NULL,
	blocked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	blocked_until DATETIME NOT NULL,
	reason VARCHAR(255),
	PRIMARY KEY (pk),
	UNIQUE KEY uniq_ip (ip),
	KEY idx_blocked_until (blocked_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Active and recent IP blocks';
