import os
import streamlit as st

try:
    import pandas as pd
except Exception as e:
    pd = None

st.set_page_config(page_title="HK Podravka App", page_icon="🤼", layout="centered")

st.title("HK Podravka – administracija")

# ---------- Helpers ----------
def load_coaches(path: str = "coaches.csv"):
    """
    Učitava trenere iz CSV-a (očekuje stupce 'id' i 'name').
    Vraća listu opcija za selectbox i DataFrame (ako je pandas dostupan).
    Sigurno rukuje svim greškama i praznim stanjem.
    """
    # Ako pandas nije dostupan, vratimo prazno stanje
    if pd is None:
        return ["-"], None

    if not os.path.exists(path):
        return ["-"], pd.DataFrame(columns=["id", "name"])

    try:
        df = pd.read_csv(path)
        # Normalizacija naziva stupaca
        cols = {c.lower(): c for c in df.columns}
        # Pokušaj pronaći 'id' i 'name' bez obzira na velika/mala slova
        id_col = cols.get("id") or cols.get("coach_id") or cols.get("sifra") or cols.get("šifra")
        name_col = cols.get("name") or cols.get("coach") or cols.get("ime") or cols.get("naziv")
        if id_col is None and "id" not in df.columns:
            df["id"] = df.index + 1
            id_col = "id"
        if name_col is None and "name" not in df.columns:
            # Pokušaj složiti ime iz dostupnih stupaca
            if {"first_name", "last_name"}.issubset(set([c.lower() for c in df.columns])):
                # pronađi originalne nazive stupaca
                fn = [c for c in df.columns if c.lower() == "first_name"][0]
                ln = [c for c in df.columns if c.lower() == "last_name"][0]
                df["name"] = df[fn].astype(str).str.strip() + " " + df[ln].astype(str).str.strip()
            else:
                df["name"] = df.iloc[:, 0].astype(str)
            name_col = "name"

        # Osiguraj da oba stupca postoje
        df = df[[id_col, name_col]].rename(columns={id_col: "id", name_col: "name"})
        df["id"] = df["id"].astype(str)
        df["name"] = df["name"].astype(str)

        options = ["-"] + [f"{r['id']} – {r['name']}" for _, r in df.iterrows()]
        return options, df
    except Exception:
        # Ako dođe do bilo koje greške pri čitanju, vrati prazno
        empty = pd.DataFrame(columns=["id", "name"])
        return ["-"], empty

# ---------- UI ----------
st.subheader("Odabir trenera")

options, coaches_df = load_coaches()

c_label = st.selectbox("Trener", options, index=0, help="Učitaj 'coaches.csv' u istu mapu kao aplikaciju.")

# Parsiranje odabira: očekujemo format 'id – name'
selected_id = None
selected_name = None
if c_label and c_label != "-":
    if "–" in c_label:
        selected_id, selected_name = [x.strip() for x in c_label.split("–", 1)]
    elif "-" in c_label:
        selected_id, selected_name = [x.strip() for x in c_label.split("-", 1)]
    else:
        selected_name = c_label

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Odabrani ID:**")
    st.code(selected_id or "—")
with col2:
    st.markdown("**Ime trenera:**")
    st.code(selected_name or "—")

# Informativne poruke
if pd is None:
    st.warning("Pandas nije instaliran. Instaliraj paket 'pandas' kako bi se učitali podaci o trenerima.")
elif coaches_df is None or coaches_df.empty:
    st.info("Nije pronađen 'coaches.csv' ili je prazan. Dodaj datoteku sa stupcima 'id' i 'name'.")

st.divider()
st.caption("Ako želiš, mogu dodati i druge sekcije (natjecanja, treninzi, članovi, financije).")
