import re
T = open('oo_template.md').read()
def sub(m):
    name = m.group(1)
    return "```python\n" + open('../code/'+name).read().rstrip() + "\n```"
open('chapters/30-oo-design.md','w').write(re.sub(r'@@(\S+?)@@', sub, T))
