import re
import os
import shutil
from datetime import datetime
from typing import List
from sqlalchemy import create_engine, text, select
from sqlalchemy import Table, Column
from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session
from sqlalchemy.schema import PrimaryKeyConstraint

engine = create_engine('postgresql+psycopg2:///merlanfrit')
session = Session(engine)

OUTDIR = '../'

HEADER = '<html><link rel="stylesheet" type="text/css" href="style.css" /><body><div class="container">'
FOOTER = '</div></body></html>'

class Base(DeclarativeBase):
    pass

auteurarticle = Table(
    'spip_auteurs_articles',
    Base.metadata,
    Column('id_auteur', ForeignKey("spip_auteurs.id_auteur")),
    Column('id_article', ForeignKey("spip_articles.id_article")),
)

class Auteur(Base):
    __tablename__ = 'spip_auteurs'
    id_auteur:Mapped[int] = mapped_column(primary_key=True)
    nom:Mapped[str]
    
class Article(Base):
    __tablename__ = 'spip_articles'
    id_article:Mapped[int] = mapped_column(primary_key=True)
    titre:Mapped[str]
    descriptif:Mapped[str]
    chapo:Mapped[str]
    texte:Mapped[str]
    ps:Mapped[str]
    date:Mapped[datetime]
    auteurs: Mapped[List[Auteur]] = relationship(secondary=auteurarticle)

class Slug(Base):
    __tablename__ = 'spip_urls'
    url:Mapped[str] = mapped_column(primary_key=True)
    type:Mapped[str]
    id_objet:Mapped[int]
    date:Mapped[datetime]

def extract():
    total = {}
    shutil.copy('index.html', os.path.join(OUTDIR, 'index.html'))
    for a in session.query(Article).order_by(Article.date):
        slug = session.query(Slug).where(Slug.id_objet==a.id_article).where(Slug.type=='article').order_by(Slug.date.desc()).first()
        if slug is None:
            continue
        sr = SpipReader()

        text = HEADER
        text += '<p class="menu"><a href="index.html">Index</a></p>'
        text += '<h1>' + a.titre + '</h1>'
        auteurs = 'anonyme'
        if a.auteurs:
            auteurs = 'par ' + ', '.join([auteur.nom for auteur in a.auteurs])
            text += f'<p class="auteur">{auteurs}</p>'
        date = a.date.strftime('%d/%m/%Y')
        text += '<p class="info">' + date + '</p>'
        text += '<div class="chapo">' + sr.reformat(a.chapo) + '</div>'
        text += sr.reformat(a.texte)
        text += '<div class="ps">' + sr.reformat(a.ps) + '</div>'
        text += sr.get_notes()
        text += FOOTER

        # outdir = os.path.join(OUTDIR, str(a.date.year))
        # os.makedirs(outdir, exist_ok=True)
        outfile = slug.url + '.html'
        with open(os.path.join(OUTDIR, outfile), 'w') as f:
            f.write(text)
        if a.date.year not in total:
            total[a.date.year] = []
        total[a.date.year].append(f'<li><a href="./{outfile}">{a.titre}</a>, <i>{auteurs}</i></li>')
    with open(os.path.join(OUTDIR, 'index.html'), 'a') as f:
        f.write(HEADER)
        for year, l in total.items():
            f.write(f'<h2>{year}</h2><ul>')
            for a in l:
                f.write(a)
            f.write('</ul>')
        f.write(FOOTER)
        

# strings

retour = re.compile(r'\r')
itemize = re.compile(r'-\*')
intertitre = re.compile(r'\{\{\{(.*?)\}\}\}', flags=re.DOTALL)
gras = re.compile(r'\{\{(.*?)\}\}', flags=re.DOTALL)
italic = re.compile(r'\{(.*?)\}', flags=re.DOTALL)
note = re.compile(r'\[\[(.*?)\]\]', flags=re.DOTALL)
mfurl = re.compile(r'http://merlanfrit.net/([^"]*)')
url = re.compile(r'\[([^[]*?)->(.*?)\]', flags=re.DOTALL)
wikiurl = re.compile(r'\[\?(.*?)\]')
suppr = re.compile(r'<img.*?>|<doc.*?>')
paragraph = re.compile(r'\n\n+')

class SpipReader:

    note_idx = 1
    notes = None

    def __init__(self):
        self.notes = []

    def format_urls(self, text):
        # urls
        text = wikiurl.sub(r'<a href="https://fr.wikipedia.org/wiki/\1">\1</a>', text)
        text = url.sub(r'<a href="\2">\1</a>', text)
        text = mfurl.sub(r'./\1.html', text)
        text = suppr.sub(r'', text)
        return text

    def reformat(self, text):

        nbp = []
        # formattage
        text = retour.sub(r'', text)
        text = intertitre.sub(r'<h2>\1</h2>', text)
        text = itemize.sub(r'<br/>&emsp;&mdash;&nbsp;', text)
        text = gras.sub(r'<b>\1</b>', text)
        text = italic.sub(r'<i>\1</i>', text)
        # notes de bas de page reloues
        start, res = 0, ''
        for n in note.finditer(text):
            nbp.append(n.group(1))
            self.notes.append(f'<li id="note{self.note_idx}"><a href="#upnote{self.note_idx}">&uarr;</a>{self.note_idx}. {self.format_urls(text[n.start()+2:n.end()-2])}</li>')
            res += text[start:n.start()]+f'<span id="upnote{self.note_idx}"><sup><a href="#note{self.note_idx}">{self.note_idx}</a></sup></span>'
            start = n.end()
            self.note_idx += 1            
        text = res + text[start:]
        text = self.format_urls(text)

        text = '<p>' + '</p><p>'.join(paragraph.split(text)) + '</p>'

        return text

    def get_notes(self):
        if self.notes:
            return '<ul class="notes">'+''.join(self.notes)+'</ul>'
        return ''