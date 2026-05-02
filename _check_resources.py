import re
with open('backend/app/simulation/world.py', encoding='utf-8') as f:
    content = f.read()
types = set(re.findall(r"resource_type\s*=\s*\"([^\"]+)\"", content))
print('resource_types:', types)
