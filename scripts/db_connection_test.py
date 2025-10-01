#!/usr/bin/env python

'''
This is a simple script to test whether your environment is set
up correctly to access the database.
It tests access to the 'dascenacore' Python module and connection
parameters to the database, then performs a very simple query.

If one can run the script without exceptions, it's a success.
'''

from ascl_core.database.connections import Trillian2Connection as db
import ascl_core.database.ascldb.ASCLModelClasses as ascldb

session = db.Session()

codes = session.query(ascldb.ASCLCode).limit(10).all()

for code in codes:
	print(code)


