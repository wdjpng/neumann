import re

content = """
(100, 100) (200, 200)
(300, 300) (400, 400)
(500, 500) (600, 600)
(700, 700) (800, 800)
(900, 10)
"""
pattern = re.compile(r'\((\d+),\s*(\d+)(?:,\s*(\d+),\s*(\d+))?\)')
matches = [tuple(int(x) for x in match if x) for match in pattern.findall(content)]
print(matches)