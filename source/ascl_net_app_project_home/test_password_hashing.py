#!/usr/bin/env python
"""
Test script for password hashing upgrade (SHA-1 to bcrypt).

This script tests the dual-hash authentication system and demonstrates
the automatic migration from legacy SHA-1 to bcrypt.
"""

import sys
import hashlib
import bcrypt

# Add app to path
sys.path.insert(0, '.')

# Import password utilities from admin controller
from ascl_net_app.controllers.admin import (
	_hash_password_bcrypt,
	_hash_password_sha1,
	_verify_password
)


def test_sha1_hashing():
	"""Test SHA-1 password hashing (legacy)."""
	print("\n=== Test 1: SHA-1 Hashing (Legacy) ===")
	password = "test_password_123"
	sha1_hash = _hash_password_sha1(password)
	print(f"Password: {password}")
	print(f"SHA-1 Hash: {sha1_hash}")
	print(f"Hash length: {len(sha1_hash)} characters")
	assert len(sha1_hash) == 40, "SHA-1 hash should be 40 characters"
	print("✓ SHA-1 hashing works correctly")


def test_bcrypt_hashing():
	"""Test bcrypt password hashing (new)."""
	print("\n=== Test 2: Bcrypt Hashing (New) ===")
	password = "test_password_123"
	bcrypt_hash = _hash_password_bcrypt(password)
	print(f"Password: {password}")
	print(f"Bcrypt Hash: {bcrypt_hash}")
	print(f"Hash length: {len(bcrypt_hash)} characters")
	assert bcrypt_hash.startswith('$2b$'), "Bcrypt hash should start with $2b$"
	assert len(bcrypt_hash) == 60, "Bcrypt hash should be 60 characters"
	print("✓ Bcrypt hashing works correctly")


def test_verify_sha1_password():
	"""Test password verification with SHA-1 hash."""
	print("\n=== Test 3: Verify SHA-1 Password ===")
	password = "my_secure_password"
	sha1_hash = _hash_password_sha1(password)

	# Test correct password
	is_valid, is_legacy = _verify_password(password, sha1_hash)
	print(f"Verifying correct password: is_valid={is_valid}, is_legacy={is_legacy}")
	assert is_valid == True, "Correct password should be valid"
	assert is_legacy == True, "SHA-1 should be marked as legacy"

	# Test incorrect password
	is_valid, is_legacy = _verify_password("wrong_password", sha1_hash)
	print(f"Verifying wrong password: is_valid={is_valid}, is_legacy={is_legacy}")
	assert is_valid == False, "Wrong password should be invalid"

	print("✓ SHA-1 password verification works correctly")


def test_verify_bcrypt_password():
	"""Test password verification with bcrypt hash."""
	print("\n=== Test 4: Verify Bcrypt Password ===")
	password = "my_secure_password"
	bcrypt_hash = _hash_password_bcrypt(password)

	# Test correct password
	is_valid, is_legacy = _verify_password(password, bcrypt_hash)
	print(f"Verifying correct password: is_valid={is_valid}, is_legacy={is_legacy}")
	assert is_valid == True, "Correct password should be valid"
	assert is_legacy == False, "Bcrypt should NOT be marked as legacy"

	# Test incorrect password
	is_valid, is_legacy = _verify_password("wrong_password", bcrypt_hash)
	print(f"Verifying wrong password: is_valid={is_valid}, is_legacy={is_legacy}")
	assert is_valid == False, "Wrong password should be invalid"

	print("✓ Bcrypt password verification works correctly")


def test_migration_scenario():
	"""Test the migration scenario from SHA-1 to bcrypt."""
	print("\n=== Test 5: Migration Scenario ===")
	password = "admin_password"

	# Simulate existing user with SHA-1 password
	old_hash = _hash_password_sha1(password)
	print(f"1. User has SHA-1 hash: {old_hash}")

	# User logs in - verify password
	is_valid, is_legacy = _verify_password(password, old_hash)
	print(f"2. Login verification: is_valid={is_valid}, is_legacy={is_legacy}")
	assert is_valid and is_legacy, "Should authenticate successfully and detect legacy hash"

	# Simulate automatic migration
	new_hash = _hash_password_bcrypt(password)
	print(f"3. After migration, user has bcrypt hash: {new_hash}")

	# Verify new hash works
	is_valid, is_legacy = _verify_password(password, new_hash)
	print(f"4. Next login verification: is_valid={is_valid}, is_legacy={is_legacy}")
	assert is_valid and not is_legacy, "Should authenticate with bcrypt and NOT be legacy"

	print("✓ Migration scenario works correctly")


def main():
	"""Run all password hashing tests."""
	print("=" * 70)
	print("Password Hashing Test Suite")
	print("Testing SHA-1 to bcrypt migration")
	print("=" * 70)

	try:
		test_sha1_hashing()
		test_bcrypt_hashing()
		test_verify_sha1_password()
		test_verify_bcrypt_password()
		test_migration_scenario()

		print("\n" + "=" * 70)
		print("✓ ALL TESTS PASSED")
		print("=" * 70)
		print("\nPassword hashing upgrade is working correctly!")
		print("- Legacy SHA-1 passwords will be automatically migrated on next login")
		print("- New passwords will use bcrypt by default")
		print("- Both hash types are supported during migration period")

	except AssertionError as e:
		print(f"\n✗ TEST FAILED: {e}")
		sys.exit(1)
	except Exception as e:
		print(f"\n✗ ERROR: {e}")
		import traceback
		traceback.print_exc()
		sys.exit(1)


if __name__ == "__main__":
	main()
