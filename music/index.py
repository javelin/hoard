# index.py
# Index song catalogue and save to songs.db
#
# Creates a document term matrix
# Just an exercise, I know there are better ways
# to do this.
#
# Mark Documento 2017/03/17

import glob, hashlib, os, re, sqlite3, string

common_diacritics = {
    'a': 'âäàá',
    'e': 'êëèé',
    'i': 'îïìí',
    'o': 'ôöòó',
    'u': 'ûüùú',
    'w': 'ŵẅẁẃ',
    'y': 'ŷÿỳý'
}
rx1 = re.compile('[%s]' % re.escape(string.punctuation))
rx2 = {letter: re.compile('[%s]' % re.escape(letters))
       for letter, letters in common_diacritics.items()}

def count(terms):
    l = {}
    for t in terms:
        l[t] = l[t] + 1 if t in l else 1
    return l


conn = sqlite3.connect('songs.db')
cur = conn.cursor()
cur.execute('drop table if exists song')
cur.execute('create table song(id text, artist text, title text, filename text, primary key(id), unique(artist, title))')
cur.execute('drop table if exists matrix')
cur.execute('create table matrix(id text, term text, value int, primary key(id, term))')

sql1 = []
sql2 = []
songs = []
ids = {}
for fn in sorted(glob.glob('songs/*.mp3')):
    noext = os.path.splitext(os.path.basename(fn))[0]
    pair = re.findall('(.*?)-\s*(.*?)\[', noext)[0]
    artist, title = pair
    artist = ' '.join([w.strip() for w in artist.split()])
    title = ' '.join([w.strip() for w in title.split()])

    s = artist + ' ' + title
    s = rx1.sub('', s).lower()
    for letter, rx in rx2.items():
        s = rx.sub(letter, s)
        
    terms = sorted(s.split())

    md5 = hashlib.md5()
    
    md5.update(s.encode('utf-8'))
    id = md5.hexdigest()
    ids[id] = ids[id] + 1 if id in ids else 1

    song = {
        'id': id,
        'artist': artist,
        'title': title,
        'filename': fn,
        'terms': count(terms)
    }
    songs.append(song)

    sql1.append((id, artist, title, fn))
    for term in sorted(song['terms'].keys()):
        sql2.append((id, term, song['terms'][term]))

print('Songs:', len(sql1))
print('Matrix:', len(sql2))

dups = [[song for song in songs if song['id'] == id] for id, n in ids.items() if n > 1]
for dup in dups:
    for du in dup:
        print(du)

print('Duplicates:', len(dups))

print('Inserting into songs...')
cur.executemany('insert into song(id, artist, title, filename) values(?, ?, ?, ?)', sql1)

print('Inserting into matrix...')
cur.executemany('insert into matrix(id, term, value) values(?, ?, ?)', sql2)

conn.commit()
print('Done.')
