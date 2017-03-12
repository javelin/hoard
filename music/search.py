# search.py
# Commandline search for a song in song.db. 
# Mark Documento 2017/03/17

import re, sqlite3, string, sys

rx = re.compile('[%s]' % re.escape(string.punctuation))

conn = sqlite3.connect('songs.db')
cur = conn.cursor()

def count(terms):
    l = {}
    for t in terms:
        l[t] = l[t] + 1 if t in l else 1
    return l

if len(sys.argv) == 1:
    print('Usage:', sys.argv[0], '<query>')
    exit()

q = [rx.sub('', term).lower().strip() for term in sys.argv[1:]]
counts = count(q)

cur.execute('drop view if exists query')

sql = ['create view query as select * from matrix']
for term in sorted(counts.keys()):
    sql.append('select "q" as id, "{}" as term, {} as value'.format(term, counts[term]))

cur.execute(' union '.join(sql))
sql = 'select q.score, s.artist, s.title, s.filename from song s join (select b.id as id, sum(a.value*b.value) as score from query a join query b on a.term = b.term where a.id = "q" group by b.id order by score desc limit 20) as q on s.id = q.id order by score desc, artist asc, title asc'

rows = list(cur.execute(sql))
if not rows:
    print('No songs matching your query were found.')
else:
    print('Found {} songs matching your query. You may refine your search to narrow your results.'.format(len(rows)))
    for row in rows:
        score, artist, title, filename = row
        print(artist, '-', title)
        print('  ', filename)
