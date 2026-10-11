import streamlit as st
import pandas as pd
import re
from collections import Counter
import yt_dlp

st.set_page_config(page_title="Analizador de Comentarios", page_icon="📊", layout="wide")

st.title("📊 Analizador de Comentarios")
st.caption("Clasificación según ejes del CEL · YouTube automático · TikTok, Instagram y Facebook: pegar o CSV")

STOPWORDS = set("""
a al algo algunas algunos ante antes como con contra cual cuando de del desde donde dos el ella ellas ellos en entre era erais eramos eran eres es esa esas ese eso esos esta estaba estaban estas este esto estos estoy fin fue fueron fui ha han has hasta hay la las le les lo los mas me mi mis mucho muy ni no nos o os otra otras otro otros para pero poco por porque que quien se si sin sobre son soy su sus te tu un una unas unos y ya yo http https www com
""".split())

POSITIVO = [
    "reforma de justicia", "reforma judicial", "reformar la justicia",
    "cese de la persecucion", "cese de la persecución", "dejen de perseguir",
    "no persigan a la policia", "no persigan a los policias", "no persigan a los policías",
    "no persigan a los militares", "militares hacen su trabajo", "policias hacen su trabajo",
    "policías hacen su trabajo", "fuerzas armadas", "apoyo a las fuerzas armadas",
    "apoyo a la policia", "apoyo a la policía", "apoyo a los militares",
    "izquierda frena", "la izquierda frena", "dejen de frenar", "frenan el pais", "frenan el país",
    "estado eficiente", "estado que funcione", "autoridades que trabajen",
    "necesidades de todos", "trabajen por el pueblo",
    "contra el comunismo", "no al comunismo", "comunismo", "socialismo",
    "contra el socialismo", "no al socialismo",
]

NEGATIVO = [
    "abajo las fuerzas armadas", "fuerzas armadas asesinas", "militares asesinos",
    "militares corruptos", "ataque a las fuerzas armadas",
    "policia asesina", "policía asesina", "policias corruptos", "policías corruptos",
    "odio a la policia", "odio a la policía", "no a la policia", "no a la policía",
    "conspiracion", "conspiración", "golpe de estado", "golpistas",
    "derecha corrupta", "fachos", "fascistas",
    "agenda progresista", "agendas progresistas", "ideologia de genero", "ideología de género",
    "progresismo",
    "contra el capitalismo", "no al capitalismo", "anticapitalista",
    "libre mercado", "contra el libre mercado",
    "antipatriot", "vendepatria", "muerte a la patria",
    "convulsion social", "convulsión social", "que arda", "toma de calles", "a las calles",
]

INSULTOS = [
    "idiota", "imbecil", "imbécil", "estupido", "estúpido", "mierda", "ctm", "conchatumadre",
    "pendejo", "hijo de puta", "hdp", "maldito", "basura", "asco", "tarado", "anormal",
]

FELICITACIONES = [
    "felicidades", "felicitaciones", "felicito", "bravo", "bien dicho", "gracias", "excelente video",
]

def normalizar(text: str) -> str:
    text = text.lower()
    text = text.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    return text

def es_sticker_o_imagen(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return True
    if any(x in t for x in ["[sticker]", "[image]", "[imagen]", "sticker", "gif"]):
        return True
    letras = re.sub(r"[^a-záéíóúñ]", "", t)
    return len(letras) < 3

def es_troll(text: str) -> bool:
    t = normalizar(text)
    if re.fullmatch(r"(ja|je|ji|jo|ha|lol|xd|jaja|jeje)+", re.sub(r"[^a-z]", "", t) or ""):
        return True
    if t.count("jaja") + t.count("jeje") >= 2 and len(t) < 80:
        return True
    return False

def puntaje(text: str, frases: list) -> int:
    t = normalizar(text)
    n = 0
    for frase in frases:
        if normalizar(frase) in t:
            n += 2 if " " in frase else 1
    return n

def clasificar(text: str, positivos: list, negativos: list, insultos: list, felicitaciones: list) -> tuple:
    original = (text or "").strip()
    if len(original) < 60:
        return "neutro", "mensaje corto, menos de 60 caracteres"
    if es_sticker_o_imagen(original):
        return "neutro", "imagen o sticker"
    if es_troll(original):
        return "neutro", "troll"
    t = normalizar(original)
    if any(normalizar(f) in t for f in felicitaciones) and puntaje(original, positivos + negativos) == 0:
        return "neutro", "felicitacion"
    if any(normalizar(i) in t for i in insultos) and puntaje(original, positivos + negativos) == 0:
        return "neutro", "insulto"
    pos = puntaje(original, positivos)
    neg = puntaje(original, negativos)
    if pos == 0 and neg == 0:
        return "neutro", "sin eje"
    if pos > neg:
        return "positivo", "coincide con criterios positivos"
    if neg > pos:
        return "negativo", "coincide con criterios negativos"
    return "neutro", "mezcla de ejes"

def terminos_busqueda(texts: list):
    palabras = []
    bigramas = []
    for raw in texts:
        tokens = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}", raw)
        limpios = [w for w in tokens if normalizar(w) not in STOPWORDS]
        palabras.extend(normalizar(w) for w in limpios)
        for a, b in zip(limpios, limpios[1:]):
            bigramas.append(normalizar(a) + " " + normalizar(b))
    conteo = Counter(palabras)
    conteo_bi = Counter(bigramas)
    elegidos = []
    for frase, n in conteo_bi.most_common():
        if n < 5:
            break
        elegidos.append((frase, n))
    for palabra, n in conteo.most_common():
        if n < 5:
            break
        if any(palabra in e[0].split() for e in elegidos):
            continue
        elegidos.append((palabra, n))
    elegidos.sort(key=lambda x: x[1], reverse=True)
    return elegidos

def fetch_youtube_comments(url: str, max_comments: int = 100):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "getcomments": True,
        "extractor_args": {"youtube": {"max_comments": [str(max_comments), "all", "0", "0"]}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        comments = info.get("comments") or []
        return info.get("title", "Video"), comments

def parse_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        for col in df.columns:
            if any(x in col.lower() for x in ["coment", "text", "mensaje", "comment"]):
                return df[col].dropna().astype(str).tolist()
        return df.iloc[:, 0].dropna().astype(str).tolist()
    except Exception as e:
        st.error(f"Error leyendo CSV: {e}")
        return []

st.subheader("Criterios de clasificación")
st.caption("Edítalos antes de analizar. Una frase o palabra por línea.")
col_p, col_n, col_u = st.columns(3)
with col_p:
    txt_pos = st.text_area("Positivos", "\n".join(POSITIVO), height=220)
with col_n:
    txt_neg = st.text_area("Negativos", "\n".join(NEGATIVO), height=220)
with col_u:
    txt_ins = st.text_area("Insultos (quedan neutros)", "\n".join(INSULTOS), height=110)
    txt_fel = st.text_area("Felicitaciones (quedan neutras)", "\n".join(FELICITACIONES), height=110)

def a_lista(texto: str) -> list:
    return [x.strip() for x in texto.splitlines() if x.strip()]

positivos = a_lista(txt_pos)
negativos = a_lista(txt_neg)
insultos = a_lista(txt_ins)
felicitaciones = a_lista(txt_fel)

plataforma = st.selectbox("Plataforma", ["YouTube", "TikTok", "Instagram", "Facebook"])
comments = []

if plataforma == "YouTube":
    url = st.text_input("Pega el enlace del video de YouTube")
    max_c = st.slider("Máximo de comentarios", 20, 500, 100)
    if st.button("Bajar y analizar", type="primary"):
        if not url:
            st.warning("Pega un enlace primero.")
        else:
            with st.spinner("Descargando comentarios de YouTube..."):
                try:
                    title, raw = fetch_youtube_comments(url, max_c)
                    comments = [c.get("text", "") for c in raw if c.get("text")]
                    st.success(f"Listo: {len(comments)} comentarios de «{title}»")
                except Exception as e:
                    st.error(f"No se pudieron bajar los comentarios: {e}")
else:
    st.info("TikTok, Instagram y Facebook no se bajan solos de forma estable y legal gratis. Pega comentarios o sube un CSV.")
    texto = st.text_area("Pega los comentarios, uno por línea", height=200)
    archivo = st.file_uploader("O sube un CSV", type=["csv"])
    if st.button("Analizar", type="primary"):
        if archivo:
            comments = parse_csv(archivo)
        elif texto.strip():
            comments = [line.strip() for line in texto.splitlines() if line.strip()]
        else:
            st.warning("Pega comentarios o sube un CSV.")

if comments:
    filas = []
    for c in comments:
        clase, motivo = clasificar(c, positivos, negativos, insultos, felicitaciones)
        filas.append({"comentario": c, "clasificacion": clase, "motivo": motivo})
    df = pd.DataFrame(filas)
    orden = {"positivo": 0, "negativo": 1, "neutro": 2}
    df["_orden"] = df["clasificacion"].map(orden)
    df = df.sort_values(["_orden"]).drop(columns="_orden").reset_index(drop=True)
    counts = df["clasificacion"].value_counts()
    total = len(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", total)
    c2.metric("Positivos", f"{int(counts.get('positivo', 0))} ({counts.get('positivo', 0)/total*100:.1f}%)")
    c3.metric("Negativos", f"{int(counts.get('negativo', 0))} ({counts.get('negativo', 0)/total*100:.1f}%)")
    c4.metric("Neutros", f"{int(counts.get('neutro', 0))} ({counts.get('neutro', 0)/total*100:.1f}%)")

    st.subheader("Distribución")
    chart = pd.DataFrame(
        {
            "cantidad": [
                int(counts.get("positivo", 0)),
                int(counts.get("negativo", 0)),
                int(counts.get("neutro", 0)),
            ]
        },
        index=["1. Positivos", "2. Negativos", "3. Neutros"],
    )
    st.bar_chart(chart)

    st.subheader("Términos de búsqueda")
    terminos = terminos_busqueda(comments)
    if terminos:
        term_df = pd.DataFrame(terminos, columns=["término", "menciones"])
        st.dataframe(term_df, use_container_width=True, hide_index=True)
    else:
        st.write("Ningún término llega a 5 menciones.")

    st.subheader("Comentarios")
    vista = df.copy()
    vista["clasificacion"] = vista["clasificacion"].map({
        "positivo": "Positivos",
        "negativo": "Negativos",
        "neutro": "Neutros",
    })
    st.dataframe(vista, use_container_width=True, hide_index=True)
    st.download_button(
        "Descargar CSV",
        vista.to_csv(index=False).encode("utf-8-sig"),
        "analisis_comentarios.csv",
        "text/csv",
    )
    st.caption("Clasificación por reglas de los ejes del CEL. Es orientativa.")

st.markdown("---")
st.caption("Abre con ABRIR.bat · http://localhost:8501")
