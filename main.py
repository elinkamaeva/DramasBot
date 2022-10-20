from urllib import request
import json
import gensim
import sqlite3
from bs4 import BeautifulSoup
import re
from pymorphy2 import MorphAnalyzer
from nltk.tokenize import wordpunct_tokenize

dracor_api = "https://dracor.org/api"


def get_dracor(corpus, length, play=None):
    """Загружает либо метаданные о корпусе, либо текст произведения"""
    url = dracor_api + "/corpora/" + corpus          # Базовый URL
    if play is not None:
        url = url + "/play/" + play + "/tei"         # URL для текста пьесы
    text_lines = []
    pairs = []
    with request.urlopen(url) as tei:
        if play is None:
            info = tei.read().decode()
            return json.loads(info)                  # Парсим и возвращаем JSON метаданные корпуса
        soup = BeautifulSoup(tei, 'lxml')            # Считываем данные
        acts = soup.find_all('div', {'type': 'act'})
        for act in acts:
            scenes = act.find_all('div', {'type': 'scene'})
            if scenes:
                for scene in scenes:
                    sc_lines = []
                    speakers = scene.find_all('sp')
                    for i, sp in enumerate(speakers):
                        if sp.find('p'):
                            str_lines = sp.find_all('p')
                            line = '\n'.join([line.text for line in str_lines])
                            line = re.sub(r'\(.+?\)', '', line)
                        else:
                            str_lines = sp.find_all('l')
                            line = '\n'.join([line.text for line in str_lines])
                            line = re.sub(r'\(.+?\)', '', line)
                        sc_lines.append((length + i, line))
                    sc_pairs = [(length + i, sc_lines[i + 1][1])
                                for i in range(len(sc_lines)) if i < len(sc_lines) - 1]
                    pairs.extend(sc_pairs)
                    sc_lines = sc_lines[:-1]
                    text_lines.extend(sc_lines)
                    length += len(sc_lines)
            else:
                act_lines = []
                speakers = act.find_all('sp')
                for i, sp in enumerate(speakers):
                    if sp.find('p'):
                        str_lines = sp.find_all('p')
                        line = '\n'.join([line.text for line in str_lines])
                        line = re.sub(r'\(.+?\)', '', line)
                    else:
                        str_lines = sp.find_all('l')
                        line = '\n'.join([line.text for line in str_lines])
                        line = re.sub(r'\(.+?\)', '', line)
                    act_lines.append((length + i, line))
                act_pairs = [(length + i, act_lines[i + 1][1])
                             for i in range(len(act_lines)) if i < len(act_lines) - 1]
                pairs.extend(act_pairs)
                act_lines = act_lines[:-1]
                text_lines.extend(act_lines)
                length += len(act_lines)
    return text_lines, pairs, length                      # Возвращаем текст/токены произведения


def get_data(corpus):
    """Скачивает все пьесы из корпуса"""
    lines = []
    pairs = []
    length = 0
    for drama in get_dracor(corpus, length)["dramas"]:       # Пробегаемся по всем произведениям
        name = drama["name"]                         # Название произведения
        text_lines, text_pairs, n = get_dracor(corpus, length, name)
        lines.extend(text_lines)                     # Скачиваем текст
        pairs.extend(text_pairs)
        length = n
    return lines, pairs


lines, pairs = get_data("rus")


morph = MorphAnalyzer()


def read_corpus(chunks, tokens_only=False):
    for i, line in chunks:
        tokens = gensim.utils.simple_preprocess(line)
        lemmas = [morph.parse(token)[0].normal_form for token in tokens]
        if tokens_only:
            yield lemmas
        else:
            yield gensim.models.doc2vec.TaggedDocument(lemmas, [i])


train_corpus = list(read_corpus(lines))

model = gensim.models.doc2vec.Doc2Vec(vector_size=50, min_count=2, epochs=40)
model.build_vocab(train_corpus)
model.train(train_corpus, total_examples=model.corpus_count, epochs=model.epochs)
file = 'dracor.model'
model.save(file)
model = gensim.models.doc2vec.Doc2Vec.load(file)

conn = sqlite3.connect('rus_dracor.db', check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS lines 
(id int PRIMARY KEY, line text)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS answers_to_lines 
(id int PRIMARY KEY, answer text) 
""")

cur.executemany('INSERT INTO lines VALUES (?, ?)', lines)
cur.executemany('INSERT INTO answers_to_lines VALUES (?, ?)', pairs)

conn.commit()


def lemmatize(text):
    tokens = [token for token in wordpunct_tokenize(text)]
    lemmas = [morph.parse(token)[0].normal_form for token in tokens if str(morph.parse(token)[0].tag) != 'PNCT']
    return lemmas


def find_answer(text):
    t_lemmas = lemmatize(text)
    vector = model.infer_vector(t_lemmas)
    sim_id = model.dv.most_similar([vector], topn=1)[0][0]
    cur.execute("SELECT answer FROM answers_to_lines WHERE id = ?", (sim_id,))
    answer = cur.fetchone()[0]
    return answer
