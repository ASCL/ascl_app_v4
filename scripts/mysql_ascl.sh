#!/bin/bash
#
# Helper script for password-less MySQL access to ASCL database
# Uses credentials from ~/.my.cnf [client_ascl] section
#
# Usage:
#   ./scripts/mysql_ascl.sh                    # Interactive session
#   ./scripts/mysql_ascl.sh -e "SQL QUERY"    # Execute query
#
# Example:
#   ./scripts/mysql_ascl.sh -e "SELECT COUNT(*) FROM codes;"
#

mysql --defaults-group-suffix=_ascl ascl_db "$@"
