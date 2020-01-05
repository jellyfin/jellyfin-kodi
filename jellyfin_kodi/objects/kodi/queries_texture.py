from __future__ import division, absolute_import, print_function, unicode_literals

get_cache = """
SELECT      cachedurl
FROM        texture
WHERE       url = ?
"""


delete_cache = """
DELETE FROM     texture
WHERE           url = ?
"""
