from dotenv import load_dotenv
load_dotenv()
from core.db import init_db, list_memories
init_db()
memories = list_memories()
print('Total memories:', len(memories))
if memories:
    print('First 3 keys:')
    for m in memories[:3]:
        print(' -', m.get('key'), ':', m.get('content','')[:50])
